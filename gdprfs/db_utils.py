from ast import pattern
from pathlib import Path
from gdprfs.models import Person, File, Session
from datetime import datetime
import os
import subprocess
from docx import Document
from odf.opendocument import load as load_odt
from odf.text import P
import pandas as pd
from fnmatch import fnmatch

GDPROWNER_PATH = Path("/var/lib/gdprfs/.gdprowner")

def load_gdprowner():
    """
    Parse lines like:
       jdoe: doe/**
       aturing: research/*
    Returns a list of (uid, pattern)
    """
    rules = []
    if GDPROWNER_PATH.exists():
        for line in GDPROWNER_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            uid, pattern = line.split(":", 1)
            rules.append( (uid.strip(), pattern.strip()) )
    return rules

GDPROWNER_RULES = load_gdprowner()# global cache. This is loaded only once at startup of the FUSE daemon.
print(f"[INIT] Loaded gdprowner rules: {GDPROWNER_RULES}") # [INIT] Loaded gdprowner rules: [('jdoe', 'doe/**')]

# def reload_gdprignore():
#     """Update the global variable in-place, so every function using GDPRIGNORE_PATTERNS automatically sees the updated patterns."""
#     global GDPRIGNORE_PATTERNS
#     GDPRIGNORE_PATTERNS = load_gdprignore()

def _is_temp_name(fuse_path: str) -> bool:
    """Detect temporary filenames created by editors (e.g., gedit)."""
    name = os.path.basename(fuse_path)
    return (
        name.startswith(".goutputstream-")
        or name.endswith("~") # editor temp
        or name.startswith(".#")
        or name.endswith(".swp")

        or name.startswith("~$") # MS Office temporary file
        or name.startswith(".~lock") # LibreOffice lock file
        or name.endswith(".tmp") # generic temp
        or name.endswith(".csv#") # LibreOffice temp variant
    )

def _manual_owner_for_path(p: Path):
    rel = str(p).replace("/var/lib/gdprfs/upper/", "")
    for uid, pattern in GDPROWNER_RULES:
        if fnmatch(rel, pattern):
            return uid
    return None

def _uids_from_path_string(path_str: str, session):
    """
    Infer personal data purely from the *path* (filename + folders).
    Returns a list of Person objects.
    """
    path_lc = path_str.lower()
    persons = []

    for person in session.query(Person).all():
        first = (person.first_name or "").strip().lower()
        last  = (person.last_name  or "").strip().lower()
        full = f"{first} {last}".strip()

        if not first and not last:
            continue

        # Match full name, or first, or last, in path
        if full and full in path_lc:
            persons.append(person)
        elif first and first in path_lc:
            persons.append(person)
        elif last and last in path_lc:
            persons.append(person)

    return persons

def _uids_from_folder(p: Path, session):
    """This checks only the folder name (not the full path)."""
    folder = p.parent.name.lower()
    return _uids_from_path_string(folder, session)

def _uids_from_filename(p: Path, session):
    """This checks only the filename, not folders."""
    return _uids_from_path_string(p.name.lower(), session)

def _extract_pdf_to_text(abs_path: str) -> str:
    """
    Extract text from a PDF using pdftotext.
    Method used by the LLM + DB mapping.
    """
    try:
        out = subprocess.run(
            ["pdftotext", "-layout", abs_path, "-"],
            capture_output=True,
            text=True
        )
        return out.stdout
    except Exception as e:
        print("[PDF ERROR]", e)
        return ""

def _extract_docx_to_text(abs_path: str) -> str:
    """Extract visible text from a DOCX file."""
    try:
        doc = Document(abs_path)
        paras = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paras)
    except Exception as e:
        print("[DOCX ERROR]", e)
        return ""

def _extract_odt_to_text(abs_path: str) -> str:
    """Extract visible text from an ODT file."""
    try:
        doc = load_odt(abs_path)
        paras = doc.getElementsByType(P)
        out = []
        for p in paras:
            out.append("".join(
                n.data for n in p.childNodes if hasattr(n, "data")
            ))
        return "\n".join(out)
    except Exception as e:
        print("[ODT ERROR]", e)
        return ""

def _extract_excel_to_text(abs_path: str) -> str:
    """Extract text from the first sheet of an Excel file."""
    try:
        df = pd.read_excel(abs_path, dtype=str)
        rows = []
        for _, row in df.iterrows():
            rows.append(" ".join(str(x) for x in row.values if str(x) != "nan"))
        return "\n".join(rows)
    except Exception as e:
        print("[XLSX ERROR]", e)
        return ""

