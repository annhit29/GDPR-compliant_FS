from errno import EACCES
import getpass
import threading
from fuse import Fuse
import fuse
fuse.fuse_python_api = (0, 2) 

from gdprfs.llm import run_llm_analysis_and_update_db
from gdprfs.settings import INSTRLIB_EXE, INSTRLIB_FORMULA, INSTRLIB_LOG, INSTRLIB_SIG
from instrlib.instrument import Instrument
from instrlib.logger import Logger
from instrlib.pdp import EnfGuard
from instrlib.schema import Schema
from instrlib.pep import PEP, InstrumentationMapping
from instrlib.event import Event, Functional
import os, shutil
from pathlib import Path
from gdprfs.db_utils import Session, sync_users_from_external, update_file_mapping_for_upper, update_file_metadata, mark_file_deleted, _is_temp_name
from gdprfs.models import File, Person
import yaml
import json
import subprocess # so the poller runs independently of the FUSE main loop, i.e. one daemon for FUSE, one daemon for poller
from pypdf import PdfReader, PdfWriter
from io import BytesIO

PDF_CACHE = {}
REDACTED_TEMPLATE = Path("/var/lib/gdprfs/redacted_template.pdf")
# todo: 0) d'autres formats de fichiers <- redacted qd lecture mm pour les txt (suppression handler)
# 1) filename dit qqch aussi
# 2) folder-level <- soit on lit le nom du dossier, soit on declare explicitement le PII (cf 3))
# 3) declarer manuellement le PII (dans le internal interface, par l'utilisateur interne) <- inspiration: .gitignore

# run as root to have access to /dev/fuse and /var/lib/gdprfs
UPPER_DIR  = Path("/var/lib/gdprfs/upper")
MIRROR_DIR = Path("/var/lib/gdprfs/mirror")

# Make sure the directories exist and are private
UPPER_DIR.mkdir(parents=True, exist_ok=True)
MIRROR_DIR.mkdir(parents=True, exist_ok=True)
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
# to keep things clean, modular, and reusable

def _upper(path: str) -> Path:
    """
    Map FUSE path to the real file path in UPPER_DIR
    aka Find the real file in the upper dir
    """
    return (UPPER_DIR / path.lstrip("/")).resolve()

def _mirror(path: str) -> Path:
    """
    Map FUSE path to the real file path in MIRROR_DIR
    aka Find the real file in the mirror dir
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
    Then you delete the corresponding trusted copy in /mirror too
    (or mark it deleted if you want versioning later).
    """
    dst = _mirror(fuse_path)
    if dst.exists():
        dst.unlink()

def replay_from_consent_db(logger):
    """
    On startup, all active events are re-injected into the enforcer, so that the enforcer has the latest event states.
    """
    import requests
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

        for row in rows:
            uid = row["uid"]
            purpose = row["purpose"]
            status = row["status"].lower()

            ev_name = state_to_event.get(status)

            if not ev_name:
                print(f"[INIT] Unknown status: {status}, skipping...")
                continue

            expected_nb_args = len(schema.mapping.get(ev_name, [])) # number of args expected for an event (triggered by data subjects) to take (2 for Consent/Revoke, 1 for RequestAccess/RequestErasure)

            if expected_nb_args == 2: # if event has 2 args (e.g. Consent, Revoke)
                evt = Event(ev_name, uid, purpose)
            else:
                evt = Event(ev_name, uid) # it's 1 arg (e.g. RequestAccess, RequestErasure)

            logger.log([evt], threading.Event(), False)
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
                    # same fallback you already use
                    pseudo = (first[:1] + last) if (first or last) else "anonymous"
                    uids.append(pseudo)

    return uids

def _get_file_and_user(path: str):
    """Return (file_id, list of uids) for the file at path, if any."""
    with Session() as session:
        file_obj = session.query(File).filter(File.abs_path == str(Path(path).resolve())).first()
        if not file_obj:
            return None, []
        
        uids = []
        for person in file_obj.people:
            # print(f"[DEBUG] Linked Person: uid={person.uid}, first={person.first_name}, last={person.last_name}")
            # if person and person.uid: # if person exists and has a uid
            #     uids.append(person.uid)
            if person.uid:
                uids.append(person.uid)
            else:
                # fallback ID for page-based enforcement
                first = (person.first_name or "").lower().replace(" ", "")
                last  = (person.last_name or "").lower().replace(" ", "")
                uid = first[:1] + last if first or last else "anonymous"
                uids.append(uid)

        # print(f"[DEBUG] Returning from _get_file_and_user: fid={file_obj.file_id}, uids={uids}")
        return file_obj.file_id, uids


