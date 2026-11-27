"""Run a conversion in a killable child process.

Why: a Python thread cannot be cancelled or time-limited, so a slow/hung conversion would hold the
single worker slot forever on a small free-tier host. A child process (own process group) can be
killed together with anything it spawned (e.g. LibreOffice)."""
import asyncio, os, re, signal, sys
from pathlib import Path

class WorkerCancelled(Exception): pass
class WorkerTimeout(Exception): pass
class WorkerFailed(Exception):
    def __init__(self, reason, tail=''):
        super().__init__(reason); self.reason=reason; self.tail=tail

_EXC=re.compile(r'^((?:[A-Za-z_]\w*\.)*[A-Z]\w*[a-z]\w*):\s*(.*)$')   # unindented 'pkg.ClassName: message'; excludes INFO:/ERROR: prefixes

def extract_reason(log_text):
    """Return a short, path-free, user-safe reason from a child's traceback/stderr tail."""
    reason=None
    for line in log_text.splitlines():
        m=_EXC.match(line.rstrip())
        if m: reason=m.group(2) or m.group(1)
    if not reason: return 'The converter stopped unexpectedly. Details are in the server log.'
    reason=re.sub(r'(/[\w.\-]+){2,}','<path>',reason)       # never leak server paths
    return reason[:200]

async def _kill_group(proc):
    if proc.returncode is None:
        try: os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError): pass
    try: await asyncio.wait_for(proc.wait(), 10)
    except asyncio.TimeoutError: pass

async def run_worker(argv, log_path, timeout, is_cancelled=None, poll=0.2):
    log_path=Path(log_path)
    with log_path.open('wb') as log:
        proc=await asyncio.create_subprocess_exec(*argv, start_new_session=True, stdout=log, stderr=log)
    loop=asyncio.get_running_loop(); deadline=loop.time()+timeout
    try:
        while proc.returncode is None:
            if is_cancelled is not None and await is_cancelled(): raise WorkerCancelled()
            if loop.time()>=deadline: raise WorkerTimeout()
            try: await asyncio.wait_for(asyncio.shield(proc.wait()), poll)
            except asyncio.TimeoutError: pass
        if proc.returncode!=0:
            size=log_path.stat().st_size
            with log_path.open('rb') as f:
                f.seek(max(0,size-8192)); tail=f.read().decode('utf-8','replace')
            raise WorkerFailed(extract_reason(tail), tail)
    finally:
        await _kill_group(proc)   # always: also reaps grandchildren such as soffice.bin
