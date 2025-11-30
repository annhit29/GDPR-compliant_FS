from pathlib import Path
from gdprfs.models import Person, File, Session
from datetime import datetime
import os
import subprocess
from docx import Document
from odf.opendocument import load as load_odt
from odf.text import P
import pandas as pd

def _is_temp_name(fuse_path: str) -> bool:
    # print("in _is_temp_name")
    """Detect temporary filenames created by editors (e.g., gedit)."""
    name = os.path.basename(fuse_path)
    return (
        name.startswith(".goutputstream-")
        or name.endswith("~") # editor temp
        or name.startswith(".#")
        or name.endswith(".swp")

        #todo 10h11: testing
        or name.startswith("~$") # MS Office temporary file
        or name.startswith(".~lock") # LibreOffice lock file
        or name.endswith(".tmp") # generic temp
        or name.endswith(".csv#") # LibreOffice temp variant
    )

def _extract_pdf_to_text(abs_path: str) -> str:
    """Extract text from a PDF using pdftotext."""
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

# def _extract_docx_to_text(abs_path: str) -> str:
#     """Extract visible text from a DOCX file."""
#     try:
#         doc = Document(abs_path)
#         paras = [p.text for p in doc.paragraphs if p.text.strip()]
#         return "\n".join(paras)
#     except Exception as e:
#         print("[DOCX ERROR]", e)
#         return ""

# def _extract_odt_to_text(abs_path: str) -> str:
#     """Extract visible text from an ODT file."""
#     try:
#         doc = load_odt(abs_path)
#         paras = doc.getElementsByType(P)
#         out = []
#         for p in paras:
#             out.append("".join(
#                 n.data for n in p.childNodes if hasattr(n, "data")
#             ))
#         return "\n".join(out)
#     except Exception as e:
#         print("[ODT ERROR]", e)
#         return ""

# def _extract_excel_to_text(abs_path: str) -> str:
#     """Extract text from the first sheet of an Excel file."""
#     try:
#         df = pd.read_excel(abs_path, dtype=str)
#         rows = []
#         for _, row in df.iterrows():
#             rows.append(" ".join(str(x) for x in row.values if str(x) != "nan"))
#         return "\n".join(rows)
#     except Exception as e:
#         print("[XLSX ERROR]", e)
#         return ""

def _get_text_for_matching(p: Path) -> str | None:
    """
    Return plaintext for name matching, from any supported format.
    Never modifies the underlying file; only uses extractors.
    """
    ext = p.suffix.lower()

    print(f"[DB][EXTRACT] Processing file: {p} (ext={ext})")

    # Try reading as plain text ONLY for obvious text formats
    if ext in [".txt", ".csv", ".json", ".md", ".log"]:
        print("[DB][EXTRACT] Trying UTF-8 plain text read")
        try:
            txt = p.read_text(encoding="utf-8")

            print("[DB][EXTRACT] UTF-8 plain text read SUCCESS")
            print("[DB][EXTRACT] Preview (first 200 chars):")
            print(txt[:200])
            return txt # is the txt or csv or other listed above format
        except UnicodeDecodeError:
            print("[DB][EXTRACT] UTF-8 plain text read FAILED, falling back")
            pass

    # Fall back to rich extractors for binary formats
    if ext == ".pdf":
        print("[DB][EXTRACT] Using PDF extractor")
        text = _extract_pdf_to_text(str(p))
        print("[DB][EXTRACT] PDF extractor output preview (first 200 chars):")
        print(text[:200])
        return text
        # return _extract_pdf_text(str(p))

    # if ext == ".docx":
    #     return _extract_docx_to_text(str(p))
    # if ext == ".odt":
    #     return _extract_odt_to_text(str(p))
    # if ext in [".xls", ".xlsx"]:
    #     return _extract_excel_to_text(str(p))

    # Unsupported binary format
    print("[DB][EXTRACT] Unsupported file type → returning None")
    return None


# def _read_text_safe(p: Path) -> str | None:
#     try:
#         return p.read_text(encoding="utf-8", errors="ignore")
#     except Exception:
#         return None  # for binary file or unreadable, return None, not ""

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

    content = _get_text_for_matching(p) #_read_text_safe(p)
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