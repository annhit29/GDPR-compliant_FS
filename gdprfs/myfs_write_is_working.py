from fuse import Fuse
import fuse
fuse.fuse_python_api = (0, 2) 

from gdprfs.settings import INSTRLIB_EXE, INSTRLIB_FORMULA, INSTRLIB_LOG, INSTRLIB_SIG
from instrlib.instrument import Instrument
from instrlib.logger import Logger
from instrlib.pdp import EnfGuard
from instrlib.schema import Schema
from instrlib.pep import PEP, InstrumentationMapping
from instrlib.event import Event, Functional
import os, shutil
from pathlib import Path

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

ann20010929@ann20010929-ThinkPad-P16s-Gen-3:~/MA3/Building_a_GDPR-compliant_file_system/instrlib$ ls /var/lib/gdprfs/upper
test.txt
ann20010929@ann20010929-ThinkPad-P16s-Gen-3:~/MA3/Building_a_GDPR-compliant_file_system/instrlib$ ls /var/lib/gdprfs/mirror
ls: cannot open directory '/var/lib/gdprfs/mirror': Permission denied
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


    
# ========== SCHEMA ==========
schema = Schema()
schema.add('Use', [str, str]) # for reads
schema.add('Collect', [str, str]) # for writes
schema.add('Erase', [str]) # for the erase of a file
# schema.add('Consent', [str, str]) # for consent events
# schema.add('Revoke', [str, str]) # for revoke consent events

# ========== HANDLERS ==========
def none_handler(event_name, event_args, response, *args, **kwargs):
    """
    Python side  =/= Enforcer side
    The none_handler means "do nothing" in the python side (if I wanna return or print sthon the terminal).
    and the enforcer is actually suppressing or causing a file operation.
    """
    return None

# suppression_handlers = {('Use'): none_handler}
suppression_handlers = {
    ('Use'): none_handler,
    ('Collect'): none_handler
}
causation_handlers = {('Erase'): none_handler#,
                    #   ('Consent'): none_handler,
                    #   ('Collect'): none_handler
                      }

# ========== MAPPINGS ==========
def read_mapping(action):  return Event('Use', str(action), 'marketing')
# todo: or the following?
# def read_mapping(action):
#     print("[DEBUG InstrumentationMapping] remapping event", action)
#     return Event('Use', str(action), 'analytics')  # different purpose!

def write_mapping(action): return Event('Collect', str(action), 'marketing')
def unlink_mapping(action): return Event('Erase', str(action))

instrumentation_mapping = InstrumentationMapping({
    'read': read_mapping,
    'write': write_mapping,
    'unlink': unlink_mapping
})
# todo: or
# instrumentation_mapping = InstrumentationMapping({
#     'Use': read_mapping,
#     'Collect': write_mapping,
#     'Erase': unlink_mapping
# })
# ?

pep = PEP(
    mapping={
        ('MyFS', 'read'): Functional(
    'Use',
    lambda path, *a, **kw:
        [Event('Collect', "14a-123", "marketing")] if os.path.basename(path).startswith(".goutputstream-") #“This operation isn’t part of any suppressible mapping; I'm letting it through, but no suppression logic applies.”
        else [Event('Use', "14a-123", "marketing")]
),
        # ('MyFS', 'read'): Functional('Use', lambda path, *a, **kw: [Event('Use', "14a-123", "marketing")]), 
        #todo: for the fileid, use the kw to find the file fid; o/w create a script for finding the file fid
        ('MyFS', 'write'): Functional('Collect', lambda path, *a, **kw: [Event('Collect', "14a-123", "marketing")]),
        # ('MyFS', 'unlink'): Functional('Erase', lambda path, *a, **kw: [Event('Erase', path)]),
    },
    suppression_handlers=suppression_handlers,
    causation_handlers=causation_handlers,
    instrumentation_mapping=instrumentation_mapping#InstrumentationMapping({}) 
    #todo: instrumentation_mapping or InstrumentationMapping({}) ?
)

pdp = EnfGuard(INSTRLIB_EXE, INSTRLIB_SIG, INSTRLIB_FORMULA, log_file=INSTRLIB_LOG)

# logger = Logger(name="gdprfs")
logger = Logger(pep, schema, pdp)
print("PEP mapping keys:", list(logger.pep.mapping.keys()))
pdp.start_threads() # then start the EnfGuard enforcer + threads

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

