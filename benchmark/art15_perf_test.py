"""
Benchmark: Right of Access Workflow Performance (Art 15)
"""

import argparse
import csv
import io
import json
import os
import shutil
import statistics
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

import requests

# ── Constants ────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent          # instrlib/
FUSE_MOUNT = Path("/tmp/mnt")
UPPER_DIR = Path("/var/lib/gdprfs/upper")
MIRROR_DIR = Path("/var/lib/gdprfs/mirror")

INGEST_URL = "http://127.0.0.1:7000/ingest"
ACCESS_DOWNLOAD_URL = "http://127.0.0.1:7000/access_download"
CONSENT_PLATFORM_URL = "http://127.0.0.1:5000"
LLM_ANALYZER_URL = "http://127.0.0.1:5005"

CONSENT_DB = BASE_DIR / "external_consent_platform" / "instance" / "external_consent_platform.db"
GDPRFS_DB = BASE_DIR / "gdprfs.db"

DS_UID_1 = "fhublet"

DS_UID_2 = "zkowalski"

# Baseline source directory.
# For the baseline mode, the script reads these existing files and packages them locally.
# Change this if your plain-FS baseline files live elsewhere.
BASELINE_SOURCE_DIR = FUSE_MOUNT

EXPECTED_MANIFEST = {
  "data_subject": "fhublet",
  "files": [
    {
      "file_id": "fhublet_collect_5wf2.pdf",
      "filename": "fhublet_collect_5wf2.pdf"
    },
    {
      "file_id": "fhublet_collection.pdf",
      "filename": "fhublet_collection.pdf"
    },
    {
      "file_id": "fhublet.txt",
      "filename": "fhublet.txt"
    },
    {
      "file_id": "jdoe&whsieh&fhublet_spCat246.txt",
      "filename": "jdoe&whsieh&fhublet_spCat246.txt",
      "special_categories_art9": [
        "racial_ethnic"
      ]
    },
    {
      "file_id": "fhublet&whsieh&jdoe.txt",
      "filename": "fhublet&whsieh&jdoe.txt"
    }
  ]
}

# ── Helper Functions ─────────────────────────────────────────────────────────

