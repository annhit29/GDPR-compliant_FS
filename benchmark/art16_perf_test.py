"""
Benchmark: Right to Rectification Workflow Performance (Art 16)

Measures wall-clock time of Art 16 workflows for data subject fhublet
(file: fhublet.txt) across 3 modes:
  1. baseline       — plain filesystem, no GDPR, no LLM
  2. gdpr_no_llm    — GDPR FUSE filesystem, no LLM analyzer
  3. gdpr_with_llm  — GDPR FUSE filesystem + LLM analyzer

Workflow 1 (wf1): Write incorrect data, read, rectify, then read rectified
  1.  StartSession("achao", "marketing", "direct_marketing")
  2.  Consent("fhublet", "marketing")
  3.  Write incorrect data "hi\\nhi\\n" to fhublet.txt (Write + Collect)
  4-5. Read fhublet.txt -> "hi\\nhi\\n" (Use) + close
  6.  RequestRectification -> file rectified to "Bonjour\\n"
  7.  Read fhublet.txt -> "Bonjour\\n" (Use) + close
  8.  StopSession("achao")

Workflow 2 (wf2): Incorrect data already present, rectify and read
  1.  StartSession("achao", "marketing", "direct_marketing")
  2.  Consent("fhublet", "marketing")
  3.  RequestRectification -> file rectified to "Bonjour\\n"
      (IsRectificationRequest + HasInaccuracy asserted by enforcer)
  4.  Read fhublet.txt -> "Bonjour\\n" (Use) + close
  5.  StopSession("achao")

Safety: snapshot_state() backs up fhublet.txt, DB rows, and processing_record
max(id) before first iteration; cleanup_iteration() restores everything after each.

Usage (from instrlib/):
  python3 -m benchmark.art16_perf_test --workflow wf1 --mode baseline --n 1
  python3 -m benchmark.art16_perf_test --workflow wf2 --mode gdpr_with_llm --n 1
  python3 -m benchmark.art16_perf_test --workflow all --mode all --n 5
"""

import argparse
import base64
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
UPLOAD_URL = "http://127.0.0.1:7000/upload_rectification"

CONSENT_DB = BASE_DIR / "external_consent_platform" / "instance" / "external_consent_platform.db"
GDPRFS_DB = BASE_DIR / "gdprfs.db"

DS_UID = "fhublet"
CONTROLLER_UID = "achao"
BACKUP_DIR = Path.home() / "Downloads" / "upper_copy_for_benchmark"
TARGET_FILE = "fhublet.txt"
EDITED_FILENAME = "fhublet_edited.txt"

ORIGINAL_CONTENT = b"hi\nhi\n"      # incorrect data written in step 3
RECTIFIED_CONTENT = b"Bonjour\n"    # corrected data after rectification


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


def upload_rectification_file(filename: str, content: bytes) -> str:
    """Upload an edited file to the rectification staging endpoint. Returns fid_new."""
    payload = {
        "filename": filename,
        "content_b64": base64.b64encode(content).decode("ascii"),
    }
    resp = requests.post(UPLOAD_URL, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    assert data.get("ok"), f"upload_rectification failed: {data}"
    return data["fid_new"]


def wait_for_rectification(timeout: float = 15.0, poll_interval: float = 0.3):
    """Poll until fhublet.txt content changes to rectified content."""
    deadline = time.monotonic() + timeout
    target_path = UPPER_DIR / TARGET_FILE
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["sudo", "cat", str(target_path)],
            capture_output=True,
        )
        if RECTIFIED_CONTENT.strip() in result.stdout.strip():
            return
        time.sleep(poll_interval)
    raise TimeoutError(
        f"Rectification did not complete within {timeout}s. "
        f"Check rectify_causation_handler logs."
    )


# ── Snapshot & Restore ───────────────────────────────────────────────────────