# @Instrument(logger) # Apply the Instrument decorator with our logger to MyFS
# @Instrument(logger, skip_attr_overwrite=True) #<- not safe, coz monkey-patch
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
            f.write(data)
            f.flush()

        # After writing, sync to mirror
        _sync_to_mirror(path)
        print(f"[WRITE] path={path} → synced to mirror")
        return len(data) # Returning len(data) tells FUSE “OK, I wrote everything.”

    def getattr(self, path):
        """
        Return the attributes of a file or directory.
        (e.g. size, permissions, owner, timestamps)
        Called whenever Linux does 'ls', 'stat', etc.
        """
        print(f"[DEBUG getattr] called with path={path}", flush=True)

        from fuse import Stat
        from errno import ENOENT

        # Find the real file inside /upper
        real_path = _upper(path)

        if not real_path.exists():
            raise OSError(ENOENT, "No such file or directory")

        # Get the actual file info from disk
        s = real_path.lstat()

        # Fill the FUSE Stat structure
        st = Stat()
        st.st_mode  = s.st_mode      # file type + permissions
        st.st_nlink = s.st_nlink     # number of hard links
        st.st_size  = s.st_size      # file size in bytes
        st.st_uid   = s.st_uid       # owner user id (still needed for Linux)
        st.st_gid   = s.st_gid       # group id
        st.st_atime = int(s.st_atime)  # access time
        st.st_mtime = int(s.st_mtime)  # modification time
        st.st_ctime = int(s.st_ctime)  # change/creation time

        # print(f"st", st)
        return st

    def readdir(self, path, offset):
        """
        (awscli-venv) ann20010929@ann20010929-ThinkPad-P16s-Gen-3:~/MA3/Building_a_GDPR-compliant_file_system/instrlib$ ls -la /tmp/mnt
        total 25
        drwxr-xr-x  2 root root     0 Jan  1  1970 .
        drwxrwxrwt 25 root root 20480 Oct 14 16:55 ..
        -rw-r--r--  1 root root    13 Jan  1  1970 hello.txt
        """
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
        # allow access if the path exists in /upper
        print(f"[DEBUG open] called with path={path}, flags={flags}", flush=True)
        if _upper(path).exists():
            return 0
        from errno import ENOENT
        raise OSError(ENOENT, "No such file or directory")

    def read(self, path, size, offset, fh=None):
        print("read file")
    
        # detect misrouted write()
        # so mimic FUSE def write()
        if isinstance(size, (bytes, bytearray)):
            print(f"[WRITE] Misrouted write() detected — redirecting safely to raw write for {path}")
            return self._write(path, size, offset, fh)

            # data = size

            # p = _upper(path)
            # _ensure_parent(p)
            # with open(p, "r+b" if p.exists() else "wb") as f:
            #     f.seek(offset)
            #     f.write(data)
            #     f.flush()
            # _sync_to_mirror(path)
            # print(f"[WRITE] path={path} → synced to mirror (manual fallback)")
            # return len(data) # Returning len(data) tells FUSE “OK, I wrote everything.”

        p = _upper(path)
        if not p.is_file():
            from errno import ENOENT
            raise OSError(ENOENT, "No such file or directory")

        # return only the requested slice, as bytes
        with open(p, "rb") as f: # the file is being read from p i.e. from /upper 
            f.seek(offset)
            # return f.read(size)
            print(f"size: {size}")
            data = f.read(size)
        print(f"[READ] path={path} reading from {p}, {len(data)} bytes, size={size}, offset={offset}, returning={data}")

        return data


    def create(self, path, mode, fi=None):
        """Create a new empty file in /upper and sync to /mirror."""
        p = _upper(path)
        _ensure_parent(p)
        print(f"[CREATE] Creating new file {p}")

        # Create file in upper layer
        # I opened the file, now it exists, even if I didn’t write on it yet.
        with open(p, "wb") as f:
            pass # create empty file

        # Sync to mirror
        _sync_to_mirror(path)
        print(f"[CREATE] Synced {p} → mirror")
        return 0

    def rename(self, old, new):
        """
        Rename a file or directory from 'old' → 'new'
        Both in /upper and in /mirror
        """
        print("I'm in the rename function")
        print(f"[DEBUG rename] called with old={old}, new={new}", flush=True)
        old_p = _upper(old)
        new_p = _upper(new)
        print(f"[RENAME] {old_p} → {new_p}")

        if not old_p.exists():
            from errno import ENOENT
            raise OSError(ENOENT, f"No such file: {old}")

        _ensure_parent(new_p)
        os.rename(old_p, new_p)

        # Also rename in mirror if it exists
        old_m = _mirror(old)
        new_m = _mirror(new)
        if old_m.exists():
            _ensure_parent(new_m)
            os.rename(old_m, new_m)

        print(f"[RENAME] Synced {old_p} → {new_p} and {old_m} → {new_m}")
        return 0

    def write(self, path, data, offset, fh=None):
        print(f"[DEBUG write] called with path={path}, data = {data}, data_len={len(data)}, offset={offset}", flush=True)
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

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 myfs.py <mountpoint>")
        sys.exit(1)
    
    fs = MyFS()
    fs.parse()              # parse FUSE args
    fs.main()               # enter service loop