def _get_text_for_matching(p: Path) -> str | None:
    """
    Return plaintext for name matching, from any supported format.
    Never modifies the underlying file; only uses extractors.
    """
    ext = p.suffix.lower()

    # print(f"[DB][EXTRACT] Processing file: {p} (ext={ext})")

    # Try reading as plain text ONLY for obvious text formats
    if ext in [".txt", ".csv", ".json", ".md", ".log"]:
        # print("[DB][EXTRACT] Trying UTF-8 plain text read")
        try:
            txt = p.read_text(encoding="utf-8")

            # print("[DB][EXTRACT] UTF-8 plain text read SUCCESS")
            # print("[DB][EXTRACT] Preview (first 200 chars):")
            # print(txt[:200])
            return txt # is the txt or csv or other listed above format
        except UnicodeDecodeError:
            print("[DB][EXTRACT] UTF-8 plain text read FAILED, falling back")
            pass

    # Fall back to rich extractors for binary formats
    if ext == ".pdf":
        # print("[DB][EXTRACT] Using PDF extractor")
        text = _extract_pdf_to_text(str(p))
        # print("[DB][EXTRACT] PDF extractor output preview (first 200 chars):")
        # print(text[:200])
        return text

    if ext == ".docx":
        return _extract_docx_to_text(str(p))
    if ext == ".odt":
        print("[DB][EXTRACT] Using ODT extractor")
        text = _extract_odt_to_text(str(p))
        print("[DB][EXTRACT] ODT extractor output preview (first 200 chars):")
        print(text[:200])
        return text
    if ext in [".xls", ".xlsx"]:
        return _extract_excel_to_text(str(p))

    # Unsupported binary format
    print("[DB][EXTRACT] Unsupported file type → returning None")
    return None

def rescan_all_upper_files():
    """Rescan all files in /upper to (re)create missing mappings."""
    upper_dir = Path("/var/lib/gdprfs/upper")
    for path in upper_dir.rglob("*"):
        if path.is_file():
            try:
                update_file_mapping_for_upper(str(path.resolve()), context="rescan")
            except Exception as e:
                print(f"[DB] Rescan warning for {path}: {e}", flush=True)

def update_file_metadata(file_path: str, last_action: str):
    """Update timestamps and last action for a file."""
    p = Path(file_path)

    if not p.exists():
        return

    # real filesystem timestamps
    stat = os.stat(p)
    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    accessed = datetime.fromtimestamp(stat.st_atime).strftime("%Y-%m-%d %H:%M:%S")

    with Session() as session:
        f = session.query(File).filter_by(file_id=p.name).first()
        if not f:
            # print(f"[DB] Warning: File {p.name} not found in DB for metadata update.")
            return
        
        # Always refresh absolute path (in case file was renamed/moved)
        f.abs_path = str(p)

        if last_action == "write":
            f.modified_at = modified
        f.accessed_at = accessed
        f.last_action = last_action
        session.commit()
        print(f"[DB] Updated metadata for {p.name} (last_action={last_action})")

def mark_file_deleted(file_path: str):
    """Completely remove the file entry from the database when it's deleted in /upper."""
    from gdprfs.models import File
    p = Path(file_path)
    file_id = p.name

    with Session() as session:
        f = session.query(File).filter_by(file_id=file_id).first()
        if f:
            session.delete(f)
            session.commit()
            print(f"[DB] Deleted DB record for {file_id}")