def events_for_path(path: str, event_type: str):
    """
    Return a list of Event objects (possibly multiple if file has several owners).
    event_type ∈ {'Use', 'Collect', 'Delete'}
    """
    fid, uid = _get_file_and_user(_upper(path))
    # Skip temporary names
    if _is_temp_name(path):
        return [Event('Collect', 'tempfile', 'marketing')]
    if not fid:
        fid = f"unknown-{os.path.basename(path)}"
    if not uid:
        uid = "anonymous"
    if event_type == 'Use':
        return [Event('Use', fid, uid)]
    elif event_type == 'Collect':
        return [Event('Collect', fid, 'marketing')]
    elif event_type == 'Delete':
        return [Event('Delete', fid)]
    else:
        return []


def events_for_read(path):
    """Return appropriate events for read(), skip .goutputstream temporary files."""
    base = os.path.basename(path)

    # if _should_ignore():
    #     print(f"[DEBUG] Ignoring read from system process for {base}")
    #     return []
    # Case 1: temporary gedit files (.goutputstream-XXXX)
    if base.startswith(".goutputstream-"):
        # print(f"[DEBUG] Skipping Collect for temporary file: {path}")
        return []  # No event, coz final Collect will be emitted at rename()

    # Case 2: normal file read → Use(fid, purpose, uid)
    fid, uids = _get_file_and_user(_upper(path))
    fid = fid or f"unknown-{base}"

    events = []
    with Session() as session:
        file_obj = session.query(File).filter(File.abs_path == str(_upper(path).resolve())).first()
        # print(f'{file_obj=}')
        # print(f'{file_obj.people=}')

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
            # events.append(Event("Use", fid, "marketing", uid))

    print(f"[GDPR] Emitting {len(events)} Use events for {fid}: {[e.args for e in events]}")
    return events

# ========== SCHEMA ==========
schema = Schema()
schema.add("UseNonPII", [str, str]) # for reads of non-PII files
schema.add('Use', [str, str]) # for reads
schema.add('Delete', [str])    # for deletes
schema.add('Collect', [str, str]) # for writes

schema.add('StartSession', [str, str, str])
schema.add('StopSession', [str])

schema.add('Consent', [str, str]) # for consent events
schema.add('Revoke', [str, str]) # for revoke consent events
schema.add('RequestAccess', [str]) # request all DS data events from the FS
schema.add('RequestErasure', [str]) # request erasure of all DS data events in the FS



# ========== HANDLERS ==========
def none_handler(event_name, event_args, response, *args, **kwargs):
    """
    Python side  =/= Enforcer side
    The none_handler means "do nothing" in the python side (if I wanna return or print sth on the terminal).
    and the enforcer is actually suppressing or causing a file operation.
    """
    return None

suppression_handlers = {('Use'): none_handler}

causation_handlers = {('UseNonPII'): none_handler,
                        ('Delete'): none_handler,
                        ('Collect'): none_handler,
                      ('Consent'): none_handler,
                        ('Revoke'): none_handler,
                        ('RequestAccess'): none_handler,
                        ('RequestErasure'): none_handler
                      }

# ========== MAPPINGS ==========
def read_mapping(action):  
    print(f'[read_mapping DEBUG] {str(action)}')
    return Event('Use', str(action), 'userid1')
# todo: or the following?
# def read_mapping(action):
    # print("[DEBUG InstrumentationMapping] remapping event", action)
    # return Event('Use', str(action), 'analytics')  # different purpose!

def write_mapping(action): return Event('Collect', str(action), 'marketing')
def unlink_mapping(action): return Event('Delete', str(action))

instrumentation_mapping = InstrumentationMapping({
    'read': read_mapping,
    'write': write_mapping,
    'unlink': unlink_mapping
    # 'Use': lambda x:x
})

