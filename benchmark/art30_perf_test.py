"""
Benchmark: Records of Processing Activities Workflow Performance (Art 30)

Measures wall-clock time of an Art 30 workflow — read, write, rename, revoke,
suppressed read — for data subject jdoe (file: jdoe_health.txt) across 2 modes:
  1. baseline       — plain filesystem, no GDPR, no LLM
  2. gdpr_with_llm  — GDPR FUSE filesystem + LLM analyzer

Workflow:
  1.  StartSession("achao", "marketing", "direct_marketing")
  2.  Consent("jdoe","marketing") + SpecialConsent("jdoe","marketing","health")
  3.  Internal user reads jdoe_health.txt (Use + SpecialData + processing_records)
  4-5. Internal user writes file (.→ :() + close (Collect + SpecialData + processing_records)
  6.  Rename to jdoe_health_renamedTest.txt (Collect + SpecialData + processing_records)
  7.  Rename back to jdoe_health.txt (Collect)
  8.  RevokeSpecialConsent("jdoe","marketing","health")
  9-10. Read after revoke → REDACTED + close
  11. StopSession("achao")

Safety: snapshot_state() backs up jdoe_health.txt, DB rows, and processing_record
max(id) before first iteration; cleanup_iteration() restores everything after each.

Usage (from instrlib/):
  python -m benchmark.art30_perf_test --mode all --n 5
  python -m benchmark.art30_perf_test --mode baseline --n 2
"""

import argparse
import csv
import os
import shutil
import sqlite3
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── Constants ────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent          # instrlib/
FUSE_MOUNT = Path("/tmp/mnt")
UPPER_DIR = Path("/var/lib/gdprfs/upper")
MIRROR_DIR = Path("/var/lib/gdprfs/mirror")

INGEST_URL = "http://127.0.0.1:7000/ingest"
CONSENT_PLATFORM_URL = "http://127.0.0.1:5000"
LLM_ANALYZER_URL = "http://127.0.0.1:5005"

CONSENT_DB = BASE_DIR / "external_consent_platform" / "instance" / "external_consent_platform.db"
GDPRFS_DB = BASE_DIR / "gdprfs.db"

DS_UID = "jdoe"
CONTROLLER_UID = "achao"
SPECIAL_CATS = ["health"]
BACKUP_DIR = Path.home() / "Downloads" / "upper_copy_for_benchmark"
TARGET_FILE = "jdoe_health.txt"
RENAMED_FILE = "jdoe_health_renamedTest.txt"


# ── Helper Functions ─────────────────────────────────────────────────────────

