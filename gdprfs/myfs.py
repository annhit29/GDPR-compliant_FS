import requests
from errno import EACCES
import getpass
import threading
from fuse import Fuse
import fuse
fuse.fuse_python_api = (0, 2) 

import csv
from io import StringIO, BytesIO
from gdprfs.llm import run_llm_analysis_and_update_db
from gdprfs.settings import INSTRLIB_EXE, INSTRLIB_FORMULA, INSTRLIB_LOG, INSTRLIB_SIG
from instrlib.instrument import Instrument
from instrlib.logger import Logger
from instrlib.pdp import EnfGuard
from instrlib.schema import Schema
from instrlib.pep import PEP, InstrumentationMapping
from instrlib.event import Event, Functional
import os, shutil
from datetime import datetime
from pathlib import Path
from gdprfs.db_utils import Session, sync_users_from_external, update_file_mapping_for_upper, update_file_metadata, mark_file_deleted, _is_temp_name
from gdprfs.models import File, Person, PersonFileSpecialCategory
import yaml
import json
import subprocess # so the poller runs independently of the FUSE main loop, i.e. one daemon for FUSE, one daemon for poller
from pypdf import PdfReader, PdfWriter
from io import BytesIO
from fuse import Stat
from errno import ENOENT
import zipfile
import time as _time
import base64, uuid as _uuid

PDF_CACHE = {}
CSV_CACHE = {}  # key: absolute Path → {"enforced_bytes": bytes, "mtime": float}
REDACTED_TEMPLATE = Path("/var/lib/gdprfs/redacted_template.pdf")
_access_responses = {}  # uid -> {response_id, zip_path}

_current_session_purpose = "marketing"  # updated by StartSession/StopSession
_session_active = False  # True only between StartSession and StopSession
_save_in_progress_dirs = set()  # directories where a temp→real save is in progress

# run as root to have access to /dev/fuse and /var/lib/gdprfs
UPPER_DIR  = Path("/var/lib/gdprfs/upper")
MIRROR_DIR = Path("/var/lib/gdprfs/mirror")

# Make sure the directories exist and are private
UPPER_DIR.mkdir(parents=True, exist_ok=True)
MIRROR_DIR.mkdir(parents=True, exist_ok=True)
(UPPER_DIR / "_rectify_staging").mkdir(parents=True, exist_ok=True) # a directory for staging files for Art 16 rectification files, not accessible by users and cleaned up after use
os.chmod(MIRROR_DIR, 0o700) # The directory /var/lib/gdprfs/mirror is accessible only by root (rwx------)
"""
[Design choice] not having other users access the mirror dir:
because /mirror is the trusted, immutable mirror
Thus,
- Users never touch /mirror directly
- Only our Python FUSE daemon (running as root) reads/writes there: through _sync_to_mirror() and _delete_from_mirror()
- We can see what's inside only if we use sudo
"""

# safely remove stale temp files .goutputstream-XXXXXX on mount startup:
for f in UPPER_DIR.glob(".goutputstream-*"):
    f.unlink(missing_ok=True)

#  ========== HELPER FUNCTIONS ==========

def _upper(path: str) -> Path:
    """
    Map FUSE path to the real file path in UPPER_DIR
    i.e. Find the real file in the upper dir
    """
    return (UPPER_DIR / path.lstrip("/")).resolve()

def _mirror(path: str) -> Path:
    """
    Map FUSE path to the real file path in MIRROR_DIR
    i.e. Find the real file in the mirror dir
    """
    return (MIRROR_DIR / path.lstrip("/")).resolve()

def _ensure_parent(p: Path):
    """Make sure the folder exists before saving a file"""
    p.parent.mkdir(parents=True, exist_ok=True)

def _sync_to_mirror(fuse_path: str):
    """Copy file from /upper to /mirror"""
    src = _upper(fuse_path)
    dst = _mirror(fuse_path)
    if not src.exists():
        return
    _ensure_parent(dst)
    shutil.copy2(src, dst)

def _delete_from_mirror(fuse_path: str):
    """
    If the user deletes something from FUSE,
    Then we delete the corresponding trusted copy in /mirror too
    (or mark it deleted if we want versioning later).
    """
    dst = _mirror(fuse_path)
    if dst.exists():
        dst.unlink()

def _do_delete_file(fuse_path: str):
    """Delete a file from upper + mirror + DB.
    Called by both FUSE unlink() and enforcer causation handler."""
    p = _upper(fuse_path)
    if p.exists():
        os.unlink(p)
    _delete_from_mirror(fuse_path)
    try:
        mark_file_deleted(str(p.resolve()))
    except Exception as e:
        print(f"[DB] Warning: failed to log deletion for {p}: {e}")
    print(f"[DELETE] {fuse_path} removed from upper, mirror, and DB")

def _check_consent(uid: str, purpose: str) -> bool:
    """Return True if uid has active consent for purpose, False if revoked."""
    try:
        res = requests.get(f"http://127.0.0.1:5000/api/consents/{uid}/{purpose}", timeout=1)
        data = res.json()
        return data.get("status") == "consented"
    except Exception:
        return True  # fail-open: assume consent if platform unreachable

def _check_special_consent(uid: str, spCat: str) -> bool:
    """Return True if uid has active special consent for the given Art 9 category."""
    try:
        res = requests.get(f"http://127.0.0.1:5000/api/consents/special/{uid}/{spCat}", timeout=1)
        data = res.json()
        return data.get("status") == "special_consented"
    except Exception:
        return True  # fail-open: assume consent if platform unreachable

def replay_from_consent_db(logger):
    """
    On startup, all active events are re-injected into the enforcer, so that the enforcer has the latest event states.
    """
    BASE_URL = "http://127.0.0.1:5000"
    CONFIG_PATH = "/home/ann20010929/MA3/Building_a_GDPR-compliant_file_system/instrlib/external_consent_platform/event_config.yaml"

    try:
        # Load event mapping from YAML
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
        state_to_event = config.get("state_to_event", {})

        # Fetch all current consent states directly
        res = requests.get(f"{BASE_URL}/api/consents")
        rows = res.json()
        print(f"[INIT] Replaying {len(rows)} consent states into enforcer...")

        # Only replay consent/revoke events: request events (RequestAccess,
        # RequestErasure, RequestRectification) need extra fields (fid, fid_new)
        # not stored in CurrentEventState, so skip them.
        replayable = {"Consent", "Revoke", "SpecialConsent", "RevokeSpecialConsent"}

        for row in rows:
            try:
                uid = row["uid"]
                purpose = row["purpose"]
                status = row["status"].lower()

                ev_name = state_to_event.get(status)

                if not ev_name:
                    print(f"[INIT] Unknown status: {status}, skipping...")
                    continue

                if ev_name not in replayable:
                    print(f"[INIT] Skipping non-replayable event {ev_name} for {uid}")
                    continue

                if ev_name in ("SpecialConsent", "RevokeSpecialConsent"):
                    spCat = row.get("spCat", "")
                    evt = Event(ev_name, uid, purpose, spCat)
                else:
                    evt = Event(ev_name, uid, purpose)

                logger.log([evt], threading.Event(), False)
                print(f"[INIT] Replayed {evt}")
            except Exception as e:
                print(f"[INIT] Warning: failed to replay row {row}: {e}")
        print("[INIT] Replay completed.")

    except Exception as e:
        print(f"[INIT] Failed to replay consents from consent DB: {e}")