def fuse_ingest(kind: str, **kwargs) -> dict:
    """POST an event to the FUSE ingest server (port 7000)."""
    payload = {"kind": kind, **kwargs}
    resp = requests.post(INGEST_URL, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def download_zip(response_id: str) -> bytes:
    """GET the access-response ZIP from the FUSE ingest server."""
    resp = requests.get(f"{ACCESS_DOWNLOAD_URL}/{response_id}", timeout=10)
    resp.raise_for_status()
    return resp.content

def _normalize_manifest(manifest: dict) -> dict:
    """Normalize manifest so comparison is stable."""
    out = {"data_subject": manifest.get("data_subject"), "files": []}
    for entry in manifest.get("files", []):
        norm = {
            "file_id": entry.get("file_id"),
            "filename": entry.get("filename"),
        }
        if "special_categories_art9" in entry:
            norm["special_categories_art9"] = sorted(entry.get("special_categories_art9", []))
        out["files"].append(norm)

    out["files"].sort(key=lambda x: (x.get("file_id") or "", x.get("filename") or ""))
    return out

def verify_expected_zip(zip_bytes: bytes, expected_manifest: dict):
    """
    Verify ZIP contains:
    - manifest.json
    - expected data_subject
    - expected files list
    - expected special_categories_art9
    - each listed filename physically present in the ZIP
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names, f"Expected manifest.json in ZIP, got {sorted(names)}"

        manifest = json.loads(zf.read("manifest.json"))
        got = _normalize_manifest(manifest)
        exp = _normalize_manifest(expected_manifest)

        assert got["data_subject"] == exp["data_subject"], (
            f"Expected data_subject={exp['data_subject']!r}, got {got['data_subject']!r}"
        )
        assert got["files"] == exp["files"], (
            "Manifest mismatch.\n"
            f"Expected: {json.dumps(exp, indent=2, ensure_ascii=False)}\n"
            f"Got:      {json.dumps(got, indent=2, ensure_ascii=False)}"
        )

        for entry in exp["files"]:
            filename = entry["filename"]
            assert filename in names, f"Expected file {filename!r} in ZIP, got {sorted(names)}"

def verify_empty_zip(zip_bytes: bytes, uid: str):
    """Assert the ZIP contains only manifest.json with an empty files list."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names, f"Expected manifest.json in ZIP, got {names}"
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest.get("data_subject") == uid, (
            f"Expected data_subject={uid!r}, got {manifest.get('data_subject')!r}"
        )
        assert manifest.get("files") == [], (
            f"Expected empty files list, got {manifest.get('files')!r}"
        )

def cleanup_iteration(workflow: str):
    """Remove test artifacts between benchmark runs."""
    access_dir = Path("/var/lib/gdprfs/access_responses")
    if access_dir.exists():
        uid = DS_UID_1 if workflow == "wf1" else DS_UID_2
        zips = list(access_dir.glob(f"response_{uid}_*.zip"))
        if zips:
            subprocess.run(
                ["sudo", "rm", "-f"] + [str(p) for p in zips],
                check=False, capture_output=True,
            )


def _is_fuse_mounted() -> bool:
    try:
        with open("/proc/mounts") as f:
            return any("/tmp/mnt" in line for line in f)
    except FileNotFoundError:
        return False


def _is_reachable(url: str) -> bool:
    try:
        requests.get(url, timeout=2)
        return True
    except Exception:
        return False

def preflight_checks(workflow: str, mode: str):
    """Verify preconditions for the given workflow/mode."""
    if mode == "baseline":
        if workflow == "wf1":
            missing = []
            for entry in EXPECTED_MANIFEST["files"]:
                p = BASELINE_SOURCE_DIR / entry["filename"]
                if not p.exists():
                    missing.append(str(p))
            if missing:
                raise RuntimeError(
                    "Baseline source files not found:\n  " + "\n  ".join(missing)
                )
        elif workflow == "wf2":
            pass
        else:
            raise RuntimeError(f"Unknown workflow: {workflow}")
        return

    if not _is_fuse_mounted():
        raise RuntimeError("FUSE filesystem not mounted at /tmp/mnt")
    if not _is_reachable(CONSENT_PLATFORM_URL):
        raise RuntimeError("External consent platform not reachable (port 5000)")
    if not CONSENT_DB.exists():
        raise RuntimeError(f"Consent DB not found: {CONSENT_DB}")

    if mode == "gdpr_no_llm":
        if _is_reachable(LLM_ANALYZER_URL):
            requests.post(f"{LLM_ANALYZER_URL}/disable", timeout=5)
            print("  [INFO] LLM analyzer disabled for no-LLM benchmark")

    elif mode == "gdpr_with_llm":
        if not _is_reachable(LLM_ANALYZER_URL):
            raise RuntimeError("LLM analyzer not reachable (port 5005)")
        requests.post(f"{LLM_ANALYZER_URL}/enable", timeout=5)
        print("  [INFO] LLM analyzer enabled for with-LLM benchmark")


# ── Workflow Classes ─────────────────────────────────────────────────────────
class BaselineWorkflow1:
    """
    Plain filesystem baseline.

    It locally packages the already-existing fhublet files plus the expected manifest,
    without touching any DB and without mutating the source files.
    """

    def run(self) -> dict:
        t0 = time.perf_counter()

        # Step 1: RequestAccess + response generation (synthetic baseline)
        t1 = time.perf_counter()
        with tempfile.NamedTemporaryFile(prefix=f"response_{DS_UID_1}_", suffix=".zip") as tmp:
            zip_path = Path(tmp.name)

            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("manifest.json", json.dumps(EXPECTED_MANIFEST, indent=2))
                for entry in EXPECTED_MANIFEST["files"]:
                    src = BASELINE_SOURCE_DIR / entry["filename"]
                    zf.write(src, arcname=entry["filename"])

            t_request_access_with_response = time.perf_counter() - t1

            # Step 2: Download ZIP (local read)
            t2 = time.perf_counter()
            zip_bytes = zip_path.read_bytes()
            verify_expected_zip(zip_bytes, EXPECTED_MANIFEST)
            t_download_zip = time.perf_counter() - t2

        t_total = time.perf_counter() - t0

        return {
            "t_request_access_with_response": t_request_access_with_response,
            "t_download_zip": t_download_zip,
            "t_total": t_total,
        }



class BaselineWorkflow2:
    """Mode 1: simulate access request locally, no GDPR, no LLM."""

    def run(self) -> dict:
        tmp_dir = tempfile.mkdtemp(prefix="gdprfs_bench_art15_")
        try:
            t0 = time.perf_counter()

            # Step 1: RequestAccess — create manifest + ZIP locally
            t1 = time.perf_counter()
            manifest = {"data_subject": DS_UID_2, "files": []}
            zip_path = os.path.join(tmp_dir, f"response_{DS_UID_2}.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            t_request_access_with_response = time.perf_counter() - t1

            # Step 2: Download ZIP — read from disk
            t2 = time.perf_counter()
            zip_bytes = Path(zip_path).read_bytes()
            verify_empty_zip(zip_bytes, DS_UID_2)
            t_download_zip = time.perf_counter() - t2

            t_total = time.perf_counter() - t0
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return {
            "t_request_access_with_response": t_request_access_with_response,
            "t_download_zip": t_download_zip,
            "t_total": t_total,
        }


class GDPRWorkflow:
    """Mode 2/3: GDPR FUSE filesystem, optionally with LLM."""

    def __init__(self, workflow: str, with_llm: bool):
        self.workflow = workflow
        self.with_llm = with_llm

    def run(self) -> dict:
        t0 = time.perf_counter()

        # Step 1: RequestAccess
        t1 = time.perf_counter()

        if self.workflow == "wf1":
            resp = fuse_ingest("RequestAccess", uid=DS_UID_1)
        else:#if self.workflow == "wf2"
            resp = fuse_ingest("RequestAccess", uid=DS_UID_2)

        response_id = resp["response_id"]
        t_request_access_with_response = time.perf_counter() - t1

        # Step 2: Download ZIP
        t2 = time.perf_counter()
        zip_bytes = download_zip(response_id)

        if self.workflow == "wf1":        
            verify_expected_zip(zip_bytes, EXPECTED_MANIFEST)
        else:
            verify_empty_zip(zip_bytes, DS_UID_2)
    
        t_download_zip = time.perf_counter() - t2

        t_total = time.perf_counter() - t0

        return {
            "t_request_access_with_response": t_request_access_with_response,
            "t_download_zip": t_download_zip,
            "t_total": t_total,
        }


# ── Runner & Reporter ────────────────────────────────────────────────────────

class BenchmarkRunner:
    def __init__(self, workflow: str, mode: str, n: int):
        self.workflow = workflow
        self.mode = mode
        self.n = n

    def _make_workflow(self):
        if self.workflow == "wf1":
            if self.mode == "baseline":
                return BaselineWorkflow1()
            elif self.mode == "gdpr_no_llm":
                return GDPRWorkflow("wf1", with_llm=False)
            elif self.mode == "gdpr_with_llm":
                return GDPRWorkflow("wf1", with_llm=True)

        elif self.workflow == "wf2":
            if self.mode == "baseline":
                return BaselineWorkflow2()
            elif self.mode == "gdpr_no_llm":
                return GDPRWorkflow("wf2", with_llm=False)
            elif self.mode == "gdpr_with_llm":
                return GDPRWorkflow("wf2", with_llm=True)

        raise ValueError(f"Unknown workflow/mode: {self.workflow}/{self.mode}")


    def run(self) -> list:
        preflight_checks(self.workflow, self.mode)
        results = []
        for i in range(self.n):
            print(f"  [{self.workflow} | {self.mode}] iteration {i + 1}/{self.n} ... ", end="", flush=True)
            cleanup_iteration(self.workflow)
            time.sleep(0.5)  # brief settle time after cleanup
            workflow = self._make_workflow()
            try:
                timings = workflow.run()
                timings["iteration"] = i + 1
                timings["workflow"] = self.workflow
                timings["mode"] = self.mode
                results.append(timings)
                print(f"total={timings['t_total']:.4f}s")
            except Exception as e:
                print(f"FAILED: {e}")
            cleanup_iteration(self.workflow)
        return results


WF_TITLES = {
    "wf1": "DS With Files (fhublet)",
    "wf2": "DS With No Files (zkowalski)",
}


class BenchmarkReporter:
    STEPS = ["t_request_access_with_response", "t_download_zip", "t_total"]

    def __init__(self, workflow: str, all_results: dict, output_dir: str):
        self.workflow = workflow
        self.all_results = all_results  # mode -> list of timing dicts
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_csv(self):
        csv_path = self.output_dir / f"art15_{self.workflow}_perf_results.csv"
        fieldnames = ["mode", "iteration"] + self.STEPS
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for mode, results in self.all_results.items():
                for row in results:
                    writer.writerow({k: row.get(k, "") for k in fieldnames})
        print(f"\n  CSV saved to {csv_path}")

    def print_summary(self):
        modes = list(self.all_results.keys())
        col_w = 16

        print(f"\n{'=' * 70}")
        print("  Mean ± Std latency per step (seconds)")
        print(f"{'=' * 70}")
        header = f"  {'Step':<22}" + "".join(f"{m:>{col_w}}" for m in modes)
        print(header)
        print("  " + "-" * (22 + col_w * len(modes)))

        for step in self.STEPS:
            row = f"  {step:<22}"
            for mode in modes:
                vals = [r[step] for r in self.all_results[mode]]
                mean = statistics.mean(vals)
                std = statistics.stdev(vals) if len(vals) > 1 else 0.0
                row += f"{mean:>{col_w - 8}.4f}±{std:<7.4f}"
            print(row)
        print()

    def save_charts(self):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            print("  [WARN] matplotlib not installed — skipping charts")
            return

        modes = list(self.all_results.keys())
        steps_no_total = [s for s in self.STEPS if s != "t_total"]

        # ── Per-step grouped bar chart ──
        fig, ax = plt.subplots(figsize=(8, 5))
        x = range(len(steps_no_total))
        width = 0.8 / len(modes)
        for i, mode in enumerate(modes):
            means = [statistics.mean([r[s] for r in self.all_results[mode]])
                     for s in steps_no_total]
            stds = [statistics.stdev([r[s] for r in self.all_results[mode]])
                    if len(self.all_results[mode]) > 1 else 0.0
                    for s in steps_no_total]
            offsets = [xi - 0.4 + width * (i + 0.5) for xi in x]
            ax.bar(offsets, means, width, label=mode)

        ax.set_xticks(list(x))
        ax.set_xticklabels([s.removeprefix("t_") for s in steps_no_total], rotation=30)
        ax.set_ylabel("Time (s)")
        wf_title = WF_TITLES.get(self.workflow, self.workflow)
        ax.set_title(f"Art 15 Right of Access ({wf_title}) — Per-Step Latency")
        ax.legend()
        fig.tight_layout()
        fig.savefig(self.output_dir / f"art15_{self.workflow}_per_step.png", dpi=150)
        plt.close(fig)

        # ── Total latency bar chart ──
        fig, ax = plt.subplots(figsize=(6, 4))
        totals = [statistics.mean([r["t_total"] for r in self.all_results[m]])
                  for m in modes]
        stds = [statistics.stdev([r["t_total"] for r in self.all_results[m]])
                if len(self.all_results[m]) > 1 else 0.0
                for m in modes]
        colors = ["#4c78a8", "#f58518", "#e45756"][:len(modes)]
        ax.bar(modes, totals, color=colors)
        ax.set_ylabel("Time (s)")
        ax.set_title(f"Art 15 Right of Access ({wf_title}) — Total Latency")
        fig.tight_layout()
        fig.savefig(self.output_dir / f"art15_{self.workflow}_total.png", dpi=150)
        plt.close(fig)

        print(f"  Charts saved to {self.output_dir}/")


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Benchmark: Right of Access workflow (Art 15, DS with no files)")
    p.add_argument(
        "--workflow",
        choices=["wf1", "wf2", "all"],
        default="all",
        help="Which Art. 15 workflow(s) to benchmark (default: all)",
    )
    p.add_argument(
        "--mode",
        choices=["baseline", "gdpr_no_llm", "gdpr_with_llm", "all"],
        default="all",
        help="Which mode(s) to benchmark (default: all)",
    )
    p.add_argument("--n", type=int, default=5, help="Iterations per mode (default: 5)")
    p.add_argument(
        "--output",
        type=str,
        default=str(BASE_DIR / "benchmark" / "results"),
        help="Output directory for CSV and charts",
    )
    return p.parse_args()


def main():
    args = parse_args()

    if args.workflow == "all":
        workflows = ["wf1", "wf2"]
    else:
        workflows = [args.workflow]

    if args.mode == "all":
        modes = ["baseline", "gdpr_no_llm", "gdpr_with_llm"]
    else:
        modes = [args.mode]

    for wf in workflows:
        all_results = {}
        for mode in modes:
            print(f"\n{'=' * 60}")
            print(f"  Workflow: {wf}  |  Mode: {mode}  |  Iterations: {args.n}")
            print(f"{'=' * 60}")
            runner = BenchmarkRunner(wf, mode, args.n)
            try:
                results = runner.run()
            except RuntimeError as e:
                print(f"  SKIPPED: {e}")
                continue
            if results:
                all_results[mode] = results
                print(f"  Completed {len(results)}/{args.n} iterations")

        if all_results:
            reporter = BenchmarkReporter(wf, all_results, args.output)
            reporter.save_csv()
            reporter.print_summary()
            reporter.save_charts()
            print(f"Done ({wf}).")
        else:
            print(f"\nNo results collected for {wf}.")


if __name__ == "__main__":
    main()
