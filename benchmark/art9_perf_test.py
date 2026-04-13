"""
Benchmark: Special Data Consent Workflow Performance (Art 9)

Measures wall-clock time of the Art 9 workflow (TXT files, multiple DSs,
SpecialConsent / RevokeSpecialConsent) across 3 modes:
  1. baseline       — plain filesystem, no GDPR, no LLM
  2. gdpr_no_llm    — GDPR FUSE filesystem, no LLM analyzer
  3. gdpr_with_llm  — GDPR FUSE filesystem + LLM analyzer

Usage (from instrlib/):
  python -m benchmark.art9_perf_test --mode all --n 5
  python -m benchmark.art9_perf_test --mode gdpr_with_llm --n 1
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

import requests

# -- Constants ----------------------------------------------------------------
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

FILE1 = "jdoe&whsieh_genetic.txt"
FILE2 = "jdoe&whsieh&fhublet_spCat246.txt"

TEXT_CONTENT_1 = (
    "John Doe's DNA shows this person is a boy.\n"
    "Wei-En Hsieh's DNA shows this person is a girl.\n"
)

TEXT_CONTENT_2 = (
    "John Doe's DNA shows this person is a boy. His fingerprints were used for authentication.\n"
    "Wei-En Hsieh's DNA shows this person is a girl. She's Taiwanese :D\n"
    "\n"
    "John Doe has diabetes.\n"
)

TEXT_CONTENT_3 = (
    "John Doe's DNA shows this person is a boy. His fingerprints was used for authentication.\n"
    "Wei-En Hsieh's DNA shows this person is a girl. She's Taiwanese :D\n"
    "\n"
    "François Hublet is French.\n"
    "\n"
    "John Doe has diabetes\n"
)

TEXT_CONTENT_3_MODIFIED = TEXT_CONTENT_3.rstrip("\n") + " :D\n"


# -- Helper Functions ---------------------------------------------------------

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
    """Directly upsert special consent state in the external consent platform DB."""
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
    # 1. Remove test TXT files from FUSE mount and storage dirs
    for fname in (FILE1, FILE2):
        for d in (UPPER_DIR, MIRROR_DIR, FUSE_MOUNT):
            subprocess.run(["sudo", "rm", "-f", str(d / fname)],
                           check=False, capture_output=True)
        for d in (UPPER_DIR, MIRROR_DIR, FUSE_MOUNT):
            subprocess.run(["sudo", "rm", "-f", str(d / ".goutputstream-bench")],
                           check=False, capture_output=True)

    # 2. Clean gdprfs.db entries for test files
    if GDPRFS_DB.exists():
        conn = sqlite3.connect(str(GDPRFS_DB))
        cur = conn.cursor()
        for fname in (FILE1, FILE2):
            row = cur.execute(
                "SELECT id FROM file WHERE file_id=?", (fname,)
            ).fetchone()
            if row:
                fid = row[0]
                cur.execute("DELETE FROM person_file_map WHERE file_id=?", (fid,))
                cur.execute(
                    "DELETE FROM person_file_special_category WHERE file_id=?", (fid,)
                )
                cur.execute("DELETE FROM file WHERE id=?", (fid,))
        cur.execute("DELETE FROM person WHERE registered=0")
        conn.commit()
        conn.close()

    # 3. Clean consent DB: remove special consent + regular consent for test DSs
    if CONSENT_DB.exists():
        conn = sqlite3.connect(str(CONSENT_DB))
        cur = conn.cursor()
        for uid in ("jdoe", "whsieh", "fhublet"):
            cur.execute(
                "DELETE FROM current_event_state "
                "WHERE uid=? AND category='special_consent'",
                (uid,),
            )
        for uid in ("jdoe", "whsieh"):
            cur.execute(
                "DELETE FROM current_event_state "
                "WHERE uid=? AND category='consent'",
                (uid,),
            )
        cur.execute(
            "DELETE FROM current_event_state "
            "WHERE uid='fhublet' AND category='consent' AND purpose='marketing'",
        )
        conn.commit()
        conn.close()

    # 4. Remove merge alerts file
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


def _write_via_temp_rename(target: Path, content: bytes):
    """Write content using the editor temp+rename pattern to trigger Write+Collect events."""
    tmp_name = target.parent / ".goutputstream-bench"
    tmp_name.write_bytes(content)
    if target.exists():
        os.unlink(str(target))
    os.rename(str(tmp_name), str(target))


# -- Workflow Classes ---------------------------------------------------------

class BaselineWorkflow:
    """Mode 1: plain filesystem, no GDPR, no LLM."""

    def run(self) -> dict:
        tmp_dir = tempfile.mkdtemp(prefix="gdprfs_art9_bench_")
        try:
            t0 = time.perf_counter()

            # Step 1: StartSession (no-op)
            t_start_session = 0.0

            # Step 2: Create empty file
            f1 = os.path.join(tmp_dir, FILE1)
            t2 = time.perf_counter()
            open(f1, "w").close()
            t_create = time.perf_counter() - t2

            # Step 3: Read (no enforcement in baseline)
            t3 = time.perf_counter()
            with open(f1, "rb") as f:
                f.read()
            t_use_no_consent = time.perf_counter() - t3

            # Steps 4-5: Consent jdoe + read (no-op for consent)
            t_consent_jdoe = 0.0
            t_use_partial_consent = 0.0

            # Step 6: Consent whsieh (no-op)
            t_consent_whsieh = 0.0

            # Step 7: Read (empty file)
            t7 = time.perf_counter()
            with open(f1, "rb") as f:
                f.read()
            t_use_both_consent = time.perf_counter() - t7

            # Step 8: Write TEXT_CONTENT_1
            t8 = time.perf_counter()
            with open(f1, "w") as f:
                f.write(TEXT_CONTENT_1)
            t_write1 = time.perf_counter() - t8

            # Step 10: Read
            t10 = time.perf_counter()
            with open(f1, "rb") as f:
                f.read()
            t_use_no_spconsent = time.perf_counter() - t10

            # Steps 11-12: SpecialConsent jdoe + read (no-op)
            t_spconsent_jdoe_genetic = 0.0
            t_use_partial_spconsent = 0.0

            # Step 13: SpecialConsent whsieh (no-op)
            t_spconsent_whsieh_genetic = 0.0

            # Step 14: Read
            t14 = time.perf_counter()
            with open(f1, "rb") as f:
                f.read()
            t_use_full_spconsent = time.perf_counter() - t14

            # Step 15: Write TEXT_CONTENT_2
            t15 = time.perf_counter()
            with open(f1, "w") as f:
                f.write(TEXT_CONTENT_2)
            t_write2 = time.perf_counter() - t15

            # Step 17: Read
            t17 = time.perf_counter()
            with open(f1, "rb") as f:
                f.read()
            t_use_missing_new_spcats = time.perf_counter() - t17

            # Step 18: SpecialConsent jdoe bio+health (no-op)
            t_spconsent_jdoe_bio_health = 0.0

            # Step 19: Read
            t19 = time.perf_counter()
            with open(f1, "rb") as f:
                f.read()
            t_use_whsieh_missing = time.perf_counter() - t19

            # Step 20: SpecialConsent whsieh racial (no-op)
            t_spconsent_whsieh_racial = 0.0

            # Step 21: Read
            t21 = time.perf_counter()
            with open(f1, "rb") as f:
                f.read()
            t_use_all_spcats = time.perf_counter() - t21

            # Step 22: Rename
            f2 = os.path.join(tmp_dir, FILE2)
            t22 = time.perf_counter()
            os.rename(f1, f2)
            t_rename = time.perf_counter() - t22

            # Step 23: Read renamed file
            t23 = time.perf_counter()
            with open(f2, "rb") as f:
                f.read()
            t_use_fhublet_no_consent_after_rename = time.perf_counter() - t23

            # Steps 24-25: Consent fhublet (no-op)
            t_consent_fhublet = 0.0
            t_spconsent_fhublet_racial = 0.0

            # Step 26: Read renamed file
            t26 = time.perf_counter()
            with open(f2, "rb") as f:
                f.read()
            t_use_fhublet_consent_and_spconsent = time.perf_counter() - t26

            # Step 28: Write TEXT_CONTENT_3
            t28 = time.perf_counter()
            with open(f2, "w") as f:
                f.write(TEXT_CONTENT_3)
            t_write3 = time.perf_counter() - t28

            # Step 29: Read
            t29 = time.perf_counter()
            with open(f2, "rb") as f:
                f.read()
            t_use_fhublet_consented = time.perf_counter() - t29

            # Step 30: Write TEXT_CONTENT_3_MODIFIED
            t30 = time.perf_counter()
            with open(f2, "w") as f:
                f.write(TEXT_CONTENT_3_MODIFIED)
            t_write4 = time.perf_counter() - t30

            # Steps 32-34: Revoke/Reconsent (no-op)
            t_revoke_sp_whsieh = 0.0
            t_use_after_sp_revoke = 0.0
            t_reconsent_sp_whsieh = 0.0

            # Step 35: Read
            t35 = time.perf_counter()
            with open(f2, "rb") as f:
                f.read()
            t_use_after_sp_reconsent = time.perf_counter() - t35

            # Step 36: StopSession (no-op)
            t_stop_session = 0.0

            t_total = time.perf_counter() - t0
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return {
            "t_start_session": t_start_session,
            "t_create": t_create,
            "t_use_no_consent": t_use_no_consent,
            "t_consent_jdoe": t_consent_jdoe,
            "t_use_partial_consent": t_use_partial_consent,
            "t_consent_whsieh": t_consent_whsieh,
            "t_use_both_consent": t_use_both_consent,
            "t_write1": t_write1,
            "t_use_no_spconsent": t_use_no_spconsent,
            "t_spconsent_jdoe_genetic": t_spconsent_jdoe_genetic,
            "t_use_partial_spconsent": t_use_partial_spconsent,
            "t_spconsent_whsieh_genetic": t_spconsent_whsieh_genetic,
            "t_use_full_spconsent": t_use_full_spconsent,
            "t_write2": t_write2,
            "t_use_missing_new_spcats": t_use_missing_new_spcats,
            "t_spconsent_jdoe_bio_health": t_spconsent_jdoe_bio_health,
            "t_use_whsieh_missing": t_use_whsieh_missing,
            "t_spconsent_whsieh_racial": t_spconsent_whsieh_racial,
            "t_use_all_spcats": t_use_all_spcats,
            "t_rename": t_rename,
            "t_use_fhublet_no_consent_after_rename": t_use_fhublet_no_consent_after_rename,
            "t_consent_fhublet": t_consent_fhublet,
            "t_spconsent_fhublet_racial": t_spconsent_fhublet_racial,
            "t_use_fhublet_consent_and_spconsent": t_use_fhublet_consent_and_spconsent,
            "t_write3": t_write3,
            "t_use_fhublet_consented": t_use_fhublet_consented,
            "t_write4": t_write4,
            "t_revoke_sp_whsieh": t_revoke_sp_whsieh,
            "t_use_after_sp_revoke": t_use_after_sp_revoke,
            "t_reconsent_sp_whsieh": t_reconsent_sp_whsieh,
            "t_use_after_sp_reconsent": t_use_after_sp_reconsent,
            "t_stop_session": t_stop_session,
            "t_total": t_total,
        }


class GDPRWorkflow:
    """Mode 2/3: GDPR FUSE filesystem, optionally with LLM."""

    def __init__(self, with_llm: bool):
        self.with_llm = with_llm

    def run(self) -> dict:
        t0 = time.perf_counter()

        # Step 1: StartSession
        t1 = time.perf_counter()
        fuse_ingest("StartSession", uid="achao", purpose="marketing",
                     reason="direct_marketing")
        t_start_session = time.perf_counter() - t1

        # Step 2: Create empty FILE1 (lazy DB links jdoe & whsieh by filename)
        f1 = FUSE_MOUNT / FILE1
        t2 = time.perf_counter()
        open(f1, "w").close()
        t_create = time.perf_counter() - t2

        # Step 3: Read — no consent from jdoe or whsieh → REDACTED
        t3 = time.perf_counter()
        with open(f1, "rb") as f:
            content = f.read()
        t_use_no_consent = time.perf_counter() - t3
        assert content == b"REDACTED", (
            f"Step 3: expected REDACTED, got {content[:50]!r}"
        )

        # Step 4: jdoe Consent
        t4 = time.perf_counter()
        fuse_ingest("Consent", uid="jdoe", purpose="marketing")
        update_consent_db("jdoe", "marketing", "consented")
        t_consent_jdoe = time.perf_counter() - t4

        # Step 5: Read — whsieh still no consent → REDACTED
        t5 = time.perf_counter()
        with open(f1, "rb") as f:
            content = f.read()
        t_use_partial_consent = time.perf_counter() - t5
        assert content == b"REDACTED", (
            f"Step 5: expected REDACTED, got {content[:50]!r}"
        )

        # Step 6: whsieh Consent
        t6 = time.perf_counter()
        fuse_ingest("Consent", uid="whsieh", purpose="marketing")
        update_consent_db("whsieh", "marketing", "consented")
        t_consent_whsieh = time.perf_counter() - t6

        # Step 7: Read — both consented, file is empty → b""
        t7 = time.perf_counter()
        with open(f1, "rb") as f:
            content = f.read()
        t_use_both_consent = time.perf_counter() - t7
        print(f"\n        [Step 7] Content after both consent: {content!r}")

        # Step 8: Write TEXT_CONTENT_1 via temp+rename (triggers Write+Collect+LLM)
        t8 = time.perf_counter()
        _write_via_temp_rename(f1, TEXT_CONTENT_1.encode())
        if self.with_llm:
            time.sleep(2)  # give LLM time to analyze and update DB
        t_write1 = time.perf_counter() - t8

        # Step 10: Read — no SpecialConsent for genetic → REDACTED
        if self.with_llm:
            t10 = time.perf_counter()
            with open(f1, "rb") as f:
                content = f.read()
            t_use_no_spconsent = time.perf_counter() - t10
            assert content == b"REDACTED", (
                f"Step 10: expected REDACTED (no genetic SpecialConsent), got {content[:50]!r}"
            )
        else:
            # Without LLM, spCat not in DB → no special consent check → not REDACTED
            t10 = time.perf_counter()
            with open(f1, "rb") as f:
                content = f.read()
            t_use_no_spconsent = time.perf_counter() - t10
            print(f"        [Step 10 no-LLM] Content: {content[:80]!r}")

        # Step 11: jdoe SpecialConsent genetic
        t11 = time.perf_counter()
        fuse_ingest("SpecialConsent", uid="jdoe", purpose="marketing", spCat="genetic")
        update_special_consent_db("jdoe", "marketing", "genetic", "special_consented")
        t_spconsent_jdoe_genetic = time.perf_counter() - t11

        # Step 12: Read — whsieh lacks genetic SpecialConsent → REDACTED
        if self.with_llm:
            t12 = time.perf_counter()
            with open(f1, "rb") as f:
                content = f.read()
            t_use_partial_spconsent = time.perf_counter() - t12
            assert content == b"REDACTED", (
                f"Step 12: expected REDACTED (whsieh no genetic), got {content[:50]!r}"
            )
        else:
            t12 = time.perf_counter()
            with open(f1, "rb") as f:
                content = f.read()
            t_use_partial_spconsent = time.perf_counter() - t12
            print(f"        [Step 12 no-LLM] Content: {content[:80]!r}")

        # Step 13: whsieh SpecialConsent genetic
        t13 = time.perf_counter()
        fuse_ingest("SpecialConsent", uid="whsieh", purpose="marketing", spCat="genetic")
        update_special_consent_db("whsieh", "marketing", "genetic", "special_consented")
        t_spconsent_whsieh_genetic = time.perf_counter() - t13

        # Step 14: Read — all SpecialConsent granted → real content
        t14 = time.perf_counter()
        with open(f1, "rb") as f:
            content = f.read()
        t_use_full_spconsent = time.perf_counter() - t14
        if self.with_llm:
            assert content == TEXT_CONTENT_1.encode(), (
                f"Step 14: expected TEXT_CONTENT_1, got {content[:80]!r}"
            )
        print(f"        [Step 14] Content: {content[:80]!r}")

        # Step 15: Write TEXT_CONTENT_2 via temp+rename (LLM detects 4 spCats)
        t15 = time.perf_counter()
        _write_via_temp_rename(f1, TEXT_CONTENT_2.encode())
        if self.with_llm:
            time.sleep(2)
        t_write2 = time.perf_counter() - t15

        # Step 17: Read — jdoe lacks health+biometric; whsieh lacks racial_ethnic → REDACTED
        if self.with_llm:
            t17 = time.perf_counter()
            with open(f1, "rb") as f:
                content = f.read()
            t_use_missing_new_spcats = time.perf_counter() - t17
            assert content == b"REDACTED", (
                f"Step 17: expected REDACTED (missing new spCats), got {content[:50]!r}"
            )
        else:
            t17 = time.perf_counter()
            with open(f1, "rb") as f:
                content = f.read()
            t_use_missing_new_spcats = time.perf_counter() - t17
            print(f"        [Step 17 no-LLM] Content: {content[:80]!r}")

        # Step 18: jdoe SpecialConsent biometric + health
        t18 = time.perf_counter()
        fuse_ingest("SpecialConsent", uid="jdoe", purpose="marketing", spCat="biometric")
        update_special_consent_db("jdoe", "marketing", "biometric", "special_consented")
        fuse_ingest("SpecialConsent", uid="jdoe", purpose="marketing", spCat="health")
        update_special_consent_db("jdoe", "marketing", "health", "special_consented")
        t_spconsent_jdoe_bio_health = time.perf_counter() - t18

        # Step 19: Read — whsieh lacks racial_ethnic → REDACTED
        if self.with_llm:
            t19 = time.perf_counter()
            with open(f1, "rb") as f:
                content = f.read()
            t_use_whsieh_missing = time.perf_counter() - t19
            assert content == b"REDACTED", (
                f"Step 19: expected REDACTED (whsieh no racial_ethnic), got {content[:50]!r}"
            )
        else:
            t19 = time.perf_counter()
            with open(f1, "rb") as f:
                content = f.read()
            t_use_whsieh_missing = time.perf_counter() - t19
            print(f"        [Step 19 no-LLM] Content: {content[:80]!r}")

        # Step 20: whsieh SpecialConsent racial_ethnic
        t20 = time.perf_counter()
        fuse_ingest("SpecialConsent", uid="whsieh", purpose="marketing", spCat="racial_ethnic")
        update_special_consent_db("whsieh", "marketing", "racial_ethnic", "special_consented")
        t_spconsent_whsieh_racial = time.perf_counter() - t20

        # Step 21: Read — all spCats consented → real content
        t21 = time.perf_counter()
        with open(f1, "rb") as f:
            content = f.read()
        t_use_all_spcats = time.perf_counter() - t21
        if self.with_llm:
            assert content == TEXT_CONTENT_2.encode(), (
                f"Step 21: expected TEXT_CONTENT_2, got {content[:80]!r}"
            )
        print(f"        [Step 21] Content: {content[:80]!r}")

        # Step 22: Rename FILE1 → FILE2 (adds fhublet by filename)
        f2 = FUSE_MOUNT / FILE2
        t22 = time.perf_counter()
        os.rename(str(f1), str(f2))
        t_rename = time.perf_counter() - t22

        # Step 23: Read — fhublet lacks consent + racial_ethnic spConsent → REDACTED
        t23 = time.perf_counter()
        with open(f2, "rb") as f:
            content = f.read()
        t_use_fhublet_no_consent_after_rename = time.perf_counter() - t23
        assert content == b"REDACTED", (
            f"Step 23: expected REDACTED (fhublet no consent), got {content[:50]!r}"
        )

        # Step 25: fhublet Consent
        t25 = time.perf_counter()
        fuse_ingest("Consent", uid="fhublet", purpose="marketing")
        update_consent_db("fhublet", "marketing", "consented")
        t_consent_fhublet = time.perf_counter() - t25

        # Step 26: fhublet SpecialConsent racial_ethnic
        t26 = time.perf_counter()
        fuse_ingest("SpecialConsent", uid="fhublet", purpose="marketing", spCat="racial_ethnic")
        update_special_consent_db("fhublet", "marketing", "racial_ethnic", "special_consented")
        t_spconsent_fhublet_racial = time.perf_counter() - t26

        # Step 27: Read renamed file — Use+SpecialData logged
        t27 = time.perf_counter()
        with open(f2, "rb") as f:
            content = f.read()
        t_use_fhublet_consent_and_spconsent = time.perf_counter() - t27
        print(f"        [Step 27] Content after rename: {content[:80]!r}") 

        # Step 28: Write TEXT_CONTENT_3 via temp+rename (LLM detects fhublet+racial_ethnic)
        t28 = time.perf_counter()
        _write_via_temp_rename(f2, TEXT_CONTENT_3.encode())
        if self.with_llm:
            time.sleep(2)
        t_write3 = time.perf_counter() - t28

        # Step 30: Read — all consented → real content
        t30 = time.perf_counter()
        with open(f2, "rb") as f:
            content = f.read()
        t_use_fhublet_consented = time.perf_counter() - t30
        if self.with_llm:
            assert content == TEXT_CONTENT_3.encode(), (
                f"Step 30: expected TEXT_CONTENT_3, got {content[:80]!r}"
            )
        print(f"        [Step 30] Content: {content[:80]!r}")

        # Step 31: Write TEXT_CONTENT_3_MODIFIED (add ":D")
        t31 = time.perf_counter()
        _write_via_temp_rename(f2, TEXT_CONTENT_3_MODIFIED.encode())
        if self.with_llm:
            time.sleep(2)
        t_write4 = time.perf_counter() - t31

        # Step 33: whsieh RevokeSpecialConsent genetic
        t33 = time.perf_counter()
        fuse_ingest("RevokeSpecialConsent", uid="whsieh", purpose="marketing", spCat="genetic")
        update_special_consent_db("whsieh", "marketing", "genetic", "special_revoked")
        t_revoke_sp_whsieh = time.perf_counter() - t33

        # Step 34: Read — whsieh lacks genetic → REDACTED
        t34 = time.perf_counter()
        with open(f2, "rb") as f:
            content = f.read()
        t_use_after_sp_revoke = time.perf_counter() - t34
        assert content == b"REDACTED", (
            f"Step 34: expected REDACTED (whsieh genetic revoked), got {content[:50]!r}"
        )

        # Step 35: whsieh SpecialConsent genetic (re-consent)
        t35 = time.perf_counter()
        fuse_ingest("SpecialConsent", uid="whsieh", purpose="marketing", spCat="genetic")
        update_special_consent_db("whsieh", "marketing", "genetic", "special_consented")
        t_reconsent_sp_whsieh = time.perf_counter() - t35

        # Step 36: Read — all consented again → real content
        t36 = time.perf_counter()
        with open(f2, "rb") as f:
            content = f.read()
        t_use_after_sp_reconsent = time.perf_counter() - t36
        if self.with_llm:
            assert content == TEXT_CONTENT_3_MODIFIED.encode(), (
                f"Step 36: expected TEXT_CONTENT_3_MODIFIED, got {content[:80]!r}"
            )
        print(f"        [Step 36] Content: {content[:80]!r}")

        # Step 37: StopSession
        t37 = time.perf_counter()
        fuse_ingest("StopSession", uid="achao")
        t_stop_session = time.perf_counter() - t37

        t_total = time.perf_counter() - t0

        return {
            "t_start_session": t_start_session,
            "t_create": t_create,
            "t_use_no_consent": t_use_no_consent,
            "t_consent_jdoe": t_consent_jdoe,
            "t_use_partial_consent": t_use_partial_consent,
            "t_consent_whsieh": t_consent_whsieh,
            "t_use_both_consent": t_use_both_consent,
            "t_write1": t_write1,
            "t_use_no_spconsent": t_use_no_spconsent,
            "t_spconsent_jdoe_genetic": t_spconsent_jdoe_genetic,
            "t_use_partial_spconsent": t_use_partial_spconsent,
            "t_spconsent_whsieh_genetic": t_spconsent_whsieh_genetic,
            "t_use_full_spconsent": t_use_full_spconsent,
            "t_write2": t_write2,
            "t_use_missing_new_spcats": t_use_missing_new_spcats,
            "t_spconsent_jdoe_bio_health": t_spconsent_jdoe_bio_health,
            "t_use_whsieh_missing": t_use_whsieh_missing,
            "t_spconsent_whsieh_racial": t_spconsent_whsieh_racial,
            "t_use_all_spcats": t_use_all_spcats,
            "t_rename": t_rename,
            "t_use_fhublet_no_consent_after_rename": t_use_fhublet_no_consent_after_rename,
            "t_consent_fhublet": t_consent_fhublet,
            "t_spconsent_fhublet_racial": t_spconsent_fhublet_racial,
            "t_use_fhublet_consent_and_spconsent": t_use_fhublet_consent_and_spconsent,
            "t_write3": t_write3,
            "t_use_fhublet_consented": t_use_fhublet_consented,
            "t_write4": t_write4,
            "t_revoke_sp_whsieh": t_revoke_sp_whsieh,
            "t_use_after_sp_revoke": t_use_after_sp_revoke,
            "t_reconsent_sp_whsieh": t_reconsent_sp_whsieh,
            "t_use_after_sp_reconsent": t_use_after_sp_reconsent,
            "t_stop_session": t_stop_session,
            "t_total": t_total,
        }


# -- Runner & Reporter -------------------------------------------------------

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
            time.sleep(0.5)
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
    STEPS = [
        "t_start_session",
        "t_create", "t_use_no_consent",
        "t_consent_jdoe", "t_use_partial_consent",
        "t_consent_whsieh", "t_use_both_consent",
        "t_write1", "t_use_no_spconsent",
        "t_spconsent_jdoe_genetic", "t_use_partial_spconsent",
        "t_spconsent_whsieh_genetic", "t_use_full_spconsent",
        "t_write2", "t_use_missing_new_spcats",
        "t_spconsent_jdoe_bio_health", "t_use_whsieh_missing",
        "t_spconsent_whsieh_racial", "t_use_all_spcats",
        "t_rename",
        "t_use_fhublet_no_consent_after_rename",
        "t_consent_fhublet", "t_spconsent_fhublet_racial",
        "t_use_fhublet_consent_and_spconsent",
        "t_write3",
        "t_use_fhublet_consented",
        "t_write4",
        "t_revoke_sp_whsieh", "t_use_after_sp_revoke",
        "t_reconsent_sp_whsieh", "t_use_after_sp_reconsent",
        "t_stop_session", "t_total",
    ]

    def __init__(self, all_results: dict, output_dir: str):
        self.all_results = all_results
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_csv(self):
        csv_path = self.output_dir / "art9_perf_results.csv"
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
        print("  Mean +/- Std latency per step (seconds)")
        print(f"{'=' * 70}")
        header = f"  {'Step':<30}" + "".join(f"{m:>{col_w}}" for m in modes)
        print(header)
        print("  " + "-" * (30 + col_w * len(modes)))

        for step in self.STEPS:
            row = f"  {step:<30}"
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
            print("  [WARN] matplotlib not installed -- skipping charts")
            return

        modes = list(self.all_results.keys())
        steps_no_total = [s for s in self.STEPS if s != "t_total"]

        # Per-step grouped bar chart
        fig, ax = plt.subplots(figsize=(16, 6))
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
        ax.set_xticklabels([s.replace("t_", "") for s in steps_no_total],
                           rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("Time (s)")
        ax.set_title("Art 9 Workflow -- Per-Step Latency")
        ax.legend()
        fig.tight_layout()
        fig.savefig(self.output_dir / "art9_per_step.png", dpi=150)
        plt.close(fig)

        # Total latency bar chart
        fig, ax = plt.subplots(figsize=(6, 4))
        totals = [statistics.mean([r["t_total"] for r in self.all_results[m]])
                  for m in modes]
        stds = [statistics.stdev([r["t_total"] for r in self.all_results[m]])
                if len(self.all_results[m]) > 1 else 0.0
                for m in modes]
        colors = ["#4c78a8", "#f58518", "#e45756"][:len(modes)]
        ax.bar(modes, totals, color=colors)
        ax.set_ylabel("Time (s)")
        ax.set_title("Art 9 Workflow -- Total Latency")
        fig.tight_layout()
        fig.savefig(self.output_dir / "art9_total.png", dpi=150)
        plt.close(fig)

        print(f"  Charts saved to {self.output_dir}/")


# -- CLI ----------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Benchmark: Art 9 Special Data Consent workflow")
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