def _uids_from_page_text(text: str):
    """
    Given the text of a single PDF page, return the list of uids
    whose names appear on that page. Falls back to pseudo-uid if needed.
    """
    text_lc = (text or "").lower()
    if not text_lc.strip():
        return []

    uids = []
    with Session() as session:
        people = session.query(Person).all()
        for person in people:
            first = (person.first_name or "").strip().lower()
            last  = (person.last_name  or "").strip().lower()
            full  = f"{first} {last}".strip()

            if not first and not last:
                continue

            if full and full in text_lc:
                pass_match = True
            elif first and first in text_lc:
                pass_match = True
            elif last and last in text_lc:
                pass_match = True
            else:
                pass_match = False

            if pass_match:
                if person.uid:
                    uids.append(person.uid)
                else:
                    # fallback
                    pseudo = (first[:1] + last) if (first or last) else "anonymous"
                    uids.append(pseudo)

    return uids

def _get_file_and_user(path: str):
    """Return (file_id, list of uids) for the file at path, if any."""
    with Session() as session:
        file_obj = session.query(File).filter(File.abs_path == str(Path(path).resolve())).first()
        if not file_obj:
            return None, []
        uids = [_person_effective_uid(person) for person in file_obj.people]
        return file_obj.file_id, uids

def _get_file_and_registered_user(path: str):
    """Return (file_id, list of uids) for registered data subjects only.
    Skips ghost/unregistered Person entries created by LLM analysis."""
    with Session() as session:
        file_obj = session.query(File).filter(File.abs_path == str(Path(path).resolve())).first()
        if not file_obj:
            return None, []
        uids = [person.uid for person in file_obj.people if person.uid]
        return file_obj.file_id, uids

def _person_effective_uid(person: Person) -> str:
    """Return the real uid if registered, else the deterministic pseudo-uid used elsewhere."""
    if person.uid:
        return person.uid
    first = (person.first_name or "").lower().replace(" ", "")
    last  = (person.last_name or "").lower().replace(" ", "")
    return (first[:1] + last) if (first or last) else "anonymous"


def _special_categories_by_uid_for_file(abs_path, page_index=None, row_index=None):
    """
    Return a dict: uid -> set(categories) for this file.
    If page_index is given (PDF), only return categories for that page.
    If row_index is given (CSV), only return categories for that row.
    If neither is given, return all categories (file-level, for TXT).
    """
    out = {}

    with Session() as s:
        f = s.query(File).filter(File.abs_path == str(Path(abs_path).resolve())).first()
        if not f:
            return out

        query = (
            s.query(PersonFileSpecialCategory, Person)
            .join(Person, Person.id == PersonFileSpecialCategory.person_id)
            .filter(PersonFileSpecialCategory.file_id == f.id)
        )

        if page_index is not None:
            query = query.filter(PersonFileSpecialCategory.page_index == page_index)
        elif row_index is not None:
            query = query.filter(PersonFileSpecialCategory.row_index == row_index)

        for pfsc, person in query.all():
            uid = _person_effective_uid(person)
            out.setdefault(uid, set()).add(pfsc.special_category)

    return out

def events_for_path(path: str, event_type: str):
    """
    Return a list of Event objects (possibly multiple if file has several owners).
    event_type ∈ {'Use', 'Write', 'Delete'}
    """
    fid, uid = _get_file_and_user(_upper(path))
    # Skip temporary names
    if _is_temp_name(path):
        return [Event('Write', 'tempfile', _current_session_purpose)]
    if not fid:
        fid = f"unknown-{os.path.basename(path)}"
    if not uid:
        uid = "anonymous"
    if event_type == 'Use':
        return [Event('Use', fid, uid)]
    elif event_type == 'Write':
        return [Event('Write', fid, _current_session_purpose)]
    elif event_type == 'Delete':
        return [Event('Delete', fid)]
    else:
        return []


def events_for_read(path):
    """Return appropriate events for read(), skip .goutputstream temporary files."""
    base = os.path.basename(path)

    # Case 1: temporary gedit files (.goutputstream-XXXX)
    if base.startswith(".goutputstream-"):
        return []  # No event, because final Write will be emitted at rename()

    # Sanitize LibreOffice lock files: .~lock.fhublet.csv# → fhublet.csv
    real_base = base
    if base.startswith(".~lock.") and base.endswith("#"):
        real_base = base[len(".~lock."):-len("#")]

    # For lock files, look up the real file instead
    lookup_path = _upper(path)
    if real_base != base:
        lookup_path = _upper(path).parent / real_base

    # Case 2: normal file read → Use(fid, purpose, uid)
    fid, uids = _get_file_and_user(lookup_path)
    fid = fid or real_base

    events = []
    with Session() as session:
        file_obj = session.query(File).filter(File.abs_path == str(lookup_path.resolve())).first()

        # Case 1: No personal data linked → free access, but still log as "nonpersonal"
        if not file_obj or not file_obj.people:
            print(f"[GDPR] {fid} contains no personal data, so no enforcement needed")
            actor = getpass.getuser()
            return [Event("UseNonPII", fid, actor)]

        # Case 2: Personal data → one Use per data subject (registered or not)
        for person in file_obj.people:
            # choose uid or derive fallback
            if person.uid:
                uid = person.uid
            else:
                # deterministic pseudo-uid for unregistered users
                first = (person.first_name or "").lower().replace(" ", "")
                last  = (person.last_name or "").lower().replace(" ", "")
                uid = (first[:1] + last) if first or last else "anonymous"

            events.append(Event("Use", fid, uid))

    print(f"[GDPR] Emitting {len(events)} Use events for {fid}: {[e.args for e in events]}")

    return events


# Track (fid, cat) pairs already logged to avoid duplicate SpecialData events
# when FUSE issues multiple read() calls for the same open().
# Cleared in open() so each new file open gets a fresh log.
_special_data_logged = set()

def _special_data_events(fid, abs_path, uids=None, page_index=None, row_index=None):
    """
    Return SpecialData(fid, cat) events for categories that actually apply
    to at least one linked data subject in this file/page and for which that
    subject has valid special consent (i.e. the data is actually used, not REDACTED).

    This logs that special category data was accessed with proper consent,
    for audit and compliance purposes.
    Deduplicates: each (fid, cat) pair is only logged once per open() cycle."""
    cats_by_uid = _special_categories_by_uid_for_file(abs_path, page_index=page_index, row_index=row_index)
    if not cats_by_uid:
        return []

    uids = uids or []
    consented_cats = set()

    for uid in uids:
        for cat in cats_by_uid.get(uid, set()):
            if _check_special_consent(uid, cat):
                consented_cats.add(cat)

    # Remove already-logged pairs
    consented_cats -= {cat for cat in consented_cats if (fid, cat) in _special_data_logged}

    if not consented_cats:
        print(f"[GDPR Art9] No new consented special categories → skipping SpecialData emission")
        return []

    # Mark as logged
    for cat in consented_cats:
        _special_data_logged.add((fid, cat))

    evts = [Event("SpecialData", fid, cat) for cat in consented_cats]
    print(f"[GDPR Art9] Co-emitting {len(evts)} SpecialData events for {fid} (consented categories: {consented_cats})")
    return evts

def _emit_art30_records(activity):
    """Art 30: manually cause Record events (enforcer causation bug workaround).
    Called after SpecialData events are logged, since special data overrides the SME exemption."""
    records = [
        {"name": "Record", "args": ["GDPRFS", "GDPRFS", activity, "Controller", "GDPRFS"]},
        {"name": "Record", "args": ["GDPRFS", "GDPRFS", activity, "DPO", "dpo@gdprfs.com"]},
        {"name": "Record", "args": ["GDPRFS", "GDPRFS", activity, "Purpose", _current_session_purpose]},
        {"name": "Record", "args": ["GDPRFS", "GDPRFS", activity, "SecurityMeasures", "Access control, consent-aware enforcement, purpose limitation"]},
    ]
    threading.Thread(target=record_causation_handler, args=(records,), daemon=True).start()