def snapshot_state() -> dict:
    """Back up fhublet.txt and its DB rows before the benchmark starts."""
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

    print(f"  [SNAPSHOT] Backed up {TARGET_FILE} -> {backup_path}")
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

    # 2. Clean rectification staging leftovers
    subprocess.run(
        ["sudo", "bash", "-c", f"rm -f {UPPER_DIR / '_rectify_staging'}/*"],
        check=False, capture_output=True,
    )

    # 3. Clean up gdprfs.db (root-owned, use sudo sqlite3)
    max_pr_id = snapshot["max_pr_id"]
    sql = f"DELETE FROM processing_record WHERE id > {max_pr_id};"
    subprocess.run(
        ["sudo", "sqlite3", str(GDPRFS_DB)],
        input=sql, text=True, check=False, capture_output=True,
    )

    # 4. Verify file row still exists (rectification preserves it, but just in case)
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

    # 5. Reset consent state in consent DB
    update_consent_db(DS_UID, "marketing", "consented")


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

# ---------- Workflow 1: Write + Read + Rectify + Read ----------

class BaselineWorkflow1:
    """WF1 Baseline: plain filesystem write/read/overwrite, no GDPR, no LLM."""

    def run(self) -> dict:
        tmp_dir = tempfile.mkdtemp(prefix="gdprfs_bench_art16_")
        try:
            tmp_file = os.path.join(tmp_dir, TARGET_FILE)

            t0 = time.perf_counter()

            # Step 1: StartSession (no-op)
            t_start_session = 0.0

            # Step 2: Consent (no-op)
            t_consent = 0.0

            # Step 3: Write incorrect data
            t3 = time.perf_counter()
            with open(tmp_file, "wb") as f:
                f.write(ORIGINAL_CONTENT)
            t_write = time.perf_counter() - t3

            # Step 4-5: Read before rectification
            t4 = time.perf_counter()
            with open(tmp_file, "rb") as f:
                content = f.read()
            t_read_before = time.perf_counter() - t4
            assert content == ORIGINAL_CONTENT

            # Step 6: Rectification (just overwrite)
            t6 = time.perf_counter()
            with open(tmp_file, "wb") as f:
                f.write(RECTIFIED_CONTENT)
            t_rectification = time.perf_counter() - t6

            # Step 7: Read after rectification
            t7 = time.perf_counter()
            with open(tmp_file, "rb") as f:
                content = f.read()
            t_read_after = time.perf_counter() - t7
            assert content == RECTIFIED_CONTENT

            # Step 8: StopSession (no-op)
            t_stop_session = 0.0

            t_total = time.perf_counter() - t0
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return {
            "t_start_session": t_start_session,
            "t_consent": t_consent,
            "t_write": t_write,
            "t_read_before": t_read_before,
            "t_rectification": t_rectification,
            "t_read_after": t_read_after,
            "t_stop_session": t_stop_session,
            "t_total": t_total,
        }


class GDPRWorkflow1:
    """WF1 GDPR: FUSE write + read + rectification + read, optionally with LLM."""

    def __init__(self, with_llm: bool):
        self.with_llm = with_llm

    def run(self) -> dict:
        fuse_file = FUSE_MOUNT / TARGET_FILE

        t0 = time.perf_counter()

        # Step 1: StartSession
        t1 = time.perf_counter()
        fuse_ingest("StartSession", uid=CONTROLLER_UID, purpose="marketing",
                     reason="direct_marketing")
        t_start_session = time.perf_counter() - t1

        # Step 2: Consent
        t2 = time.perf_counter()
        fuse_ingest("Consent", uid=DS_UID, purpose="marketing")
        update_consent_db(DS_UID, "marketing", "consented")
        t_consent = time.perf_counter() - t2

        # Step 3: Write incorrect data via FUSE
        # FUSE doesn't implement truncate() — use O_WRONLY
        t3 = time.perf_counter()
        fd = os.open(str(fuse_file), os.O_WRONLY)
        os.write(fd, ORIGINAL_CONTENT)
        os.close(fd)
        t_write = time.perf_counter() - t3

        # Step 4-5: Read before rectification via FUSE
        t4 = time.perf_counter()
        with open(fuse_file, "rb") as f:
            content = f.read()
        t_read_before = time.perf_counter() - t4
        assert ORIGINAL_CONTENT.strip() in content.strip(), \
            f"Expected {ORIGINAL_CONTENT!r} in file, got: {content!r}"

        # Step 6: Rectification (upload + request + wait)
        t6 = time.perf_counter()
        fid_new = upload_rectification_file(EDITED_FILENAME, RECTIFIED_CONTENT)
        fuse_ingest("RequestRectification", uid=DS_UID,
                     fid_old=TARGET_FILE, fid_new=fid_new)
        wait_for_rectification()
        t_rectification = time.perf_counter() - t6

        # Step 7: Read after rectification via FUSE
        t7 = time.perf_counter()
        with open(fuse_file, "rb") as f:
            content = f.read()
        t_read_after = time.perf_counter() - t7
        assert RECTIFIED_CONTENT.strip() in content.strip(), \
            f"Expected {RECTIFIED_CONTENT!r} after rectification, got: {content!r}"

        # Step 8: StopSession
        t8 = time.perf_counter()
        fuse_ingest("StopSession", uid=CONTROLLER_UID)
        t_stop_session = time.perf_counter() - t8

        t_total = time.perf_counter() - t0

        return {
            "t_start_session": t_start_session,
            "t_consent": t_consent,
            "t_write": t_write,
            "t_read_before": t_read_before,
            "t_rectification": t_rectification,
            "t_read_after": t_read_after,
            "t_stop_session": t_stop_session,
            "t_total": t_total,
        }


