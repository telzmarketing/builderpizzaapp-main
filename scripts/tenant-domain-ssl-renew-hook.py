#!/usr/bin/python3 -I
"""Certbot deploy hook. Root-owned standalone; no backend/package imports."""
import fcntl
import os
from pathlib import Path
import stat
import subprocess
import sys


def trusted(path, directory=False, mode=None):
    for item in [*reversed(path.parents), path]:
        info = item.lstat()
        sticky_lock_root = (item == Path('/run/lock') and stat.S_ISDIR(info.st_mode)
                            and stat.S_IMODE(info.st_mode) == 0o1777)
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or (info.st_mode & 0o022 and not sticky_lock_root):
            raise ValueError('unsafe path')
    info = path.stat()
    if directory and not stat.S_ISDIR(info.st_mode):
        raise ValueError('unsafe directory')
    if not directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
        raise ValueError('unsafe file')
    if mode is not None and stat.S_IMODE(info.st_mode) != mode:
        raise ValueError('unsafe permissions')


def main():
    fd = None
    try:
        if os.geteuid() != 0:
            raise ValueError('root required')
        trusted(Path(__file__).absolute())
        lock = Path('/run/lock/telz/maintenance.lock')
        trusted(lock.parent, directory=True, mode=0o700)
        fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        info = os.fstat(fd)
        if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
            raise ValueError('unsafe lock')
        # Renewal must not be silently skipped if another maintenance holds lock.
        # Bounded retries allow an operator to see failure without deadlocking Certbot.
        import time
        deadline = time.monotonic() + 120
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ValueError('maintenance busy')
                time.sleep(1)
        environment = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/root', 'LANG': 'C.UTF-8'}
        for argv in (['/usr/sbin/nginx', '-t'], ['/usr/bin/systemctl', 'reload', 'nginx']):
            trusted(Path(argv[0]).resolve(strict=True))
            subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=45, check=True, env=environment)
        print('[telz-domain-ssl] renewal reload completed')
        return 0
    except Exception:
        print('[telz-domain-ssl] renewal reload failed; inspect nginx and maintenance status', file=sys.stderr)
        return 1
    finally:
        if fd is not None:
            os.close(fd)


if __name__ == '__main__':
    sys.exit(main())