# ========== PEP ==========
def events_for_read_or_skip(path):
    # If normal files => keep old behavior
    if not str(path).lower().endswith(".pdf"):
        return events_for_read(path)
    # If PDF => skip full-file Use events
    return []

pep = PEP(
    mapping={
        ('MyFS', 'read'): Functional('Use', lambda path, *a, **kw: events_for_read_or_skip(path)),
        ('MyFS', 'write'): Functional('Collect', lambda path, *a, **kw: events_for_path(path, 'Collect')),
        # ('MyFS', 'unlink'): Functional('Delete', lambda path, *a, **kw: events_for_path(path, 'Delete')),
    },
    suppression_handlers=suppression_handlers,
    causation_handlers=causation_handlers#,
    # instrumentation_mapping=instrumentation_mapping
    # todo: francois said use suppression_handlers, causation_handlers, and instrumentation_mapping, then no need mapping?? see miniTwitter_rv/twitt/enforcer.py
)

pdp = EnfGuard(INSTRLIB_EXE, INSTRLIB_SIG, INSTRLIB_FORMULA, log_file=INSTRLIB_LOG)

# logger = Logger(name="gdprfs")
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
        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                # --- Branch 1: handle Consent/Revoke events ---

                if self.path == "/ingest":
                    # length = int(self.headers.get("Content-Length", "0"))
                    # payload = json.loads(self.rfile.read(length) or b"{}")
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
                        evt = Event("StartSession", uid, purpose, reason)

                    # CASE 2: StopSession(uid)
                    elif kind == "StopSession":
                        evt = Event("StopSession", uid)

                    # CASE 3: Consent/Revoke or others (already handled)
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

                # --- Branch 2: handle user sync trigger ---
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
                if issubclass(target, FuseBase):# to avoid overwriting __getattribute__ and __setattribute__ of Fuse-based classes
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
        print(f"[DEBUG write] called with path={path}, data = {data}, data_len={len(data)}, offset={offset}", flush=True)
        p = _upper(path)

        # Ensure the parent folder exists
        _ensure_parent(p)
    
        # Write to the real upper file
        with open(p, "r+b" if p.exists() else "wb") as f:
            f.seek(offset)
            f.write(data) # data written into the real file in /upper
            f.flush() # flush to disk

        # --- skip temp files ---
        if not _is_temp_name(path):
            # print("before trying to update mapping in _write")
            try:
                update_file_mapping_for_upper(str(p.resolve()), context="write")
                update_file_metadata(str(p.resolve()), "write")
                
                # print("PRINT A COLLECT in _write")
                # self._emit_collect_event(path) # solves the issue of no Collect event for direct writes ending with numbers
            except Exception as e:
                print(f"[DB] Warn: mapping update failed for {p}: {e}")
        else:
            print(f"[DB] Skipped mapping for temporary file: {path}")

        # After writing, sync to mirror
        _sync_to_mirror(path)
        print(f"[WRITE] path={path} → synced to mirror")

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

    def _emit_collect_event(self, path: str):
        """Emit a GDPR Collect event for a file when a write happens but no Collect event is triggered."""
        try:
            fid, _ = _get_file_and_user(_upper(path))
            fid = fid or f"unknown-{os.path.basename(path)}"
            evt = Event('Collect', fid, 'marketing')
            logger.log([evt], threading.Event(), False)
            print(f"[GDPR] Fallback Collect event emitted for {path}")
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

        # 2) Figure out base fid + uids for this file
        # fid_base, uids = _get_file_and_user(abspath)
        fid_base, _ = _get_file_and_user(abspath)
        if not fid_base:
            fid_base = os.path.basename(abspath)
        # if not uids:
        #     uids = ["anonymous"]

        writer = PdfWriter()

        # 3) For each page: ask enforcer, then add original or blank page
        for idx, page in enumerate(reader.pages):
            page_fid = f"{fid_base}/page-{idx}"
            page_text = page.extract_text() or ""
            uids = _uids_from_page_text(page_text)


            if not uids:
                # page has no personal data → no Use event, no suppression
                writer.add_page(page)
                continue

            events = [Event("Use", page_fid, uid) for uid in uids]

            cau, sup, _, _ = logger.log(events, threading.Event(), False)

            if sup:
                print(f"[GDPR] Page {idx} suppressed → inserting blank page")
                # writer.add_blank_page(width=595, height=842)
                red_page = self._make_redacted_page()
                red_reader = PdfReader(BytesIO(red_page))
                writer.add_page(red_reader.pages[0])
            else:
                writer.add_page(page)

        # 4) Serialize redacted PDF once
        buf = BytesIO()
        writer.write(buf)
        data = buf.getvalue()

        PDF_CACHE[abspath] = {"redacted_bytes": data}
        return data

    def getattr(self, path): #v
        """
        Return the attributes of a file or directory.
        (e.g. size, permissions, owner, timestamps)
        Called whenever Linux does 'ls', 'stat', etc.
        """
        # print(f"[DEBUG getattr] called with path={path}", flush=True)

        from fuse import Stat
        from errno import ENOENT

        # Find the real file inside /upper
        real_path = _upper(path)

        if not real_path.exists():
            # print("ghost file")
            '''
            These ghost files are simply there coz the FS is asking if these ghost filenames exist in the FS, not because it's creating them.
            They only show up in the logs since each “Does this file exist?” question triggers a check inside the FUSE filesystem.
            '''
            raise OSError(ENOENT, "No such file or directory")

        # Get the actual file info from disk
        s = real_path.lstat()

        # Fill the FUSE Stat structure
        st = Stat()
        st.st_mode  = s.st_mode      # file type + permissions
        st.st_nlink = s.st_nlink     # number of hard links
        st.st_size = s.st_size      # file size in bytes
        st.st_uid   = s.st_uid       # owner user id (still needed for Linux)
        st.st_gid   = s.st_gid       # group id
        st.st_atime = int(s.st_atime)  # access time
        st.st_mtime = int(s.st_mtime)  # modification time
        st.st_ctime = int(s.st_ctime)  # change/creation time

        # # --- FIX FOR PDF REDACTION ---
        # if str(real_path).lower().endswith(".pdf"):
        #     # Ensure redacted PDF is generated
        #     data = self._get_or_build_redacted_pdf(path)
        #     st.st_size = len(data)
        #     return st

        # # Non-PDF: return real size
        # st.st_size = s.st_size

        return st

    def readdir(self, path, offset): #v
        print(f"[DEBUG readdir] called with path={path}", flush=True)
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
        print("in open")

        # allow access if the path exists in /upper
        # print(f"[DEBUG open] called with path={path}, flags={flags}", flush=True)
        p = _upper(path)
        if p.exists():
            # PDF cache invalidation
            if str(p).lower().endswith(".pdf"):
                PDF_CACHE.pop(p, None)
            update_file_mapping_for_upper(str(p.resolve()), context="open")
            update_file_metadata(str(p.resolve()), "open")
            return 0
        from errno import ENOENT
        raise OSError(ENOENT, "No such file or directory")

    def read(self, path, size, offset, fh=None):
        print("read file")

        if isinstance(size, (bytes, bytearray)): #if size is data instead of int
            print(f"[WRITE] Misrouted write() detected: redirecting safely to raw write for {path}")
            return self._write(path, size, offset, fh)

        p = _upper(path)
        if not p.is_file():
            from errno import ENOENT
            raise OSError(ENOENT, "No such file or directory")
        
        # =========== CASE1: pdf with page-based Use event ===========
        if str(p).lower().endswith(".pdf"):
            print("[PDF] Page-based enforcement for PDF read")

            redacted_bytes = self._get_or_build_redacted_pdf(path)

            # still update DB mapping + metadata for access stats
            update_file_mapping_for_upper(str(p.resolve()), context="read")
            update_file_metadata(str(p.resolve()), "read")

            return redacted_bytes[offset:offset + size]

        # =========== CASE2: non-pdf files ===========        
        # return only the requested slice, as bytes
        with open(p, "rb") as f: # the file is being read from p i.e. from /upper 
            f.seek(offset)
            # print(f"size: {size}")
            data = f.read(size)

        print(f"[READ] path={path} reading from {p}, {len(data)} bytes, size={size}, offset={offset}, returning={data}")
        
        update_file_mapping_for_upper(str(p.resolve()), context="read") 
        update_file_metadata(str(p.resolve()), "read") # update timestamps + last_action

        return data


    def create(self, path, mode, fi=None):
        """Create a new empty file in /upper and sync to /mirror."""
        p = _upper(path)
        _ensure_parent(p)
        # print(f"[CREATE] Creating new file {p}")

        # Create file in upper layer
        # I opened the file, now it exists, even if I didn’t write on it yet.
        with open(p, "wb") as f:
            pass # create empty file

        # Sync to mirror
        _sync_to_mirror(path)
        print(f"[CREATE] Synced {p} → mirror")
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
        # print("I'm in the rename function")
        # print(f"[DEBUG rename] called with old={old}, new={new}", flush=True)
        old_p = _upper(old)
        new_p = _upper(new)
        # print(f"[RENAME] {old_p} → {new_p}")

        if not old_p.exists():
            from errno import ENOENT
            raise OSError(ENOENT, f"No such file: {old}")

        # ---------- GDPR ENFORCEMENT FOR FINAL SAVE ----------
        # gedit pattern: .goutputstream-XXXX  -> real filename
        if os.path.basename(old).startswith(".goutputstream-") and not _is_temp_name(new):
            # Ask: is Use(fid, uid) allowed for this final file?
            events = events_for_read(new)
            cau_flag, sup_flag, _, _ = logger.log(events, threading.Event(), False)
            print(f"[GDPR] rename check for {new}: cau_flag={cau_flag}, sup_flag={sup_flag}")

            if sup_flag:
                print(f"[GDPR] Blocking final save for {new} due to missing consent")
                # IMPORTANT: do NOT rename on disk, just fail
                raise OSError(EACCES, "GDPR policy: write requires external consent")
        # ------------------------------------------------------


        _ensure_parent(new_p)
        os.rename(old_p, new_p)

        # Also rename in mirror if it exists
        old_m = _mirror(old)
        new_m = _mirror(new)
        if old_m.exists():
            _ensure_parent(new_m)
            os.rename(old_m, new_m)

        # print(f"[RENAME] Synced {old_p} → {new_p} and {old_m} → {new_m}")

        # After successful save, and after successful rename, re-check mapping for the final file name
        try:
            # Detect gedit/temporary saves: rename from temp → real file
            if os.path.basename(old).startswith(".goutputstream-") and not _is_temp_name(new):
                context = "write"  # treat this as a real save, not a rename
                # Update DB for the final file
                update_file_mapping_for_upper(str(new_p.resolve()), context=context)
                update_file_metadata(str(new_p.resolve()), context)
                # print(f"[DB] Updated mapping for final save {new}")

                # Emit the GDPR Collect event for the real file
                self._emit_collect_event(new)
                print(f"[GDPR] Sent Collect event for final file {new} via Logger.log()")

            else:
                context = "rename"

                # Update DB for final file name
                update_file_mapping_for_upper(str(new_p.resolve()), context=context, old_name=os.path.basename(old))
                update_file_metadata(str(new_p.resolve()), context)
                print(f"[DB] Mapped after {context} → {new}")

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
        print("I am in the 'real' write function")
        return self._write(path, data, offset, fh)

    def unlink(self, path):
        p = _upper(path)
        if not p.exists():
            from errno import ENOENT
            raise OSError(ENOENT, "No such file or directory")

        # Delete in upper and mirror
        os.unlink(p) # delete from upper
        _delete_from_mirror(path) # delete from mirror
        print(f"[UNLINK] path={path} → removed from upper and mirror")

        # Update the database to reflect the deletion
        try:
            mark_file_deleted(str(p.resolve()))
        except Exception as e:
            print(f"[DB] Warning: failed to log deletion for {p}: {e}")

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
    gc.collect() # clean up the memory (eg: files already deleted for a very long time) before mounting
    
    def start_consent_poller():
        try:
            subprocess.Popen(
                ["python3", "/home/ann20010929/MA3/Building_a_GDPR-compliant_file_system/instrlib/external_consent_platform/poller.py"]#,
            )
            print("[INIT] Consent poller started in background.") # means this FS successfully launched the poller daemon via subprocess.Popen().
        except Exception as e:
            print(f"[INIT] Warning: failed to start poller: {e}")

    start_consent_poller() # start the consent poller in the background
    start_ingest_server(logger) # start the ingest HTTP server for Consent/Revoke events
    fs.main()               # enter service loop