# ========== SCHEMA ==========
schema = Schema()
schema.add("UseNonPII", [str, str]) # for reads of non-PII files
schema.add('Use', [str, str]) # for reads
schema.add('Write', [str, str]) # for writes
schema.add('Delete', [str])    # for deletes
schema.add('Collect', [str, str]) # for collection events

schema.add('StartSession', [str, str, str])
schema.add('StopSession', [str])

schema.add('Consent', [str, str]) # for consent events
schema.add('Revoke', [str, str]) # for revoke consent events

# for art15
schema.add('IsCategory', [str, str])
schema.add('RequestAccess', [str]) # request all DS data events from the FS

# for art17
schema.add('RequestErasure', [str, str]) # request erasure of all DS data events in the FS

# for art16
schema.add('RequestRectification', [str, str, str])  # Art 16: (uid, fid_old, fid_new)

schema.add('RequestResponse', [str, str, str])

schema.add('Contains', [str, str])

# for art9
schema.add('Rectify', [str, str]) # for rectification events
schema.add('SpecialConsent', [str, str, str]) # for special category data consent (uid, purpose, spCat)
schema.add('RevokeSpecialConsent', [str, str, str]) # for revoking special category data consent (uid, purpose, spCat)
schema.add('SpecialData', [str, str]) # for special category data (file_id, spCat)

# for art30
schema.add('Record', [str, str, str, str, str]) # for recording an event in the data subject's record

# ========== HANDLERS ==========
def delete_causation_handler(event_list):
    """Called by enforcer when it causes Delete(fid) (Art 17 erasure or Art 5 accuracy).
    args is list[str], e.g. ['fhublet.txt']: not list[list[str]]."""
    for event_json in event_list:
        args = event_json.get("args", [])
        fid = args[0] if args else ""
        if not fid:
            print(f"[CAUSATION] Enforcer caused Delete with empty fid, skipping")
            continue
        print(f"[CAUSATION] Enforcer caused Delete({fid})")

        with Session() as session:
            from gdprfs.models import File
            f = session.query(File).filter_by(file_id=fid).first()
            if not f:
                print(f"[CAUSATION] File {fid} not found in DB, skipping")
                continue

        _do_delete_file("/" + fid)

def rectify_causation_handler(event_list):
    """Called by enforcer when it causes Rectify(fid_old, fid_new)."""
    for event_json in event_list:
        args = event_json.get("args", [])
        fid_old = args[0] if len(args) > 0 else "" 
        fid_new = args[1] if len(args) > 1 else ""
        if not fid_old or not fid_new:
            print(f"[CAUSATION] Rectify with missing args, skipping")
            continue
        print(f"[CAUSATION] Enforcer caused Rectify({fid_old}, {fid_new})")

        staging_path = Path(UPPER_DIR) / "_rectify_staging" / fid_new
        target_upper = _upper("/" + fid_old)
        target_mirror = _mirror("/" + fid_old)

        if not staging_path.exists():
            print(f"[CAUSATION] Staged file {staging_path} not found")
            continue

        # Replace file content
        shutil.copy2(str(staging_path), str(target_upper))
        if target_mirror.exists():
            shutil.copy2(str(staging_path), str(target_mirror))
        staging_path.unlink()

        # Invalidate caches
        CSV_CACHE.pop(str(target_upper), None)
        PDF_CACHE.pop(str(target_upper), None)

        # Re-run LLM analysis on rectified file
        run_llm_analysis_and_update_db(str(target_upper))

def record_causation_handler(event_list):
    """Called by enforcer when it causes Record(pr, c, a, p, v) (Art 30)."""
    for event_json in event_list:
        args = event_json.get("args", [])
        if len(args) < 5:
            print(f"[CAUSATION] Record with insufficient args: {args}, skipping")
            continue
        pr, c, a, p, v = args[0], args[1], args[2], args[3], args[4]
        print(f"[CAUSATION] Enforcer caused Record({pr}, {c}, {a}, {p}, {v})")

        with Session() as session:
            from gdprfs.models import ProcessingRecord
            record = ProcessingRecord(
                processor=pr, controller=c, activity=a,
                property=p, value=v,
                timestamp=datetime.now().isoformat()
            )
            session.add(record)
            session.commit()

def none_handler(event_name, event_args, response, *args, **kwargs):
    """
    Python side ≠ Enforcer side
    The none_handler means "do nothing" in the python side (if we want to return or print something on the terminal).
    And the enforcer suppresses or causes a file operation.
    """
    return None

suppression_handlers = {('Use'): none_handler, ('Write'): none_handler}
causation_handlers = {
    ('Delete'): delete_causation_handler,
    ('IsCategory'): none_handler,
    ('RequestResponse'): none_handler,  # enforcer handles Art 15 response
    ('Contains'): none_handler,          # enforcer handles response content
    ('Rectify'): rectify_causation_handler,  # Art 16 rectification
    ('Record'): record_causation_handler,  # Art 30: persist records of processing activities
}

# ========== MAPPINGS ==========
def read_mapping(action):  
    return Event('Use', str(action), 'userid1')

def write_mapping(action): return Event('Write', str(action), _current_session_purpose)
def unlink_mapping(action): return Event('Delete', str(action))

instrumentation_mapping = InstrumentationMapping({
    'read': read_mapping,
    'write': write_mapping,
    'unlink': unlink_mapping
})

# ========== PEP ==========
def events_for_read_or_skip(path):
    lower = str(path).lower()
    base = os.path.basename(lower)

    # Skip temp files entirely (e.g. LibreOffice lu*.tmp)
    if _is_temp_name(base):
        return []

    # Sanitize lock file name: .~lock.fhublet.csv# → fhublet.csv
    if base.startswith(".~lock.") and base.endswith("#"):
        base = base[len(".~lock."):-len("#")]

    # Skip full-file events for formats with custom enforcement
    if base.endswith(".pdf") or base.endswith(".txt") or base.endswith(".csv") or base.endswith(".odt"):
        return []  # Use events emitted manually inside read()

    return events_for_read(path)

def events_for_write_or_skip(path):
    """Skip automatic Write event logging for temp files and for files that need
    consent pre-checks (handled in _write / rename instead)."""
    base = os.path.basename(str(path).lower())

    # Temp files: Write event is emitted later at rename (temp → real)
    if _is_temp_name(path):
        return []

    # For all non-temp files: skip automatic logging here.
    # The write() body and rename() gate handle consent checks + event emission.
    return []

pep = PEP(
    mapping={
        ('MyFS', 'read'): Functional('Use', lambda path, *a, **kw: events_for_read_or_skip(path)),
        ('MyFS', 'write'): Functional('Write', lambda path, *a, **kw: events_for_write_or_skip(path)),
    },
    suppression_handlers=suppression_handlers,
    causation_handlers=causation_handlers
)

pdp = EnfGuard(INSTRLIB_EXE, INSTRLIB_SIG, INSTRLIB_FORMULA, log_file=INSTRLIB_LOG)

logger = Logger(pep, schema, pdp)
print("PEP mapping keys:", list(logger.pep.mapping.keys()))

# --- STARTUP OF THE ENFORCER AND SYNC ---
pdp.start_threads() # then start the EnfGuard enforcer + threads
sync_users_from_external() # sync users from external consent platform
replay_from_consent_db(logger) # replay all current consent states into the enforcer

# --- Ingest HTTP server: receives Consent/Revoke from poller ---
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

