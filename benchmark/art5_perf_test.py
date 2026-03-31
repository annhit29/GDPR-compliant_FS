"""
Benchmark: Collect Workflow Performance (Art 5)

Measures wall-clock time of the Collect workflow (1 PDF, 1 DS "fhublet")
across 3 modes:
  1. baseline       — plain filesystem, no GDPR, no LLM
  2. gdpr_no_llm    — GDPR FUSE filesystem, no LLM analyzer
  3. gdpr_with_llm  — GDPR FUSE filesystem + LLM analyzer

Usage (from instrlib/):
  python -m benchmark.art5_perf_test --mode all --n 5
  python -m benchmark.art5_perf_test --mode baseline --n 2
"""

import argparse
import csv
import json
import os
import shutil
import sqlite3
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent          # instrlib/
FUSE_MOUNT = Path("/tmp/mnt")
UPPER_DIR = Path("/var/lib/gdprfs/upper")
MIRROR_DIR = Path("/var/lib/gdprfs/mirror")

INGEST_URL = "http://127.0.0.1:7000/ingest"
RESOLVE_URL = "http://127.0.0.1:8000/resolve_merge"
CONSENT_PLATFORM_URL = "http://127.0.0.1:5000"
LLM_ANALYZER_URL = "http://127.0.0.1:5005"

CONSENT_DB = BASE_DIR / "external_consent_platform" / "instance" / "external_consent_platform.db"
GDPRFS_DB = BASE_DIR / "gdprfs.db"
MERGE_ALERT_FILE = BASE_DIR / "merge_alerts.json"

DEFAULT_PDF = Path.home() / "Downloads" / "fhublet_collect_5wf2.pdf"
TEST_FILENAME = "fhublet_collect_5wf2.pdf"

import requests


# ── Helper Functions ─────────────────────────────────────────────────────────

