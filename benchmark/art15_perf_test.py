"""
Benchmark: Right of Access Workflow Performance (Art 15)

Measures wall-clock time of the Art 15 access-request workflow
for a data subject (zkowalski) who has consent but NO files in the system,
across 3 modes:
  1. baseline       — plain filesystem, no GDPR, no LLM
  2. gdpr_no_llm    — GDPR FUSE filesystem, no LLM analyzer
  3. gdpr_with_llm  — GDPR FUSE filesystem + LLM analyzer

Usage (from instrlib/):
  python -m benchmark.art15_perf_test --mode all --n 5
  python -m benchmark.art15_perf_test --mode baseline --n 2
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

DS_UID = "zkowalski"


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


def cleanup_iteration():
    """Remove test artifacts between benchmark runs."""
    # Remove access response ZIPs for the test DS
    access_dir = Path("/var/lib/gdprfs/access_responses")
    if access_dir.exists():
        zips = list(access_dir.glob(f"response_{DS_UID}_*.zip"))
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


def preflight_checks(mode: str):
    """Verify preconditions for the given mode. Raises RuntimeError on failure."""
    if mode == "baseline":
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

    if mode == "gdpr_with_llm":
        if not _is_reachable(LLM_ANALYZER_URL):
            raise RuntimeError("LLM analyzer not reachable (port 5005)")
        requests.post(f"{LLM_ANALYZER_URL}/enable", timeout=5)
        print("  [INFO] LLM analyzer enabled for with-LLM benchmark")


# ── Workflow Classes ─────────────────────────────────────────────────────────

class BaselineWorkflow:
    """Mode 1: simulate access request locally, no GDPR, no LLM."""

    def run(self) -> dict:
        tmp_dir = tempfile.mkdtemp(prefix="gdprfs_bench_art15_")
        try:
            t0 = time.perf_counter()

            # Step 1: RequestAccess — create manifest + ZIP locally
            t1 = time.perf_counter()
            manifest = {"data_subject": DS_UID, "files": []}
            zip_path = os.path.join(tmp_dir, f"response_{DS_UID}.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            t_request_access_with_response = time.perf_counter() - t1

            # Step 2: Download ZIP — read from disk
            t2 = time.perf_counter()
            zip_bytes = Path(zip_path).read_bytes()
            verify_empty_zip(zip_bytes, DS_UID)
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

    def __init__(self, with_llm: bool):
        self.with_llm = with_llm

    def run(self) -> dict:
        t0 = time.perf_counter()

        # Step 1: RequestAccess
        t1 = time.perf_counter()
        resp = fuse_ingest("RequestAccess", uid=DS_UID)
        response_id = resp["response_id"]
        t_request_access_with_response = time.perf_counter() - t1

        # Step 2: Download ZIP
        t2 = time.perf_counter()
        zip_bytes = download_zip(response_id)
        verify_empty_zip(zip_bytes, DS_UID)
        t_download_zip = time.perf_counter() - t2

        t_total = time.perf_counter() - t0

        return {
            "t_request_access_with_response": t_request_access_with_response,
            "t_download_zip": t_download_zip,
            "t_total": t_total,
        }


# ── Runner & Reporter ────────────────────────────────────────────────────────

class BenchmarkRunner:
    def __init__(self, mode: str, n: int):
        self.mode = mode
        self.n = n

    def _make_workflow(self):
        if self.mode == "baseline":
            return BaselineWorkflow()
        elif self.mode == "gdpr_no_llm":
            return GDPRWorkflow(with_llm=False)
        elif self.mode == "gdpr_with_llm":
            return GDPRWorkflow(with_llm=True)
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

    def run(self) -> list:
        preflight_checks(self.mode)
        results = []
        for i in range(self.n):
            print(f"  [{self.mode}] iteration {i + 1}/{self.n} ... ", end="", flush=True)
            cleanup_iteration()
            time.sleep(0.5)  # brief settle time after cleanup
            workflow = self._make_workflow()
            try:
                timings = workflow.run()
                timings["iteration"] = i + 1
                timings["mode"] = self.mode
                results.append(timings)
                print(f"total={timings['t_total']:.4f}s")
            except Exception as e:
                print(f"FAILED: {e}")
            cleanup_iteration()
        return results


class BenchmarkReporter:
    STEPS = ["t_request_access_with_response", "t_download_zip", "t_total"]

    def __init__(self, all_results: dict, output_dir: str):
        self.all_results = all_results  # mode -> list of timing dicts
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_csv(self):
        csv_path = self.output_dir / "art15_wf2_perf_results.csv"
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
            ax.bar(offsets, means, width, yerr=stds, label=mode, capsize=3)

        ax.set_xticks(list(x))
        ax.set_xticklabels([s.removeprefix("t_") for s in steps_no_total], rotation=30)
        ax.set_ylabel("Time (s)")
        ax.set_title("Art 15 Right of Access (No Files) — Per-Step Latency")
        ax.legend()
        fig.tight_layout()
        fig.savefig(self.output_dir / "art15_wf2_per_step.png", dpi=150)
        plt.close(fig)

        # ── Total latency bar chart ──
        fig, ax = plt.subplots(figsize=(6, 4))
        totals = [statistics.mean([r["t_total"] for r in self.all_results[m]])
                  for m in modes]
        stds = [statistics.stdev([r["t_total"] for r in self.all_results[m]])
                if len(self.all_results[m]) > 1 else 0.0
                for m in modes]
        colors = ["#4c78a8", "#f58518", "#e45756"][:len(modes)]
        ax.bar(modes, totals, yerr=stds, capsize=5, color=colors)
        ax.set_ylabel("Time (s)")
        ax.set_title("Art 15 Right of Access (No Files) — Total Latency")
        fig.tight_layout()
        fig.savefig(self.output_dir / "art15_wf2_total.png", dpi=150)
        plt.close(fig)

        print(f"  Charts saved to {self.output_dir}/")


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Benchmark: Right of Access workflow (Art 15, DS with no files)")
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

    if args.mode == "all":
        modes = ["baseline", "gdpr_no_llm", "gdpr_with_llm"]
    else:
        modes = [args.mode]

    all_results = {}
    for mode in modes:
        print(f"\n{'=' * 60}")
        print(f"  Mode: {mode}  |  Iterations: {args.n}")
        print(f"{'=' * 60}")
        runner = BenchmarkRunner(mode, args.n)
        try:
            results = runner.run()
        except RuntimeError as e:
            print(f"  SKIPPED: {e}")
            continue
        if results:
            all_results[mode] = results
            print(f"  Completed {len(results)}/{args.n} iterations")

    if all_results:
        reporter = BenchmarkReporter(all_results, args.output)
        reporter.save_csv()
        reporter.print_summary()
        reporter.save_charts()
        print("Done.")
    else:
        print("\nNo results collected.")


if __name__ == "__main__":
    main()