def start_ingest_server(logger):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/access_download/"):
                response_id = self.path.split("/access_download/", 1)[1]
                # Find the matching ZIP
                zip_path = Path(f"/var/lib/gdprfs/access_responses/{response_id}.zip")
                if zip_path.exists():
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("Content-Disposition", f"attachment; filename={response_id}.zip")
                    data = zip_path.read_bytes()
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self.send_error(404, "Response not found")
            elif self.path.startswith("/access_status/"):
                uid = self.path.split("/access_status/", 1)[1]
                info = _access_responses.get(uid)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                if info:
                    self.wfile.write(json.dumps({"ready": True, "response_id": info["response_id"]}).encode())
                else:
                    self.wfile.write(json.dumps({"ready": False}).encode())
            else:
                self.send_error(404, "Unknown endpoint")
                
        def do_POST(self):
            global _current_session_purpose, _session_active
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                # --- Branch 1: handle Consent/Revoke events ---

                if self.path == "/ingest":
                    kind = str(payload.get("kind", "")).strip() # is the event name, e.g. "Consent", "Revoke", "RequestAccess", "RequestErasure", "StartSession", "StopSession"
                    uid = payload.get("uid")
                    purpose = str(payload.get("purpose", "")).strip()
                    reason = str(payload.get("reason", "")).strip()

                    if not kind or not uid:
                        self.send_error(400, "missing kind or uid")
                        return

                    # CASE 1: StartSession(uid, purpose, reason)
                    if kind == "StartSession":
                        if not purpose or not reason:
                            self.send_error(400, "missing purpose or reason for StartSession")
                            return
                        _current_session_purpose = purpose
                        _session_active = True
                        evt = Event("StartSession", uid, purpose, reason)

                    # CASE 2: StopSession(uid)
                    elif kind == "StopSession":
                        _current_session_purpose = "marketing"
                        _session_active = False
                        evt = Event("StopSession", uid)

                    # CASE 3a: SpecialConsent(uid, purpose, spCat) of Art 9
                    elif kind == "SpecialConsent":
                        spCat = str(payload.get("spCat", "")).strip()
                        if not purpose or not spCat:
                            self.send_error(400, "missing purpose or spCat for SpecialConsent")
                            return
                        evt = Event("SpecialConsent", uid, purpose, spCat)

                    # CASE 3b: RevokeSpecialConsent(uid, purpose, spCat) of Art 9
                    elif kind == "RevokeSpecialConsent":
                        spCat = str(payload.get("spCat", "")).strip()
                        if not purpose or not spCat:
                            self.send_error(400, "missing purpose or spCat for RevokeSpecialConsent")
                            return
                        evt = Event("RevokeSpecialConsent", uid, purpose, spCat)

                    # CASE 4a: RequestAccess(uid)
                    elif kind == "RequestAccess":
                        # 1. Log RequestAccess to enforcer
                        evt = Event("RequestAccess", uid)
                        logger.log([evt], threading.Event(), False)

                        # 2. Query DB for all files + special categories linked to this DS
                        with Session() as db_sess:
                            person = db_sess.query(Person).filter_by(uid=uid).first()
                            file_records = []
                            special_cats = {}  # file_id -> [categories]
                            if person:
                                file_records = [(f.file_id, f.abs_path) for f in person.files if f.abs_path]
                                # Query Art 9 special categories per file for this person
                                rows = (
                                    db_sess.query(PersonFileSpecialCategory, File)
                                    .join(File, File.id == PersonFileSpecialCategory.file_id)
                                    .filter(PersonFileSpecialCategory.person_id == person.id)
                                    .all()
                                )
                                for pfsc, f in rows:
                                    special_cats.setdefault(f.file_id, []).append(pfsc.special_category)

                        # 3. Package files + metadata manifest into a ZIP
                        request_id = f"access_{uid}_{int(_time.time())}"
                        response_id = f"response_{uid}_{int(_time.time())}"
                        staging_dir = Path("/var/lib/gdprfs/access_responses")
                        staging_dir.mkdir(parents=True, exist_ok=True)
                        zip_path = staging_dir / f"{response_id}.zip"

                        with zipfile.ZipFile(zip_path, 'w') as zf:
                            for file_id, abs_path in file_records:
                                if abs_path and Path(abs_path).exists():
                                    zf.write(abs_path, arcname=os.path.basename(abs_path))
                            # Include metadata manifest with special categories (Art 9)
                            manifest = {"data_subject": uid, "files": []}
                            for file_id, abs_path in file_records:
                                entry = {"file_id": file_id, "filename": os.path.basename(abs_path or "")}
                                if file_id in special_cats:
                                    entry["special_categories_art9"] = special_cats[file_id]
                                manifest["files"].append(entry)
                            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

                        # 4. Emit RequestResponse to enforcer
                        resp_evt = Event("RequestResponse", uid, "access", response_id)
                        logger.log([resp_evt], threading.Event(), False)

                        # 5. Track response for download
                        _access_responses[uid] = {"response_id": response_id, "zip_path": str(zip_path)}

                        # 6. Return success
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "ok": True, "message": "Access request processed",
                            "response_id": response_id
                        }).encode())
                        return

                    # CASE 4b: RequestErasure(uid)
                    elif kind == "RequestErasure":
                        fid = payload.get("fid", "").strip()
                        if not uid or not fid:
                            self.send_error(400, "missing uid or fid for RequestErasure")
                            return

                        # Pre-check: Art 17.b requires consent to be withdrawn first.
                        # If consent is still active for ANY purpose, erasure won't trigger.
                        has_active_consent = any(
                            _check_consent(uid, p) for p in ("marketing", "service", "analytics")
                        )
                        if has_active_consent:
                            self.send_response(200)
                            self.end_headers()
                            self.wfile.write(json.dumps({
                                "ok": False,
                                "message": f"Erasure rejected: {uid} still has active consent. Revoke consent first."
                            }).encode())
                            return

                        # 1. Log RequestErasure(uid, fid): 2 args per schema
                        evt = Event("RequestErasure", uid, fid)
                        logger.log([evt], threading.Event(), False)

                        # 2. Emit RequestResponse (required by gdpr.lex Art 17 points a/b)
                        response_id = f"response_{uid}_{int(_time.time())}"
                        resp_evt = Event("RequestResponse", uid, "erasure", response_id)
                        logger.log([resp_evt], threading.Event(), False)

                        # 3. Return success: enforcer will cause Delete(fid) if obliged
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "ok": True,
                            "message": f"RequestErasure logged for {uid}, file {fid}",
                            "response_id": response_id
                        }).encode())
                        return

                    # CASE 5: RequestRectification(uid, fid_old, fid_new) of Art 16
                    elif kind == "RequestRectification":
                        fid_old = (payload.get("fid_old") or payload.get("fid", "")).strip()
                        fid_new = payload.get("fid_new", "").strip()
                        if not uid or not fid_old or not fid_new:
                            self.send_error(400, "missing uid, fid_old, or fid_new")
                            return

                        staging_path = Path(UPPER_DIR) / "_rectify_staging" / fid_new
                        if not staging_path.exists():
                            self.send_error(400, f"staged file {fid_new} not found")
                            return

                        evt = Event("RequestRectification", uid, fid_old, fid_new)
                        logger.log([evt], threading.Event(), False)

                        response_id = f"response_{uid}_{int(_time.time())}"
                        resp_evt = Event("RequestResponse", uid, "rectification", response_id)
                        logger.log([resp_evt], threading.Event(), False)

                        # Perform rectification in background (enforcer causation bug workaround)
                        threading.Thread(target=rectify_causation_handler,
                                         args=([{"name": "Rectify", "args": [fid_old, fid_new]}],),
                                         daemon=True).start()

                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "ok": True,
                            "message": f"RequestRectification logged: {fid_old} -> {fid_new}",
                            "response_id": response_id
                        }).encode())
                        return

                    # CASE 6: Consent/Revoke or others (already handled)
                    # Create a generic Event, supporting any kind
                    # If purpose missing, drop it automatically
                    elif purpose: # if purpose is provided && it's not the StopSession event
                        evt = Event(kind, uid, purpose)
                    else:
                        evt = Event(kind, uid)

                    print(f"[INGEST] Received {kind} event from {'internal' if kind in ['StartSession','StopSession'] else 'external'} platform.")                    
                    logger.log([evt], threading.Event(), False)
                    print(f"[INGEST] Logged event {kind}({uid}, {purpose or reason})")

                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"ok": true, "message": "Event ingested/logged."}')

                # --- Branch 2: handle rectification file upload (Art 16) ---
                elif self.path == "/upload_rectification":
                    content_b64 = payload.get("content_b64", "")
                    filename = payload.get("filename", "").strip()
                    if not content_b64 or not filename:
                        self.send_error(400, "missing content_b64 or filename")
                        return
                    fid_new = f"{_uuid.uuid4().hex}_{filename}" #the prefix ensures filename prevents collisions in recttify_staging/ folder
                    staging_path = UPPER_DIR / "_rectify_staging" / fid_new
                    staging_path.write_bytes(base64.b64decode(content_b64))
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "fid_new": fid_new}).encode())

                # --- Branch 3: handle user sync trigger ---
                elif self.path == "/sync_users":
                    try:
                        sync_users_from_external()
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(b'{"ok": true, "msg": "Synced users successfully"}')
                        print("[SYNC] Received external trigger → synced users from consent platform.")

                    except Exception as e:
                        self.send_error(500, str(e))

                else:
                    self.send_error(404, "Unknown endpoint")

            except Exception as e:
                self.send_error(500, str(e))

        def log_message(self, *a, **kw):  # silence default HTTP logs
            return

    def serve():
        HTTPServer(("127.0.0.1", 7000), Handler).serve_forever()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    print("[INIT] Ingest + Sync HTTP server started at:")
    print("  - POST /ingest → for Consent/Revoke events")
    print("  - POST /sync_users → for syncing new users")
    print("  - POST /ingest also supports StartSession/StopSession from internal purpose platform")

