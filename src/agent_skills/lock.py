"""Advisory file locking."""

import fcntl
import os
import time
from pathlib import Path


class LockError(Exception):
    pass


class AdvisoryLock(object):
    def __init__(self, path, timeout=10.0):
        self.path = Path(path)
        self.timeout = timeout
        self._fd = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o644)
        deadline = time.time() + self.timeout
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except (IOError, OSError):
                if time.time() >= deadline:
                    os.close(self._fd)
                    self._fd = None
                    raise LockError("could not acquire lock: %s" % self.path)
                time.sleep(0.1)

    def release(self):
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            except (IOError, OSError):
                pass
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()
        return False