# ---------- Workflow 2: Rectify (data already incorrect) + Read ----------

class BaselineWorkflow2:
    """WF2 Baseline: file already has incorrect data, overwrite + read."""

    def run(self) -> dict:
        tmp_dir = tempfile.mkdtemp(prefix="gdprfs_bench_art16_wf2_")
        try:
            tmp_file = os.path.join(tmp_dir, TARGET_FILE)

            # Setup (untimed): write incorrect data so file exists
            with open(tmp_file, "wb") as f:
                f.write(ORIGINAL_CONTENT)

            t0 = time.perf_counter()

            # Step 1: StartSession (no-op)
            t_start_session = 0.0

            # Step 2: Consent (no-op)
            t_consent = 0.0

            # Step 3: Rectification (plain file overwrite)
            t3 = time.perf_counter()
            with open(tmp_file, "wb") as f:
                f.write(RECTIFIED_CONTENT)
            t_rectification = time.perf_counter() - t3

            # Step 4: Read rectified content
            t4 = time.perf_counter()
            with open(tmp_file, "rb") as f:
                content = f.read()
            t_read = time.perf_counter() - t4
            assert content == RECTIFIED_CONTENT

            # Step 5: StopSession (no-op)
            t_stop_session = 0.0

            t_total = time.perf_counter() - t0
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return {
            "t_start_session": t_start_session,
            "t_consent": t_consent,
            "t_rectification": t_rectification,
            "t_read": t_read,
            "t_stop_session": t_stop_session,
            "t_total": t_total,
        }


class GDPRWorkflow2:
    """WF2 GDPR: file already has incorrect data, rectify via FUSE + read."""

    def __init__(self, with_llm: bool):
        self.with_llm = with_llm

    def run(self) -> dict:
        fuse_file = FUSE_MOUNT / TARGET_FILE

        t0 = time.perf_counter()

        # Step 1: StartSession
        t1 = time.perf_counter()
        fuse_ingest("StartSession", uid=CONTROLLER_UID, purpose="marketing",
                     reason="direct_marketing")
        t_start_session = time.perf_counter() - t1

        # Step 2: Consent
        t2 = time.perf_counter()
        fuse_ingest("Consent", uid=DS_UID, purpose="marketing")
        update_consent_db(DS_UID, "marketing", "consented")
        t_consent = time.perf_counter() - t2

        # Step 3: Rectification (upload + RequestRectification + wait)
        # Enforcer refines into: IsRectificationRequest + HasInaccuracy
        # Then causes Rectify(fid_old, fid_new) via rectify_causation_handler
        t3 = time.perf_counter()
        fid_new = upload_rectification_file(EDITED_FILENAME, RECTIFIED_CONTENT)
        fuse_ingest("RequestRectification", uid=DS_UID,
                     fid_old=TARGET_FILE, fid_new=fid_new)
        wait_for_rectification()
        t_rectification = time.perf_counter() - t3

        # Step 4: Read rectified content via FUSE (Use event logged)
        t4 = time.perf_counter()
        with open(fuse_file, "rb") as f:
            content = f.read()
        t_read = time.perf_counter() - t4
        assert RECTIFIED_CONTENT.strip() in content.strip(), \
            f"Expected {RECTIFIED_CONTENT!r} after rectification, got: {content!r}"

        # Step 5: StopSession
        t5 = time.perf_counter()
        fuse_ingest("StopSession", uid=CONTROLLER_UID)
        t_stop_session = time.perf_counter() - t5

        t_total = time.perf_counter() - t0

        return {
            "t_start_session": t_start_session,
            "t_consent": t_consent,
            "t_rectification": t_rectification,
            "t_read": t_read,
            "t_stop_session": t_stop_session,
            "t_total": t_total,
        }