def fuse_ingest(kind: str, **kwargs) -> dict:
    """POST an event to the FUSE ingest server (port 7000)."""
    payload = {"kind": kind, **kwargs}
    resp = requests.post(INGEST_URL, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def update_consent_db(uid: str, purpose: str, status: str):
    """Directly upsert consent state in the external consent platform DB."""
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


def update_special_consent_db(uid: str, purpose: str, spCat: str, status: str):
    """Directly upsert special consent state (Art 9) in the consent DB."""
    conn = sqlite3.connect(str(CONSENT_DB))
    cur = conn.cursor()
    row = cur.execute(
        "SELECT current_state_id FROM current_event_state "
        "WHERE uid=? AND purpose=? AND category='special_consent' AND spCat=?",
        (uid, purpose, spCat),
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
            "(uid, purpose, category, spCat, status, updated_at) "
            "VALUES (?, ?, 'special_consent', ?, ?, ?)",
            (uid, purpose, spCat, status, now),
        )
    conn.commit()
    conn.close()


# ── Snapshot & Restore ───────────────────────────────────────────────────────

def snapshot_state() -> dict:
    """Back up jdoe_health.txt and its DB rows before the benchmark starts."""
    # 1. Verify backup exists
    backup_path = BACKUP_DIR / TARGET_FILE
    if not backup_path.exists():
        raise RuntimeError(f"Backup file not found: {backup_path}")

    # 2. Snapshot gdprfs.db rows (read-only access is fine)
    conn = sqlite3.connect(str(GDPRFS_DB))
    cur = conn.cursor()
    file_row = cur.execute(
        "SELECT * FROM file WHERE file_id=?", (TARGET_FILE,)
    ).fetchone()
    if not file_row:
        conn.close()
        raise RuntimeError(f"{TARGET_FILE} not found in gdprfs.db file table")

    file_pk = file_row[0]  # file.id (primary key)
    pfm_rows = cur.execute(
        "SELECT * FROM person_file_map WHERE file_id=?", (file_pk,)
    ).fetchall()
    pfsc_rows = cur.execute(
        "SELECT * FROM person_file_special_category WHERE file_id=?", (file_pk,)
    ).fetchall()

    # 3. Record max processing_record id (to delete new rows after each iteration)
    max_pr_id = cur.execute("SELECT MAX(id) FROM processing_record").fetchone()[0]
    if max_pr_id is None:
        max_pr_id = 0
    conn.close()

    print(f"  [SNAPSHOT] Backed up {TARGET_FILE} → {backup_path}")
    print(f"  [SNAPSHOT] file row: id={file_pk}, pfm_rows={len(pfm_rows)}, "
          f"pfsc_rows={len(pfsc_rows)}, max_pr_id={max_pr_id}")

    return {
        "backup_path": backup_path,
        "file_row": file_row,
        "file_pk": file_pk,
        "pfm_rows": pfm_rows,
        "pfsc_rows": pfsc_rows,
        "max_pr_id": max_pr_id,
    }


def cleanup_iteration(snapshot: dict):
    """Restore files, DB rows, processing_records, and consent state."""
    # 1. Restore physical file to upper + mirror
    for target_dir in (UPPER_DIR, MIRROR_DIR):
        subprocess.run(
            ["sudo", "cp", str(BACKUP_DIR / TARGET_FILE), str(target_dir / TARGET_FILE)],
            check=False, capture_output=True,
        )

    # 2. Remove renamed file remnants from upper + mirror
    for target_dir in (UPPER_DIR, MIRROR_DIR):
        subprocess.run(
            ["sudo", "rm", "-f", str(target_dir / RENAMED_FILE)],
            check=False, capture_output=True,
        )

    # 3. Clean up gdprfs.db (root-owned, use sudo sqlite3)
    max_pr_id = snapshot["max_pr_id"]
    sql_lines = []

    # 3a. Delete new processing_record rows
    sql_lines.append(f"DELETE FROM processing_record WHERE id > {max_pr_id};")

    # 3b. Delete renamed file DB entries (must delete dependent rows first)
    sql_lines.append(
        f"DELETE FROM person_file_special_category WHERE file_id IN "
        f"(SELECT id FROM file WHERE file_id='{RENAMED_FILE}');"
    )
    sql_lines.append(
        f"DELETE FROM person_file_map WHERE file_id IN "
        f"(SELECT id FROM file WHERE file_id='{RENAMED_FILE}');"
    )
    sql_lines.append(f"DELETE FROM file WHERE file_id='{RENAMED_FILE}';")

    sql = "\n".join(sql_lines)
    subprocess.run(
        ["sudo", "sqlite3", str(GDPRFS_DB)],
        input=sql, text=True, check=False, capture_output=True,
    )

    # 3c. Re-insert original file row if missing
    check = subprocess.run(
        ["sudo", "sqlite3", str(GDPRFS_DB),
         f"SELECT id FROM file WHERE file_id='{TARGET_FILE}';"],
        capture_output=True, text=True,
    )
    if not check.stdout.strip():
        sql_lines = []
        vals = ",".join(
            "NULL" if v is None else f"'{v}'" if isinstance(v, str) else str(v)
            for v in snapshot["file_row"]
        )
        sql_lines.append(f"INSERT INTO file VALUES ({vals});")
        for row in snapshot["pfm_rows"]:
            sql_lines.append(
                f"INSERT OR IGNORE INTO person_file_map VALUES ({row[0]},{row[1]});"
            )
        for row in snapshot["pfsc_rows"]:
            vals = ",".join(
                "NULL" if v is None else f"'{v}'" if isinstance(v, str) else str(v)
                for v in row
            )
            sql_lines.append(
                f"INSERT OR IGNORE INTO person_file_special_category VALUES ({vals});"
            )
        sql = "\n".join(sql_lines)
        subprocess.run(
            ["sudo", "sqlite3", str(GDPRFS_DB)],
            input=sql, text=True, check=True,
        )

    # 4. Reset consent state in consent DB
    update_consent_db(DS_UID, "marketing", "consented")
    for spCat in SPECIAL_CATS:
        update_special_consent_db(DS_UID, "marketing", spCat, "special_consented")


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
    """Verify preconditions for the given mode."""
    if mode == "baseline":
        return

    if not _is_fuse_mounted():
        raise RuntimeError("FUSE filesystem not mounted at /tmp/mnt")
    if not _is_reachable(CONSENT_PLATFORM_URL):
        raise RuntimeError("External consent platform not reachable (port 5000)")
    if not CONSENT_DB.exists():
        raise RuntimeError(f"Consent DB not found: {CONSENT_DB}")

    # Verify target file exists in upper dir
    result = subprocess.run(
        ["sudo", "test", "-f", str(UPPER_DIR / TARGET_FILE)],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{TARGET_FILE} not found in {UPPER_DIR}")

    if mode == "gdpr_with_llm":
        if not _is_reachable(LLM_ANALYZER_URL):
            raise RuntimeError("LLM analyzer not reachable (port 5005)")
        requests.post(f"{LLM_ANALYZER_URL}/enable", timeout=5)
        print("  [INFO] LLM analyzer enabled for with-LLM benchmark")


# ── Workflow Classes ─────────────────────────────────────────────────────────

class BaselineWorkflow:
    """Mode 1: plain filesystem read/write/rename, no GDPR, no LLM."""

    def run(self) -> dict:
        tmp_dir = tempfile.mkdtemp(prefix="gdprfs_bench_art30_")
        try:
            # Setup: copy jdoe_health.txt to tempdir
            tmp_file = os.path.join(tmp_dir, TARGET_FILE)
            tmp_renamed = os.path.join(tmp_dir, RENAMED_FILE)
            shutil.copy2(str(BACKUP_DIR / TARGET_FILE), tmp_file)

            t0 = time.perf_counter()

            # Step 1: StartSession (no-op)
            t_start_session = 0.0

            # Step 2: Consent (no-op)
            t_consent = 0.0

            # Step 3: Read file
            t3 = time.perf_counter()
            with open(tmp_file, "r") as f:
                content = f.read()
            t_read = time.perf_counter() - t3

            # Step 4-5: Write file (change . to  :() + close
            t4 = time.perf_counter()
            with open(tmp_file, "r+") as f:
                data = f.read()
                f.seek(0)
                f.write(data.replace(".", " :("))
                f.truncate()
            t_write_with_collect = time.perf_counter() - t4

            # Step 6: Rename
            t6 = time.perf_counter()
            os.rename(tmp_file, tmp_renamed)
            t_rename = time.perf_counter() - t6

            # Step 7: Rename back
            t7 = time.perf_counter()
            os.rename(tmp_renamed, tmp_file)
            t_rename_back = time.perf_counter() - t7

            # Step 8: Revoke (no-op)
            t_revoke = 0.0

            # Step 9-10: Read after revoke
            t9 = time.perf_counter()
            with open(tmp_file, "r") as f:
                _ = f.read()
            t_read_after_revoke = time.perf_counter() - t9

            # Step 11: StopSession (no-op)
            t_stop_session = 0.0

            t_total = time.perf_counter() - t0
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return {
            "t_start_session": t_start_session,
            "t_consent": t_consent,
            "t_read": t_read,
            "t_write_with_collect": t_write_with_collect,
            "t_rename": t_rename,
            "t_rename_back": t_rename_back,
            "t_revoke": t_revoke,
            "t_read_after_revoke": t_read_after_revoke,
            "t_stop_session": t_stop_session,
            "t_total": t_total,
        }


class GDPRWorkflow:
    """Mode 2: GDPR FUSE filesystem with LLM."""

    def run(self) -> dict:
        fuse_file = FUSE_MOUNT / TARGET_FILE
        fuse_renamed = FUSE_MOUNT / RENAMED_FILE

        t0 = time.perf_counter()

        # Step 1: StartSession
        t1 = time.perf_counter()
        fuse_ingest("StartSession", uid=CONTROLLER_UID, purpose="marketing",
                     reason="direct_marketing")
        t_start_session = time.perf_counter() - t1

        # Step 2: Consent + SpecialConsent
        t2 = time.perf_counter()
        fuse_ingest("Consent", uid=DS_UID, purpose="marketing")
        update_consent_db(DS_UID, "marketing", "consented")
        for spCat in SPECIAL_CATS:
            fuse_ingest("SpecialConsent", uid=DS_UID, purpose="marketing", spCat=spCat)
            update_special_consent_db(DS_UID, "marketing", spCat, "special_consented")
        t_consent = time.perf_counter() - t2

        # Step 3: Read file via FUSE (triggers Use + SpecialData + processing_records)
        t3 = time.perf_counter()
        with open(fuse_file, "r") as f:
            content = f.read()
        t_read = time.perf_counter() - t3
        assert content != "REDACTED", f"Expected real content, got REDACTED"

        # Step 4-5: Write file via FUSE (triggers Collect + SpecialData + processing_records)
        # Note: FUSE has no truncate(), so avoid "w" mode (O_TRUNC). Use O_WRONLY only.
        t4 = time.perf_counter()
        new_data = content.replace(".", " :(")
        fd = os.open(str(fuse_file), os.O_WRONLY)
        os.write(fd, new_data.encode())
        os.close(fd)
        t_write_with_collect = time.perf_counter() - t4

        # Step 6: Rename via FUSE (triggers Collect + SpecialData + processing_records)
        t6 = time.perf_counter()
        os.rename(fuse_file, fuse_renamed)
        t_rename = time.perf_counter() - t6

        # Step 7: Rename back via FUSE (triggers Collect)
        t7 = time.perf_counter()
        os.rename(fuse_renamed, fuse_file)
        t_rename_back = time.perf_counter() - t7

        # Step 8: Revoke special consent
        t8 = time.perf_counter()
        fuse_ingest("RevokeSpecialConsent", uid=DS_UID, purpose="marketing", spCat="health")
        update_special_consent_db(DS_UID, "marketing", "health", "special_revoked")
        t_revoke = time.perf_counter() - t8

        # Step 9-10: Read after revoke → REDACTED
        t9 = time.perf_counter()
        with open(fuse_file, "r") as f:
            content = f.read()
        t_read_after_revoke = time.perf_counter() - t9
        assert "REDACTED" in content, \
            f"Expected REDACTED after revoke, got: {content[:80]}"

        # Step 11: StopSession
        t11 = time.perf_counter()
        fuse_ingest("StopSession", uid=CONTROLLER_UID)
        t_stop_session = time.perf_counter() - t11

        t_total = time.perf_counter() - t0

        return {
            "t_start_session": t_start_session,
            "t_consent": t_consent,
            "t_read": t_read,
            "t_write_with_collect": t_write_with_collect,
            "t_rename": t_rename,
            "t_rename_back": t_rename_back,
            "t_revoke": t_revoke,
            "t_read_after_revoke": t_read_after_revoke,
            "t_stop_session": t_stop_session,
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
        elif self.mode == "gdpr_with_llm":
            return GDPRWorkflow()
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

    def run(self) -> list:
        preflight_checks(self.mode)

        # Snapshot state for GDPR modes (baseline uses tempdir, no restore needed)
        snapshot = None
        if self.mode != "baseline":
            snapshot = snapshot_state()

        results = []
        try:
            for i in range(self.n):
                print(f"  [{self.mode}] iteration {i + 1}/{self.n} ... ", end="", flush=True)
                if snapshot:
                    cleanup_iteration(snapshot)
                time.sleep(0.5)  # brief settle time
                workflow = self._make_workflow()
                try:
                    timings = workflow.run()
                    timings["iteration"] = i + 1
                    timings["mode"] = self.mode
                    results.append(timings)
                    print(f"total={timings['t_total']:.4f}s")
                except Exception as e:
                    print(f"FAILED: {e}")
                if snapshot:
                    cleanup_iteration(snapshot)
        finally:
            if snapshot:
                cleanup_iteration(snapshot)

        return results


class BenchmarkReporter:
    STEPS = ["t_start_session", "t_consent", "t_read", "t_write_with_collect",
             "t_rename", "t_rename_back", "t_revoke", "t_read_after_revoke",
             "t_stop_session", "t_total"]

    def __init__(self, all_results: dict, output_dir: str):
        self.all_results = all_results
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_csv(self):
        csv_path = self.output_dir / "art30_perf_results.csv"
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
        header = f"  {'Step':<28}" + "".join(f"{m:>{col_w}}" for m in modes)
        print(header)
        print("  " + "-" * (28 + col_w * len(modes)))

        for step in self.STEPS:
            row = f"  {step:<28}"
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
        fig, ax = plt.subplots(figsize=(12, 5))
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
        ax.set_title("Art 30 Records of Processing — Per-Step Latency")
        ax.legend()
        fig.tight_layout()
        fig.savefig(self.output_dir / "art30_per_step.png", dpi=150)
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
        ax.set_title("Art 30 Records of Processing — Total Latency")
        fig.tight_layout()
        fig.savefig(self.output_dir / "art30_total.png", dpi=150)
        plt.close(fig)

        print(f"  Charts saved to {self.output_dir}/")


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Benchmark: Records of Processing Activities workflow (Art 30)")
    p.add_argument(
        "--mode",
        choices=["baseline", "gdpr_with_llm", "all"],
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
        modes = ["baseline", "gdpr_with_llm"]
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
