from fuse import Fuse
import fuse
fuse.fuse_python_api = (0, 2) 

import stat
from gdprfs.settings import INSTRLIB_EXE, INSTRLIB_FORMULA, INSTRLIB_LOG, INSTRLIB_SIG
from instrlib.instrument import Instrument
from instrlib.logger import Logger
from instrlib.pdp import EnfGuard
from instrlib.schema import Schema
from instrlib.pep import PEP, InstrumentationMapping
from instrlib.event import Event

schema = Schema()
schema.add('Use', [str])       # for reads
schema.add('Collect', [str])   # for writes
schema.add('Erase', [str])     # for deletions

# ========== HANDLERS ==========
def none_handler(event_name, event_args, response, *args, **kwargs):
    return None

suppression_handlers = {('Use'): none_handler}
causation_handlers = {('Erase'): none_handler}

# ========== MAPPINGS ==========
def read_mapping(action): return Event('Use', str(action))
def write_mapping(action): return Event('Collect', str(action))
def unlink_mapping(action): return Event('Erase', str(action))

instrumentation_mapping = InstrumentationMapping({
    'read': read_mapping,
    'write': write_mapping,
    'unlink': unlink_mapping
})

pep = PEP(
    suppression_handlers=suppression_handlers,
    causation_handlers=causation_handlers,
    instrumentation_mapping=instrumentation_mapping
)

pdp = EnfGuard(INSTRLIB_EXE, INSTRLIB_SIG, INSTRLIB_FORMULA, log_file=INSTRLIB_LOG)

# logger = Logger(name="gdprfs")
logger = Logger(pep, schema, pdp)

# @Instrument(logger) 
class MyFS(Fuse):
    """A minimal GDPR-aware FUSE filesystem."""

    HELLO_PATH = "/hello.txt"
    HELLO_DATA = b"reading file\n"

    def getattr(self, path): # get file attributes
        from fuse import Stat
        st = Stat()
        # st.st_mode = 0o777 | 0o100000
        # st.st_nlink = 1
        # st.st_size = 12

        """
        / is a directory
        /hello.txt is a file

        ls wants a directory path, so we give it "/", o/w EIO
        """
        if path == "/":                           # if the path is the root directory
            st.st_mode  = stat.S_IFDIR | 0o755 # directory
            st.st_nlink = 2
            st.st_size  = 0
        elif path == self.HELLO_PATH:             # if the path is /hello.txt file
            st.st_mode  = stat.S_IFREG | 0o644 # regular file
            st.st_nlink = 1
            st.st_size  = len(self.HELLO_DATA)
        else:
            # tell FUSE the entry doesn't exist
            from errno import ENOENT
            raise OSError(ENOENT, "No such file or directory")
        return st

    def readdir(self, path, offset):
        """
        (awscli-venv) ann20010929@ann20010929-ThinkPad-P16s-Gen-3:~/MA3/Building_a_GDPR-compliant_file_system/instrlib$ ls -la /tmp/mnt
        total 25
        drwxr-xr-x  2 root root     0 Jan  1  1970 .
        drwxrwxrwt 25 root root 20480 Oct 14 16:55 ..
        -rw-r--r--  1 root root    13 Jan  1  1970 hello.txt
        """
        # yield ".", 0
        # yield "..", 0
        # yield "hello.txt", 0
        from fuse import Direntry

        # Return simple Direntry objects instead of raw tuples
        for name in [".", "..", "hello.txt"]:
            yield Direntry(name)
    
    def read(self, path, size, offset, fh=None):
        """
        (awscli-venv) ann20010929@ann20010929-ThinkPad-P16s-Gen-3:~/MA3/Building_a_GDPR-compliant_file_system/instrlib$ cat /tmp/mnt/hello.txt
        reading file
        """
        # return b"reading file\n"
        if path != self.HELLO_PATH:
            from errno import ENOENT
            raise OSError(ENOENT, "No such file or directory")
        data = self.HELLO_DATA
        return data[offset:offset+size]

    def write(self, path, data, offset, fh=None):
        return len(data) # Returning len(data) tells FUSE “OK, I wrote everything.”

    def unlink(self, path):
        # print("[GDPRFS] unlink:", path)

        # Optional: pretend delete succeeds only for our file
        if path == self.HELLO_PATH:
            return 0
        from errno import ENOENT
        raise OSError(ENOENT, "No such file or directory")

    def statfs(self):
        from fuse import StatVfs
        st = StatVfs()
        st.f_bsize = 4096
        st.f_blocks = 1
        st.f_bavail = 0
        st.f_files = 1
        return st


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 myfs.py <mountpoint>")
        sys.exit(1)

    # fs = MyFS()
    # fs = Instrument(logger)(MyFS)  # Wrap MyFS with the Instrument decorator
    
    # Apply the decorator, then create an object
    # InstrumentedFS = Instrument(logger)(MyFS)
    # fs = InstrumentedFS()
    
    fs = MyFS()
    fs.parse()              # parse FUSE args
    fs.main()               # enter service loop