def fuse_ingest(kind: str, **kwargs) -> dict:
    """POST an event to the FUSE ingest server (port 7000)."""
    payload = {"kind": kind, **kwargs}
    resp = requests.post(INGEST_URL, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def update_consent_db(uid: str, purpose: str, status: str):
    """Directly upsert consent state in the external consent platform DB.

    Bypasses the 6-second poller so the FUSE daemon's _check_consent()
    sees the consent immediately.
    """
    conn = sqlite3.connect(str(CONSENT_DB))
    cur = conn.cursor()
    row = cur.execute(
        "SELECT current_state_id FROM current_event_state "
        "WHERE uid=? AND purpose=? AND category='consent'",
        (uid, purpose),
    ).fetchone()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if row:
        cur.execute(
            "UPDATE current_event_state SET status=?, updated_at=? "
            "WHERE current_state_id=?",
            (status, now, row[0]),
        )
    else:
        cur.execute(
            "INSERT INTO current_event_state "
            "(uid, purpose, category, status, updated_at) "
            "VALUES (?, ?, 'consent', ?, ?)",
            (uid, purpose, status, now),
        )
    conn.commit()
    conn.close()


def wait_for_merge_alerts(timeout: float = 120, poll_interval: float = 0.5):
    """Block until merge_alerts.json exists and contains at least one alert."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if MERGE_ALERT_FILE.exists():
            try:
                data = json.loads(MERGE_ALERT_FILE.read_text())
                if data.get("alerts"):
                    return data
            except (json.JSONDecodeError, KeyError):
                pass
        time.sleep(poll_interval)
    print(f"  [INFO] No merge alerts after {timeout}s (person may already be merged)")
    return None


def resolve_merge_alerts():
    """Read merge_alerts.json and POST each alert as 'merge' to the internal platform."""
    if not MERGE_ALERT_FILE.exists():
        return
    data = json.loads(MERGE_ALERT_FILE.read_text())
    for alert in data.get("alerts", []):
        requests.post(
            RESOLVE_URL,
            data={
                "alias": alert["alias"],
                "person_id": alert["person_id"],
                "action": "merge",
            },
            timeout=10,
            allow_redirects=False,
        )


def cleanup_iteration():
    """Remove test artifacts between benchmark runs."""
    # 1. Remove the PDF from FUSE mount and storage dirs (may need root)
    for p in (UPPER_DIR / TEST_FILENAME, MIRROR_DIR / TEST_FILENAME,
              FUSE_MOUNT / TEST_FILENAME):
        # Use sudo rm directly to avoid PermissionError on .exists() for root-owned dirs
        subprocess.run(["sudo", "rm", "-f", str(p)],
                       check=False, capture_output=True)

    # 2. Clean gdprfs.db entries for the test file
    if GDPRFS_DB.exists():
        conn = sqlite3.connect(str(GDPRFS_DB))
        cur = conn.cursor()
        # Find file row
        row = cur.execute(
            "SELECT id FROM file WHERE file_id=?", (TEST_FILENAME,)
        ).fetchone()
        if row:
            fid = row[0]
            cur.execute("DELETE FROM person_file_map WHERE file_id=?", (fid,))
            cur.execute(
                "DELETE FROM person_file_special_category WHERE file_id=?", (fid,)
            )
            cur.execute("DELETE FROM file WHERE id=?", (fid,))
        # Remove any alias entries created by this test
        cur.execute("DELETE FROM alias_person_map WHERE alias IN ('hublet')")
        # Remove unregistered Person entries (ghost entries from LLM)
        cur.execute("DELETE FROM person WHERE registered=0")
        conn.commit()
        conn.close()

    # 3. Remove merge alerts file
    MERGE_ALERT_FILE.unlink(missing_ok=True)


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


def preflight_checks(mode: str, pdf_path: Path):
    """Verify preconditions for the given mode. Raises RuntimeError on failure."""
    if not pdf_path.exists():
        raise RuntimeError(f"Source PDF not found: {pdf_path}")

    if mode == "baseline":
        return  # no services needed

    # GDPR modes need FUSE + consent platform
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
        if not _is_reachable(RESOLVE_URL.replace("/resolve_merge", "")):
            raise RuntimeError("Internal purpose platform not reachable (port 8000)")


# ── Workflow Classes ─────────────────────────────────────────────────────────

class BaselineWorkflow:
    """Mode 1: plain filesystem copy, no GDPR, no LLM."""

    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path

    def run(self) -> dict:
        tmp_dir = tempfile.mkdtemp(prefix="gdprfs_bench_")
        try:
            t0 = time.perf_counter()

            # Step 1: StartSession (no-op)
            t_start_session = 0.0

            # Step 2: Consent (no-op)
            t_consent = 0.0

            # Step 3: Copy PDF
            t3 = time.perf_counter()
            shutil.copy2(self.pdf_path, os.path.join(tmp_dir, TEST_FILENAME))
            t_copy = time.perf_counter() - t3

            # Step 4: Merge resolution (no-op)
            t_merge_resolve = 0.0

            # Step 5: StopSession (no-op)
            t_stop_session = 0.0

            t_total = time.perf_counter() - t0
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return {
            "t_start_session": t_start_session,
            "t_consent": t_consent,
            "t_copy": t_copy,
            "t_merge_resolve": t_merge_resolve,
            "t_stop_session": t_stop_session,
            "t_total": t_total,
        }


class GDPRWorkflow:
    """Mode 2/3: GDPR FUSE filesystem, optionally with LLM."""

    def __init__(self, pdf_path: Path, with_llm: bool):
        self.pdf_path = pdf_path
        self.with_llm = with_llm

    def run(self) -> dict:
        t0 = time.perf_counter()

        # Step 1: StartSession
        t1 = time.perf_counter()
        fuse_ingest("StartSession", uid="achao", purpose="marketing",
                     reason="direct_marketing")
        t_start_session = time.perf_counter() - t1

        # Step 2: Consent (send to enforcer + update consent DB directly)
        t2 = time.perf_counter()
        fuse_ingest("Consent", uid="fhublet", purpose="marketing")
        update_consent_db("fhublet", "marketing", "consented")
        t_consent = time.perf_counter() - t2

        # Step 3: Copy PDF to FUSE mount
        # Use raw read+write to avoid shutil calling os.chmod/os.utime
        # which the FUSE filesystem doesn't implement (ENOSYS).
        # In with_llm mode, the write blocks until FUSE write+rename completes,
        # which includes the synchronous LLM analysis call.
        t3 = time.perf_counter()
        dest = FUSE_MOUNT / TEST_FILENAME
        data = self.pdf_path.read_bytes()
        # print(f"\n        [BENCH] Source PDF: {self.pdf_path}")
        # print(f"        [BENCH] Source size: {len(data)} bytes")
        # print(f"        [BENCH] Source first 200 bytes: {data[:200]}")
        dest.write_bytes(data)
        # print(f"        [BENCH] Written to: {dest}")
        # # Verify what ended up in /upper
        # upper_file = UPPER_DIR / TEST_FILENAME
        # if upper_file.exists():
        #     upper_data = upper_file.read_bytes()
        #     print(f"        [BENCH] Upper file size: {len(upper_data)} bytes")
        #     print(f"        [BENCH] Upper first 200 bytes: {upper_data[:200]}")
        # else:
        #     print(f"        [BENCH] Upper file does NOT exist: {upper_file}")
        if self.with_llm:
            wait_for_merge_alerts(timeout=120)
        t_copy = time.perf_counter() - t3

        # Step 4: Merge resolution (only for with_llm mode)
        t4 = time.perf_counter()
        if self.with_llm:
            resolve_merge_alerts()
        t_merge_resolve = time.perf_counter() - t4

        # Step 5: StopSession
        t5 = time.perf_counter()
        fuse_ingest("StopSession", uid="achao")
        t_stop_session = time.perf_counter() - t5

        t_total = time.perf_counter() - t0

        return {
            "t_start_session": t_start_session,
            "t_consent": t_consent,
            "t_copy": t_copy,
            "t_merge_resolve": t_merge_resolve,
            "t_stop_session": t_stop_session,
            "t_total": t_total,
        }


# ── Runner & Reporter ────────────────────────────────────────────────────────

class BenchmarkRunner:
    def __init__(self, mode: str, n: int, pdf_path: Path):
        self.mode = mode
        self.n = n
        self.pdf_path = pdf_path

    def _make_workflow(self):
        if self.mode == "baseline":
            return BaselineWorkflow(self.pdf_path)
        elif self.mode == "gdpr_no_llm":
            return GDPRWorkflow(self.pdf_path, with_llm=False)
        elif self.mode == "gdpr_with_llm":
            return GDPRWorkflow(self.pdf_path, with_llm=True)
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

    def run(self) -> list:
        preflight_checks(self.mode, self.pdf_path)
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
    STEPS = ["t_start_session", "t_consent", "t_copy", "t_merge_resolve",
             "t_stop_session", "t_total"]

    def __init__(self, all_results: dict, output_dir: str):
        self.all_results = all_results  # mode -> list of timing dicts
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_csv(self):
        csv_path = self.output_dir / "art5_perf_results.csv"
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
        fig, ax = plt.subplots(figsize=(10, 5))
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
        ax.set_xticklabels([s.replace("t_", "") for s in steps_no_total], rotation=30)
        ax.set_ylabel("Time (s)")
        ax.set_title("Collect Workflow — Per-Step Latency")
        ax.legend()
        fig.tight_layout()
        fig.savefig(self.output_dir / "art5_per_step.png", dpi=150)
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
        ax.set_title("Collect Workflow — Total Latency")
        fig.tight_layout()
        fig.savefig(self.output_dir / "art5_total.png", dpi=150)
        plt.close(fig)

        print(f"  Charts saved to {self.output_dir}/")


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Benchmark: Collect workflow (Art 5)")
    p.add_argument(
        "--mode",
        choices=["baseline", "gdpr_no_llm", "gdpr_with_llm", "all"],
        default="all",
        help="Which mode(s) to benchmark (default: all)",
    )
    p.add_argument("--n", type=int, default=5, help="Iterations per mode (default: 5)")
    p.add_argument(
        "--pdf",
        type=str,
        default=str(DEFAULT_PDF),
        help=f"Path to source PDF (default: {DEFAULT_PDF})",
    )
    p.add_argument(
        "--output",
        type=str,
        default=str(BASE_DIR / "benchmark" / "results"),
        help="Output directory for CSV and charts",
    )
    return p.parse_args()


def main():
    args = parse_args()
    pdf_path = Path(args.pdf)

    if args.mode == "all":
        modes = ["baseline", "gdpr_no_llm", "gdpr_with_llm"]
    else:
        modes = [args.mode]

    all_results = {}
    for mode in modes:
        print(f"\n{'=' * 60}")
        print(f"  Mode: {mode}  |  Iterations: {args.n}")
        print(f"{'=' * 60}")
        runner = BenchmarkRunner(mode, args.n, pdf_path)
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