def update_file_mapping_for_upper(abs_upper_path: str, context: str = "rescan", old_name: str = None):
    """
    Update the database mapping for a file in /upper, based on its path and content.
    Steps:
    1. Manual owner override by internal person (gdprowner)
    2. Folder-level ownership
    3. Filename-level ownership
    4. Content-based ownership inference
    """

    # 0. Ignore temporary editor files
    if _is_temp_name(abs_upper_path):
        print(f"[DB] Ignoring temporary file {abs_upper_path}")
        return

    p = Path(abs_upper_path)
    file_id = p.name

    # 1. Manual owner override by internal person (gdprowner)
    owner_uid = _manual_owner_for_path(p)
    if owner_uid:
        # avoid os.stat() crash if file does not exist
        if not p.exists():
            print(f"[GDPROWNER] Path matched rule but file missing: {p}")
            return

        with Session() as session:
            print(f"[GDPROWNER] Manual override by internal person, in path {p}: assigning {file_id} → {owner_uid} (skips folder/filename/content)")

            f = session.query(File).filter_by(file_id=file_id).first()

            # ensure File exists
            if not f:
                stat = os.stat(p)
                created = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                accessed = datetime.fromtimestamp(stat.st_atime).strftime("%Y-%m-%d %H:%M:%S")

                f = File(
                    file_id=file_id,
                    abs_path=str(p.resolve()),
                    created_at=created,
                    modified_at=modified,
                    accessed_at=accessed,
                    last_action=context
                )
                session.add(f)

            # assign manual owner
            owner = session.query(Person).filter_by(uid=owner_uid).first()
            if owner and f not in owner.files:
                owner.files.append(f)

            session.commit()
            print(f"[GDPROWNER] DONE: {file_id} is now owned by Person(uid='{owner_uid}') (manual override by internal person in path {p})")

        return  # STOP here (manual override wins)

    # If file does not exist → nothing to do
    if not p.exists() or not p.is_file():
        return

    # Normal DB logic
    stat = os.stat(p)
    created = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    accessed = datetime.fromtimestamp(stat.st_atime).strftime("%Y-%m-%d %H:%M:%S")

    with Session() as session:

        # Ensure file entry exists
        f = None
        if context == "rename" and old_name:
            f = session.query(File).filter_by(file_id=old_name).first()
            if f:
                print(f"[DB] Detected rename {old_name} → {file_id}")
                f.file_id = file_id
                f.abs_path = str(p.resolve())
        
        if not f:
            f = session.query(File).filter_by(file_id=file_id).first()

        if not f: # if not exists, create it
            f = File(
                file_id=file_id,
                abs_path=str(p.resolve()),
                created_at=created,
                modified_at=modified,
                accessed_at=accessed,
                last_action=context
            )
            session.add(f)
        else:
            # update existing metadata
            f.abs_path = str(p.resolve())
            f.modified_at = modified
            f.accessed_at = accessed
            f.last_action = context

        # 2. Folder-level ownership
        folder_persons = _uids_from_folder(p, session)
        if folder_persons:
            for person in folder_persons:
                if f not in person.files:
                    person.files.append(f)
                    print(f"[lazy DB folder] Linked (folder) {person.first_name} {person.last_name} ↔ {file_id}")

            # IMPORTANT: stop here: coz no need to analyze contents, coz path reveals PII
            session.commit()
            print(f"[lazy DB folder] Finished mapping for folder `{p.parent.name}` ({person.uid} ↔ {file_id}, context={context}), folder-based only")
            return   # <--- STRONG INHERITANCE: STOP HERE

        # 3. Filename-level ownership
        filename_persons = _uids_from_filename(p, session)
        if filename_persons:
            for person in filename_persons:
                if f not in person.files:
                    person.files.append(f)
                    print(f"[DB filename] Linked (filename) {person.first_name} {person.last_name} ↔ {file_id}")
            
            # IMPORTANT: stop here: coz no need to analyze contents, coz path reveals PII
            session.commit()
            print(f"[DB filename] Finished mapping for {file_id} (context={context}), filename-based only")
            return   # <--- STRONG INHERITANCE: STOP HERE

        # 4. fallback: infer PII from file content (only if folder+filename gave nothing)
        content = _get_text_for_matching(p)
        if content is None: # binary or unreadable file; but allow empty text files to still be registered in DB
            return

        if content.strip():
            # 2) Loop over known users (Person):
            people = session.query(Person).all()

            # naive case-insensitive search
            lc = content.lower()
            for person in people:
                first = (person.first_name or "").strip().lower()
                last  = (person.last_name  or "").strip().lower()
                full = f"{first} {last}".strip()

                if not first and not last:
                    continue

                # simple case: full name, or first or last
                if full in lc or first in lc or last in lc:
                    if f not in person.files:
                        person.files.append(f)
                        print(f"[DB file content] Linked {person.first_name} {person.last_name} ↔ {file_id}")

        session.commit()
        print(f"[DB file content] Updated mapping for {file_id} (context={context}, content-based)")

def sync_users_from_external():
    """
    Synchronize users from the external consent platform to the local GDPRFS database.
    """
    import requests
    BASE_URL = "http://127.0.0.1:5000"
    try:
        res = requests.get(f"{BASE_URL}/api/users")
        users = res.json()
        print(f"[INIT] Syncing {len(users)} users to local DB...")

        with Session() as session:
            for u in users:
                uid = u["uid"]
                first = u["first_name"]
                last = u["last_name"]

                # Try to find an existing person: either by uid or by same name
                existing = session.query(Person).filter(
                    (Person.uid == uid) |
                    ((Person.first_name == first) & (Person.last_name == last))
                ).first()

                if existing:
                    existing.uid = uid
                    existing.registered = True
                    print(f"[DB] Upgraded existing person → uid={uid}, name={first} {last}")
                else:
                    new_p = Person(uid=uid, first_name=first, last_name=last, registered=True)
                    session.add(new_p)
                    print(f"[DB] Added new registered user: {first} {last} ({uid})")

            session.commit()
        print("[INIT] User sync complete.")
    except Exception as e:
        print(f"[INIT] Failed to sync users: {e}")
