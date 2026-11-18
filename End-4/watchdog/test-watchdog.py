#!/usr/bin/env python3
"""Check shutdown signals delivered to either watchdog thread on Linux."""
import ctypes
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import time

CHILD_SCRIPT = """#!/usr/bin/env python3
import os
from pathlib import Path
import signal
import sys

directory = Path(__file__).parent

def stop(number, frame):
    (directory / 'stopped').write_text(str(number))
    sys.exit(0)

signal.signal(signal.SIGTERM, stop)
if os.environ.get('RESTART_TEST'):
    fd = int(sys.argv[sys.argv.index('--watchdog-fd') + 1])
    if '--safe-mode' not in sys.argv:
        os.write(fd, b'vax\\nlock\\n')
        sys.exit(1)
    os.write(fd, b'vax\\n')
    (directory / 'restart-args').write_text(' '.join(sys.argv))
(directory / 'ready').touch()
signal.pause()
"""


def check(launcher, shutdown_signal, thread, *, restart=False):
    with tempfile.TemporaryDirectory(prefix='watchdog-shutdown-') as temp:
        directory = Path(temp)
        child = directory / 'child'
        child.write_text(CHILD_SCRIPT)
        child.chmod(0o700)
        env = os.environ.copy()
        if restart:
            env['RESTART_TEST'] = '1'
        with subprocess.Popen([launcher, '--no-nixgl', '--path', str(child)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, start_new_session=True, env=env) as process:
            try:
                deadline = time.monotonic() + 8
                while not (directory / 'ready').exists():
                    if process.poll() is not None:
                        raise AssertionError(process.stdout.read())
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Test compositor did not reach readiness')
                    time.sleep(.02)
                if thread == 'process':
                    process.send_signal(shutdown_signal)
                else:
                    threads = [int(p.name) for p in Path(f'/proc/{process.pid}/task').iterdir()]
                    assert len(threads) == 2, threads
                    tid = next(tid for tid in threads if tid != process.pid)
                    libc = ctypes.CDLL(None, use_errno=True)
                    if libc.tgkill(process.pid, tid, shutdown_signal) != 0:
                        raise OSError(ctypes.get_errno(), 'tgkill')
                output, _ = process.communicate(timeout=8)
                assert process.returncode == 0, f'{process.returncode=}\n{output}'
                assert (directory / 'stopped').read_text() == str(signal.SIGTERM), output
                if restart:
                    assert '--safe-mode --locked' in (directory / 'restart-args').read_text()
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        print(f'PASS {shutdown_signal.name} to {thread} ({restart=})')


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    launcher = sys.argv[1]
    for number in (signal.SIGTERM, signal.SIGINT):
        for destination in ('worker', 'process'):
            check(launcher, number, destination)
    check(launcher, signal.SIGTERM, 'worker', restart=True)