# ── Runner & Reporter ────────────────────────────────────────────────────────

WF_TITLES = {
    "wf1": "Write + Rectify + Read",
    "wf2": "Rectify Pre-existing Data + Read",
}

WF_STEPS = {
    "wf1": ["t_start_session", "t_consent", "t_write", "t_read_before",
             "t_rectification", "t_read_after", "t_stop_session", "t_total"],
    "wf2": ["t_start_session", "t_consent", "t_rectification", "t_read",
             "t_stop_session", "t_total"],
}


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
                return GDPRWorkflow1(with_llm=False)
            elif self.mode == "gdpr_with_llm":
                return GDPRWorkflow1(with_llm=True)

        elif self.workflow == "wf2":
            if self.mode == "baseline":
                return BaselineWorkflow2()
            elif self.mode == "gdpr_no_llm":
                return GDPRWorkflow2(with_llm=False)
            elif self.mode == "gdpr_with_llm":
                return GDPRWorkflow2(with_llm=True)

        raise ValueError(f"Unknown workflow/mode: {self.workflow}/{self.mode}")

    def run(self) -> list:
        preflight_checks(self.mode)

        # Snapshot state for GDPR modes (baseline uses tempdir, no restore needed)
        snapshot = None
        if self.mode != "baseline":
            snapshot = snapshot_state()

        results = []
        try:
            for i in range(self.n):
                print(f"  [{self.workflow} | {self.mode}] iteration {i + 1}/{self.n} ... ",
                      end="", flush=True)
                if snapshot:
                    cleanup_iteration(snapshot)
                time.sleep(0.5)  # brief settle time
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
                if snapshot:
                    cleanup_iteration(snapshot)
        finally:
            if snapshot:
                cleanup_iteration(snapshot)

        return results


class BenchmarkReporter:
    def __init__(self, workflow: str, all_results: dict, output_dir: str):
        self.workflow = workflow
        self.steps = WF_STEPS[workflow]
        self.all_results = all_results  # mode -> list of timing dicts
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_csv(self):
        csv_path = self.output_dir / f"art16_{self.workflow}_perf_results.csv"
        fieldnames = ["mode", "iteration"] + self.steps
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
        print("  Mean +/- Std latency per step (seconds)")
        print(f"{'=' * 70}")
        header = f"  {'Step':<28}" + "".join(f"{m:>{col_w}}" for m in modes)
        print(header)
        print("  " + "-" * (28 + col_w * len(modes)))

        for step in self.steps:
            row = f"  {step:<28}"
            for mode in modes:
                vals = [r[step] for r in self.all_results[mode]]
                mean = statistics.mean(vals)
                std = statistics.stdev(vals) if len(vals) > 1 else 0.0
                row += f"{mean:>{col_w - 8}.4f}+/-{std:<5.4f}"
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
        steps_no_total = [s for s in self.steps if s != "t_total"]
        wf_title = WF_TITLES.get(self.workflow, self.workflow)

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
        ax.set_title(f"Art 16 ({wf_title}) — Per-Step Latency")
        ax.legend()
        fig.tight_layout()
        fig.savefig(self.output_dir / f"art16_{self.workflow}_per_step.png", dpi=150)
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
        ax.set_title(f"Art 16 ({wf_title}) — Total Latency")
        fig.tight_layout()
        fig.savefig(self.output_dir / f"art16_{self.workflow}_total.png", dpi=150)
        plt.close(fig)

        print(f"  Charts saved to {self.output_dir}/")


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Benchmark: Right to Rectification workflow (Art 16)")
    p.add_argument(
        "--workflow",
        choices=["wf1", "wf2", "all"],
        default="all",
        help="Which Art. 16 workflow(s) to benchmark (default: all)",
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
