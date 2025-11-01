from pathlib import Path
from gdprfs.models import Person, File, Session
from datetime import datetime
import os

def _is_temp_name(fuse_path: str) -> bool:
    """Detect temporary filenames created by editors (e.g., gedit)."""
    name = os.path.basename(fuse_path)
    return (
        name.startswith(".goutputstream-")
        or name.endswith("~")
        or name.startswith(".#")
        or name.endswith(".swp")
    )

def _read_text_safe(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None  # for binary file or unreadable, return None, not ""

def rescan_all_upper_files():
    """Rescan all files in /upper to (re)create missing mappings."""
    upper_dir = Path("/var/lib/gdprfs/upper")
    for path in upper_dir.rglob("*"):
        if path.is_file():
            try:
                update_file_mapping_for_upper(str(path.resolve()), context="rescan")
            except Exception as e:
                print(f"[DB] Rescan warning for {path}: {e}", flush=True)

import time
# A small cache to remember recent writes and avoid immediate "read" overrides
_recent_writes = {}
WRITE_PROTECT_WINDOW = 1.0  # seconds
def update_file_metadata(file_path: str, last_action: str):
    """Update timestamps and last action for a file."""
    from gdprfs.models import File
    p = Path(file_path).resolve()
    key = str(p)  # use full absolute path as dictionary key

    if not p.exists():
        return

    # real filesystem timestamps
    stat = os.stat(p)
    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    accessed = datetime.fromtimestamp(stat.st_atime).strftime("%Y-%m-%d %H:%M:%S")
    now = time.time()

    with Session() as session:
        f = session.query(File).filter_by(file_id=p.name).first()
        if not f:
            # print(f"[DB] Warning: File {p.name} not found in DB for metadata update.")
            return
        
        # Always refresh absolute path (in case file was renamed/moved)
        f.abs_path = str(p)

        # --- Avoid overriding write with immediate read ---
        last_action_prev = f.last_action or ""
        print(f'{_recent_writes=}')
        if (
            last_action_prev == "write"
            and last_action == "read"
            and key in _recent_writes
            and (now - _recent_writes[key]) < WRITE_PROTECT_WINDOW
        ):
            print(f"[DB] Skipping immediate read override for {p.name}")
        else:
            f.last_action = last_action
        print(f'{f.last_action=}')

        if last_action == "write":
            _recent_writes[key] = now # record write time
            f.modified_at = modified

        f.accessed_at = accessed
        # f.last_action = last_action
        session.commit()
        print(f"[DB] Updated metadata for {p.name} (last_action={last_action})")

def mark_file_deleted(file_path: str):
    """Mark a file as deleted in the database."""
    from gdprfs.models import File
    p = Path(file_path)
    file_id = p.name
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with Session() as session:
        f = session.query(File).filter_by(file_id=file_id).first()
        if f:
            f.deleted = 1 # mark as deleted with the deleted flag
            f.last_action = "delete"
            f.modified_at = now
            f.accessed_at = now
            session.commit()
            print(f"[DB] Marked {file_id} as deleted at {now}")

def update_file_mapping_for_upper(abs_upper_path: str, context: str = "rescan", old_name: str = None):
    """
    1. Reads the file contents (in /upper),
    2. Checks if a `username` (first_name + last_name OR either one) appears,
    3. Creates/updates the Person ↔ File mapping if so.
    """

    # ignore temp files
    if _is_temp_name(abs_upper_path):
        print(f"[DB] Ignoring temporary file {abs_upper_path}")
        return

    p = Path(abs_upper_path)
    if not p.exists() or not p.is_file():
        return

    content = _read_text_safe(p)
    if content is None: # binary or unreadable file; but allow empty text files to still be registered in DB
        return
    
    stat = os.stat(p)
    created = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    accessed = datetime.fromtimestamp(stat.st_atime).strftime("%Y-%m-%d %H:%M:%S")
        
    file_id = p.name # we map on the file name (simple prototype)

    with Session() as session:
        # 1) Ensure File entry exists:
        # f = session.query(File).filter_by(file_id=file_id).first()
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
        
        # session.flush()

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
                        print(f"[DB] Linked {person.first_name} {person.last_name} ↔ {file_id}")

        session.commit()
        print(f"[DB] Updated mapping for {file_id} (context={context})")
