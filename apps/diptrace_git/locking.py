"""Serialize local conversions; release ownership automatically on process exit."""
from contextlib import contextmanager
import os
import time

ACTIVE = 'DIPTRACE_GIT_ACTIVE'


@contextmanager
def internal_commands():
    previous = os.environ.get(ACTIVE)
    os.environ[ACTIVE] = '1'
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(ACTIVE, None)
        else:
            os.environ[ACTIVE] = previous


@contextmanager
def locked(repo, timeout=20):
    repo.state_dir.mkdir(parents=True, exist_ok=True)
    with (repo.state_dir / 'sync.lock').open('a+b') as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b'\0')
            handle.flush()
        acquired = False
        deadline = time.monotonic() + timeout
        try:
            while not acquired:
                try:
                    handle.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('another synchronization is still running; retry after it finishes') from None
                    time.sleep(0.025)
            yield
        finally:
            if acquired:
                handle.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)