class InstrumentNoAttr(Instrument):
    """
    Instrument variant that skips overwriting __getattribute__ and __setattr__
    if the class is a Fuse-based class (e.g. the MyFS class) to avoid recursion errors,
    and keeps normal (i.e. non-Fuse) instrumentation for other classes.

    1. Create this class
    2. Use @InstrumentNoAttr(logger) instead of @Instrument(logger) when decorating MyFS class to not modify instrument.py.
    """

    def __init__(self, logger):
        super().__init__(logger)

    def __call__(self, target):
        if isinstance(target, type):
            # Skip overwriting get/set attribute ONLY for Fuse subclasses
            try:
                from fuse import Fuse as FuseBase
                if issubclass(target, FuseBase):
                    return self.instrument_cls(target)
            except Exception:
                pass
            # Non-Fuse classes behave as usual
            self.overwrite_getattribute(self, target)
            self.overwrite_setattribute(self, target)
            return self.instrument_cls(target)
        return super().__call__(target)

@InstrumentNoAttr(logger)
class MyFS(Fuse):
    """A minimal GDPR-compliant FUSE filesystem."""

    def _write(self, path, data, offset, fh=None):
        p = _upper(path)

        # Ensure the parent folder exists
        _ensure_parent(p)

        # GDPR pre-check: block writes to non-temp files if session/consent is missing
        if not _is_temp_name(path):
            _, uids = _get_file_and_user(p)
            if uids:
                # Art 5b: no active session → block write (purpose limitation)
                if not _session_active:
                    print(f"[GDPR Art5b] Blocking write to {path}: no active session (purpose limitation)")
                    raise OSError(EACCES, "GDPR policy: write requires an active session (Art 5b purpose limitation)")
                # Art 6: check regular consent
                for uid in uids:
                    if not _check_consent(uid, _current_session_purpose):
                        print(f"[GDPR] Blocking write to {path}: {uid} has no consent")
                        raise OSError(EACCES, "GDPR policy: write requires consent")
                # Art 9: check special consent for files with special data categories
                cats_by_uid = _special_categories_by_uid_for_file(p)
                for uid in uids:
                    for cat in cats_by_uid.get(uid, set()):
                        if not _check_special_consent(uid, cat):
                            print(f"[GDPR Art9] Blocking write to {path}: {uid} lacks special consent for '{cat}'")
                            raise OSError(EACCES, f"GDPR Art 9: write requires special consent for '{cat}'")

        # Write to the real upper file
        with open(p, "r+b" if p.exists() else "wb") as f:
            f.seek(offset)
            f.write(data) # data written into the real file in /upper
            f.flush() # flush to disk

        # Invalidate CSV cache after write
        if str(p).lower().endswith(".csv"):
            CSV_CACHE.pop(p, None)

        # --- skip temp files ---
        if not _is_temp_name(path):
            try:
                update_file_mapping_for_upper(str(p.resolve()), context="write")
                update_file_metadata(str(p.resolve()), "write")
                
            except Exception as e:
                print(f"[DB] Warn: mapping update failed for {p}: {e}")
        else:
            print(f"[DB] Skipped mapping for temporary file: {path}")

        # After writing, sync to mirror
        _sync_to_mirror(path)
        print(f"[WRITE] path={path} → synced to mirror")

        # then emit Collect event for non-temp files (data entering the system)
        if not _is_temp_name(path):
            self._emit_collect_event(path)

        # --- LLM should NOT run for temp files ---
        if not _is_temp_name(path):
            try:
                print(f"[LLM] Running LLM analysis after write for {path}")
                run_llm_analysis_and_update_db(str(p.resolve()))
            except Exception as e:
                print(f"[LLM] WARNING: LLM update failed after write: {e}")
        else:
            print(f"[LLM] Skipping LLM analysis for temp file {path}")

        return len(data) # Returning len(data) tells FUSE “OK, I wrote everything.”

    def _emit_write_event(self, path: str):
        """Emit a GDPR Write event for a file when a write happens but no Write event is triggered."""
        try:
            fid, uids = _get_file_and_user(_upper(path))
            fid = fid or f"unknown-{os.path.basename(path)}"
            events = [Event('Write', fid, _current_session_purpose)]
            cau, sup, _, _ = logger.log(events, threading.Event(), False)
            if sup:
                print(f"[GDPR] Write event for {path} was SUPPRESSED by enforcer")
            else:
                print(f"[GDPR] Write event emitted for {path}")
                special_evts = _special_data_events(fid, _upper(path), uids)
                if special_evts:
                    logger.log(special_evts, threading.Event(), False)
                    _emit_art30_records("Write")  # Art 30 workaround: Write is also DataProcessing("Use")
        except Exception as e:
            print(f"[GDPR] Warning: failed to emit Write event for {path}: {e}")

    def _emit_collect_event(self, path: str):
        """Emit a GDPR Collect event when personal data enters the system.

        Only emits for registered data subjects (with a real uid),
        not for ghost Person entries inferred by LLM content analysis.

        Collect(fid, uid) refines to:
          - PersonalData(d, ds)        via r_PersonalData_Collect
          - IsCollection("Collect", ds) via r_IsCollection
          - HasIntendedAutomatedDecision(d, ...) via r_HasIntendedAutomatedDecision
        """
        try:
            fid, uids = _get_file_and_registered_user(_upper(path))
            fid = fid or f"unknown-{os.path.basename(path)}"
            if uids:
                events = [Event('Collect', fid, uid) for uid in uids]
                cau, sup, _, _ = logger.log(events, threading.Event(), False)
                if not sup:
                    special_evts = _special_data_events(fid, _upper(path), uids)
                    if special_evts:
                        logger.log(special_evts, threading.Event(), False)
                        _emit_art30_records("Collect")  # Art 30 workaround
                    else:
                        # SpecialData events may have already been emitted this open() cycle
                        # (deduplicated by _special_data_logged). Still emit the Art 30 Collect
                        # record if the file carries consented special categories.
                        cats_by_uid = _special_categories_by_uid_for_file(_upper(path))
                        if any(
                            _check_special_consent(uid, cat)
                            for uid in uids
                            for cat in cats_by_uid.get(uid, set())
                        ):
                            _emit_art30_records("Collect")
                print(f"[GDPR] Collect events emitted for {path}: {list(uids)}")
            else:
                print(f"[GDPR] No data subjects linked to {path}, skipping Collect")
        except Exception as e:
            print(f"[GDPR] Warning: failed to emit Collect event for {path}: {e}")

    def _make_redacted_page(self):
        """
        Returns a single-page PDF that displays 'REDACTED'.
        We simply load a pre-generated template PDF from disk and cache it.
        """
        if "redacted_page" in PDF_CACHE:
            return PDF_CACHE["redacted_page"]

        if REDACTED_TEMPLATE.exists():
            with open(REDACTED_TEMPLATE, "rb") as f:
                data = f.read()
        else:
            # Fallback: blank A4 page if the template is missing
            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842)
            buf = BytesIO()
            writer.write(buf)
            data = buf.getvalue()
            print("[GDPR] WARNING: redacted_template.pdf missing → using blank page fallback")

        PDF_CACHE["redacted_page"] = data
        return data



    def _get_or_build_redacted_pdf(self, path):
        """Build (once) and cache a redacted version of the PDF with suppressed pages blanked."""
        abspath = _upper(path)

        cache = PDF_CACHE.get(abspath)
        if cache and "redacted_bytes" in cache:
            return cache["redacted_bytes"]

        # 1) Load original PDF
        reader = PdfReader(str(abspath))

        # 2) Figure out base fid + file-level uids for this file
        # File-level uids (e.g. from a .gdprowner override) must apply to every page
        # even when the page text does not mention the owner's name.
        fid_base, file_level_uids = _get_file_and_user(abspath)
        if not fid_base:
            fid_base = os.path.basename(abspath)

        writer = PdfWriter()

        # 3) For each page: ask enforcer, then add original or blank page
        for idx, page in enumerate(reader.pages):
            page_fid = f"{fid_base}/page-{idx}"
            page_text = page.extract_text() or ""
            page_uids = _uids_from_page_text(page_text)

            # Merge file-level uids with page-text uids: the file-level mapping
            # (gdprowner override or DB) gates every page regardless of content.
            uids = list(set(file_level_uids) | set(page_uids))

            if not uids:
                # page has no personal data → no Use event, no suppression
                writer.add_page(page)
                continue

            # Pre-check Art 5b: no active session → redact page (purpose limitation)
            skip_page = False
            if not _session_active:
                print(f"[GDPR Art5b] No active session → redacting page {idx} (purpose limitation)")
                skip_page = True

            # Pre-check: if any data subject lacks consent, redact without logging
            if not skip_page:
                for uid in uids:
                    if not _check_consent(uid, _current_session_purpose):
                        print(f"[GDPR] {uid} has no consent → redacting page {idx} (no Use event logged)")
                        skip_page = True
                        break
            if not skip_page:
                # Pre-check Art 9: use per-page categories (not file-level)
                page_cats_by_uid = _special_categories_by_uid_for_file(abspath, page_index=idx)
                for uid in uids:
                    for cat in page_cats_by_uid.get(uid, set()):
                        if not _check_special_consent(uid, cat):
                            print(f"[GDPR Art9] {uid} lacks special consent for '{cat}' → redacting page {idx}")
                            skip_page = True
                            break
                    if skip_page:
                        break

            if skip_page:
                red_page = self._make_redacted_page()
                red_reader = PdfReader(BytesIO(red_page))
                writer.add_page(red_reader.pages[0])
                continue

            events = [Event("Use", page_fid, uid) for uid in uids]

            cau, sup, _, _ = logger.log(events, threading.Event(), False)

            if sup:
                print(f"[GDPR] Page {idx} suppressed → inserting blank page")
                red_page = self._make_redacted_page()
                red_reader = PdfReader(BytesIO(red_page))
                writer.add_page(red_reader.pages[0])
            else:
                writer.add_page(page)
                special_evts = _special_data_events(page_fid, abspath, uids, page_index=idx)
                if special_evts:
                    logger.log(special_evts, threading.Event(), False)
                    _emit_art30_records("Use")  # Art 30 workaround

        # 4) Serialize redacted PDF once
        buf = BytesIO()
        writer.write(buf)
        data = buf.getvalue()

        PDF_CACHE[abspath] = {"redacted_bytes": data}
        return data

    def _get_or_build_enforced_csv(self, path, emit_events=True):
        """Build (once) and cache an enforced version of the CSV with redacted rows."""
        abspath = _upper(path)
        mtime = abspath.stat().st_mtime

        cache = CSV_CACHE.get(abspath)
        if cache and cache.get("mtime") == mtime:
            return cache["enforced_bytes"]

        print("[CSV] Building enforced CSV (cache miss or stale)")

        fid, file_level_uids = _get_file_and_user(abspath)
        base_fid = fid or os.path.basename(path)

        # Read original CSV as text
        with open(abspath, "r", newline="", encoding="utf-8", errors="ignore") as f:
            reader = list(csv.reader(f))

        output = []
        rows = reader

        # Pre-check Art 5b: no active session → redact all rows (purpose limitation)
        session_blocked = not _session_active and bool(file_level_uids)
        if session_blocked:
            print(f"[GDPR Art5b] No active session → redacting CSV (purpose limitation)")

        # Pre-check Art 6: if any file-level uid has revoked consent, redact all rows
        all_consented = all(_check_consent(uid, _current_session_purpose) for uid in file_level_uids) if file_level_uids else True

        # Pre-check Art 9: if file has special categories and any uid lacks special consent
        art9_blocked = False
        if all_consented and file_level_uids:
            with Session() as s:
                f_obj = s.query(File).filter(File.abs_path == str(abspath.resolve())).first()
                if f_obj and f_obj.special_categories:
                    cats = [c.strip() for c in f_obj.special_categories.split(",") if c.strip()]
                    for cat in cats:
                        for uid in file_level_uids:
                            if not _check_special_consent(uid, cat):
                                print(f"[GDPR Art9] {uid} lacks special consent for '{cat}' → redacting CSV")
                                art9_blocked = True
                                break
                        if art9_blocked:
                            break

        # Skip per-row Use events if a save is in progress
        save_in_progress = os.path.dirname(path) in _save_in_progress_dirs

        for idx, row in enumerate(rows):
            if not file_level_uids:
                output.append(row)
                continue

            if session_blocked or not all_consented or art9_blocked:
                output.append(["REDACTED"] * len(row))
                continue

            if save_in_progress or not emit_events:
                output.append(row)
                continue

            # Normal read: emit per-row Use events
            row_fid = f"{base_fid}/row-{idx}"
            events = [Event("Use", row_fid, uid) for uid in file_level_uids]

            cau, sup, _, _ = logger.log(events, threading.Event(), False)

            if sup:
                print(f"[CSV] Row {idx} suppressed")
                output.append(["REDACTED"] * len(row))
            else:
                output.append(row)
                special_evts = _special_data_events(row_fid, abspath, file_level_uids, row_index=idx)
                if special_evts:
                    logger.log(special_evts, threading.Event(), False)
                    _emit_art30_records("Use")  # Art 30 workaround

        # Serialize CSV back to bytes
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerows(output)
        csv_bytes = buf.getvalue().encode("utf-8")

        CSV_CACHE[abspath] = {"enforced_bytes": csv_bytes, "mtime": mtime}
        return csv_bytes

    def getattr(self, path):
        """
        Return the attributes of a file or directory.
        (e.g. size, permissions, owner, timestamps)
        Called whenever Linux does 'ls', 'stat', etc.
        """

        # Find the real file inside /upper
        real_path = _upper(path)

        if not real_path.exists():
            raise OSError(ENOENT, "No such file or directory")

        # Get the actual file info from disk
        s = real_path.lstat()

        # Fill the FUSE Stat structure
        st = Stat()

        # Copy actual metadata
        st.st_mode  = s.st_mode      # file type + permissions
        st.st_nlink = s.st_nlink     # number of hard links
        st.st_uid   = s.st_uid       # owner user id (still needed for Linux)
        st.st_gid   = s.st_gid       # group id
        st.st_atime = int(s.st_atime)  # access time
        st.st_mtime = int(s.st_mtime)  # modification time
        st.st_ctime = int(s.st_ctime)  # change/creation time

        # Default: real size
        st.st_size = s.st_size      # file size in bytes

        # For TXT files, make sure size is at least length of "REDACTED"
        if real_path.suffix.lower() == ".txt":
            st.st_size = max(st.st_size, len(b"REDACTED")) # len(b"REDACTED") = 8 bytes

        # For CSV files, report the enforced content size (no Use events in getattr)
        if real_path.suffix.lower() == ".csv" and real_path.is_file():
            try:
                enforced = self._get_or_build_enforced_csv(path, emit_events=False)
                st.st_size = len(enforced)
            except Exception as e:
                print(f"[CSV] getattr size override failed: {e}")

        return st

    def mkdir(self, path, mode):
        """Create a directory inside /upper and mirror."""
        p = _upper(path)
        print(f"[MKDIR] Creating directory {p}")

        # Create in upper
        _ensure_parent(p)
        p.mkdir(exist_ok=True)

        # Create in mirror
        m = _mirror(path)
        _ensure_parent(m)
        m.mkdir(exist_ok=True)

        # ---- Folder-level inheritance detection (strong inheritance) ----
        from gdprfs.db_utils import _uids_from_path_string
        folder_name = p.name.lower()

        with Session() as session:
            owners = _uids_from_path_string(folder_name, session)

            if owners:
                for person in owners:
                    print(f"[lazy DB folder] Folder '{folder_name}' recognized as belonging to {person.first_name} {person.last_name}")

                print(f"[lazy DB folder] Folder-level inheritance activated (context=mkdir)")
            else:
                print(f"[lazy DB folder] No matching person for folder '{folder_name}'")

        return 0


    def rmdir(self, path):
        """Remove a directory from both layers."""
        p = _upper(path)
        print(f"[RMDIR] Removing directory {p}")

        if not p.exists() or not p.is_dir():
            from errno import ENOENT
            raise OSError(ENOENT, "Directory does not exist")

        # Remove in upper
        os.rmdir(p)

        # Remove in mirror
        m = _mirror(path)
        if m.exists():
            os.rmdir(m)

        # Update DB
        try:
            mark_file_deleted(str(p.resolve()))
        except Exception as e:
            print(f"[DB] Warning: rmdir deletion log failed for {p}: {e}")

        return 0


    def opendir(self, path):
        """Allow opening a directory."""
        p = _upper(path)
        print(f"[OPENDIR] Opening directory {p}")

        if not p.exists() or not p.is_dir():
            from errno import ENOTDIR
            raise OSError(ENOTDIR, "Not a directory")

        return 0

    def readdir(self, path, offset):
        from fuse import Direntry
        p = _upper(path)
        if not p.is_dir():
            from errno import ENOTDIR
            raise OSError(ENOTDIR, "Not a directory")

        # Always include . and ..
        yield Direntry(".")
        yield Direntry("..")
        # List real entries from /upper
        for name in sorted(os.listdir(p)):
            yield Direntry(name)

    def access(self, path, mode):
        # allow access if the path exists in /upper
        if _upper(path).exists():
            return 0
        from errno import ENOENT
        raise OSError(ENOENT, "No such file or directory")

    def open(self, path, flags):

        # Clear SpecialData dedup tracking for this new open cycle
        _special_data_logged.clear()

        # allow access if the path exists in /upper
        p = _upper(path)
        if p.exists():
            lower = str(p).lower()
            # PDF cache invalidation
            if lower.endswith(".pdf"):
                PDF_CACHE.pop(p, None)
            # CSV cache invalidation
            if lower.endswith(".csv"):
                CSV_CACHE.pop(p, None)
            update_file_mapping_for_upper(str(p.resolve()), context="open")
            update_file_metadata(str(p.resolve()), "open")

            # Disable kernel page cache for enforced file types
            # so our read() is always called (enforcement may change between opens)
            if lower.endswith(".csv") or lower.endswith(".pdf") or lower.endswith(".txt"):
                ffi = fuse.FuseFileInfo()
                ffi.direct_io = True
                return ffi

            return 0
        raise OSError(ENOENT, "No such file or directory")

    def read(self, path, size, offset, fh=None):

        if isinstance(size, (bytes, bytearray)): #if size is data instead of int
            print(f"[WRITE] Misrouted write() detected: redirecting safely to raw write for {path}")
            return self._write(path, size, offset, fh)

        p = _upper(path)
        if not p.is_file():
            raise OSError(ENOENT, "No such file or directory")
    
        # =========== Case1: pdf with page-based Use event ===========
        if str(p).lower().endswith(".pdf"):

            redacted_bytes = self._get_or_build_redacted_pdf(path)

            # still update DB mapping + metadata for access stats
            update_file_mapping_for_upper(str(p.resolve()), context="read")
            update_file_metadata(str(p.resolve()), "read")

            return redacted_bytes[offset:offset + size]

        # =========== Case2: TXT full-file enforcement ===========
        if str(p).lower().endswith(".txt"):
            print("[TXT] Full-file enforcement for TXT read")

            # Determine file_id and data subjects
            fid, uids = _get_file_and_user(_upper(path))
            fid = fid or os.path.basename(path)

            # If no PII → normal read, but log UseNonPII
            if not uids:
                print("[TXT] No personal data → returning normal content")
                actor = getpass.getuser()
                logger.log([Event("UseNonPII", fid, actor)], threading.Event(), False)
                with open(p, "rb") as f:
                    f.seek(offset)
                    chunk = f.read(size)
                update_file_mapping_for_upper(str(p.resolve()), context="read")
                update_file_metadata(str(p.resolve()), "read")
                return chunk

            # Pre-check Art 5b: no active session → no purpose → block read
            if not _session_active:
                print(f"[GDPR Art5b] No active session → REDACTED (purpose limitation)")
                red = b"REDACTED"
                return red[offset: offset + size]

            # Pre-check: if any data subject lacks consent, return REDACTED without logging
            for uid in uids:
                if not _check_consent(uid, _current_session_purpose):
                    print(f"[GDPR] {uid} has no consent → REDACTED (no Use event logged)")
                    red = b"REDACTED"
                    return red[offset: offset + size]

            # Pre-check Art 9: if file has special categories and any uid lacks special consent
            cats_by_uid = _special_categories_by_uid_for_file(p)
            for uid in uids:
                for cat in cats_by_uid.get(uid, set()):
                    if not _check_special_consent(uid, cat):
                        print(f"[GDPR Art9] {uid} lacks special consent for '{cat}' → REDACTED (no Use event logged)")
                        red = b"REDACTED"
                        return red[offset: offset + size]
            
            # Build Use events for all uids
            events = [Event("Use", fid, uid) for uid in uids]

            # Ask the enforcer whether reading should be suppressed
            cau, sup, _, _ = logger.log(events, threading.Event(), False)

            if sup:
                print("[TXT] Suppressed → returning REDACTED")
                red = b"REDACTED"
                return red[offset: offset + size]  # respect offset+size like PDF/ODT

            # Log SpecialData separately (not co-emitted) for audit
            special_evts = _special_data_events(fid, p, uids)
            if special_evts:
                logger.log(special_evts, threading.Event(), False)
                _emit_art30_records("Use")  # Art 30 workaround

            # Otherwise → allow full file text
            with open(p, "rb") as f:
                f.seek(offset)
                chunk = f.read(size)

            update_file_mapping_for_upper(str(p.resolve()), context="read")
            update_file_metadata(str(p.resolve()), "read")

            return chunk

        # =========== Case3: CSV row-based enforcement ===========
        if str(p).lower().endswith(".csv"):
            print("[CSV] Row-based enforcement for CSV read")
            enforced = self._get_or_build_enforced_csv(path, emit_events=True)
            update_file_mapping_for_upper(str(p.resolve()), context="read")
            update_file_metadata(str(p.resolve()), "read")
            return enforced[offset : offset + size]

        # =========== Case4: Fallback case: non-pdf and non-txt files ===========        
        # return only the requested slice, as bytes
        with open(p, "rb") as f: # the file is being read from p i.e. from /upper 
            f.seek(offset)
            data = f.read(size)
        
        update_file_mapping_for_upper(str(p.resolve()), context="read") 
        update_file_metadata(str(p.resolve()), "read") # update timestamps + last_action

        return data


    def create(self, path, mode, fi=None):
        """Create a new empty file in /upper and sync to /mirror."""
        p = _upper(path)
        _ensure_parent(p)

        # Create file in upper layer
        # We opened the file, now it exists, even if we didn’t write on it yet.
        with open(p, "wb") as f:
            pass # create empty file

        # Sync to mirror
        _sync_to_mirror(path)
        print(f"[CREATE] Synced {p} → mirror")

        # Track save-in-progress for temp files
        if _is_temp_name(path):
            _save_in_progress_dirs.add(os.path.dirname(path))

        # Update DB mapping and metadata
        try:
            if not _is_temp_name(path):
                update_file_mapping_for_upper(str(p.resolve()), context="create")
                update_file_metadata(str(p.resolve()), "create")
            else:
                print(f"[DB] Skipped create() DB registration for temp file: {os.path}")

        except Exception as e:
            print(f"[DB] Warning: failed to register new file {p}: {e}")

        return 0

    def rename(self, old, new):
        """
        Rename a file or directory from 'old' → 'new'
        Both in /upper and in /mirror
        """
        old_p = _upper(old)
        new_p = _upper(new)

        if not old_p.exists():
            from errno import ENOENT
            raise OSError(ENOENT, f"No such file: {old}")

        # ---------- GDPR ENFORCEMENT FOR FINAL SAVE ----------
        # temp → real file pattern (gedit .goutputstream-*, LibreOffice .tmp, etc.)
        if _is_temp_name(old) and not _is_temp_name(new):
            _, uids = _get_file_and_user(_upper(new))
            # Art 5b: no active session → block final save (purpose limitation)
            if uids and not _session_active:
                print(f"[GDPR Art5b] Blocking final save for {new}: no active session (purpose limitation)")
                raise OSError(EACCES, "GDPR policy: write requires an active session (Art 5b purpose limitation)")
            # Art 6: check regular consent for all data subjects
            all_consented = all(_check_consent(uid, _current_session_purpose) for uid in uids) if uids else True
            if not all_consented:
                print(f"[GDPR] Blocking final save for {new} due to missing consent")
                raise OSError(EACCES, "GDPR policy: write requires external consent")
            # Art 9: check special consent for files with special data categories
            cats_by_uid = _special_categories_by_uid_for_file(new_p)
            for uid in uids:
                for cat in cats_by_uid.get(uid, set()):
                    if not _check_special_consent(uid, cat):
                        print(f"[GDPR Art9] Blocking final save for {new}: {uid} lacks special consent for '{cat}'")
                        raise OSError(EACCES, f"GDPR Art 9: write requires special consent for '{cat}'")

        # ------------------------------------------------------


        _ensure_parent(new_p)
        os.rename(old_p, new_p)

        # Invalidate CSV cache for old and new paths
        CSV_CACHE.pop(old_p, None)
        CSV_CACHE.pop(new_p, None)

        # Also rename in mirror if it exists
        old_m = _mirror(old)
        new_m = _mirror(new)
        if old_m.exists():
            _ensure_parent(new_m)
            os.rename(old_m, new_m)

        # After successful save, and after successful rename, re-check mapping for the final file name
        try:
            # Detect gedit/temporary saves: rename from temp → real file
            if _is_temp_name(old) and not _is_temp_name(new):
                context = "write"  # treat this as a real save, not a rename
                # Update DB for the final file
                update_file_mapping_for_upper(str(new_p.resolve()), context=context)
                update_file_metadata(str(new_p.resolve()), context)

                # Emit the GDPR Write event for the real file
                self._emit_write_event(new)
                print(f"[GDPR] Sent Write event for final file {new} via Logger.log()")

                # (write/overwrite a file) Emit Collect event: data entering the system
                self._emit_collect_event(new)

                # Clear save-in-progress flag
                _save_in_progress_dirs.discard(os.path.dirname(new))

            else:
                context = "rename"

                # Update DB for final file name
                update_file_mapping_for_upper(str(new_p.resolve()), context=context, old_name=os.path.basename(old))
                update_file_metadata(str(new_p.resolve()), context)
                print(f"[DB] Mapped after {context} → {new}")

                # (rename a file) Emit Collect event: renamed file may now match a DS
                self._emit_collect_event(new)

        except Exception as e:
            print(f"[DB] Warn: mapping after rename failed for {new}: {e}")
    
        try:
            if new_p.is_file(): # only run LLM analysis for files only, not for folders
                print(f"[LLM] Running LLM analysis after rename for {new}")
                run_llm_analysis_and_update_db(str(new_p.resolve()))
        except Exception as e:
            print(f"[LLM] WARNING: LLM update after rename failed: {e}")

        return 0

    def write(self, path, data, offset, fh=None):
        return self._write(path, data, offset, fh)

    def unlink(self, path):
        p = _upper(path)
        if not p.exists():
            from errno import ENOENT
            raise OSError(ENOENT, "No such file or directory")

        _do_delete_file(path)
        return 0

    def statfs(self):
        from fuse import StatVfs
        st = StatVfs()
        st.f_bsize = 4096 # file system one block size (4096 bytes = 4 KB)
        st.f_blocks = 1024 # total # of blocks in file system  = filesystem size / block size
        st.f_bavail = 1024 # available blocks = how many free space
        st.f_files = 100 # total # of file slots = total # of inodes
        st.f_namemax = 255 # maximum filename length set to 255 characters (can be more)
        return st


# in the very beginning, when the filesystem is started:
# Rescan all files in /upper to (re)create missing mappings:
from gdprfs.db_utils import rescan_all_upper_files

print("[INIT] Running automatic rescan of existing /upper files...")
try:
    rescan_all_upper_files()
    print("[INIT] Rescan complete.")
except Exception as e:
    print(f"[INIT] Rescan failed: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 myfs.py <mountpoint>")
        sys.exit(1)
    
    fs = MyFS()
    fs.parse() # parse FUSE args
    import gc
    gc.collect() 
    
    def start_consent_poller():
        try:
            subprocess.Popen(
                ["python3", "/home/ann20010929/MA3/Building_a_GDPR-compliant_file_system/instrlib/external_consent_platform/poller.py"]
            )
            print("[INIT] Consent poller started in background.") # means this FS successfully launched the poller daemon via subprocess.Popen().
        except Exception as e:
            print(f"[INIT] Warning: failed to start poller: {e}")

    start_consent_poller() # start the consent poller in the background
    start_ingest_server(logger) # start the ingest HTTP server for Consent/Revoke events
    fs.main()               # enter service loop
