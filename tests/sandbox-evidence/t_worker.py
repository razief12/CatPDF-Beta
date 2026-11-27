import asyncio, os, sys, time, tempfile, signal
from pathlib import Path
sys.path.insert(0,'/home/claude/work/p16')
from worker import *
def alive(pid):
    try: os.kill(pid,0); 
    except ProcessLookupError: return False
    # zombie check
    try: return open(f'/proc/{pid}/stat').read().split()[2]!='Z'
    except FileNotFoundError: return False
R=[]
def chk(l,ok,d=''): R.append(ok); print(('PASS ' if ok else 'FAIL ')+l+(' | '+d if d else ''))
async def main():
    d=Path(tempfile.mkdtemp())
    # 1 success
    await run_worker([sys.executable,'-c','print("ok")'],d/'a.log',10); chk('clean exit returns normally',True)
    # 2 failure reason extraction (real traceback shape from production log)
    code="import sys;sys.stderr.write('Consider using the pymupdf_layout package...\\n');raise ValueError('Image-only page detected; OCR required to avoid silent data loss')"
    try: await run_worker([sys.executable,'-c',code],d/'b.log',10); chk('failure raises',False)
    except WorkerFailed as e: chk('failure -> exact reason surfaced (not "check server logs")',e.reason=='Image-only page detected; OCR required to avoid silent data loss',e.reason)
    # 3 path scrubbing
    try: await run_worker([sys.executable,'-c',"raise RuntimeError('cannot open /tmp/abc/def/input.pdf now')"],d/'c.log',10)
    except WorkerFailed as e: chk('server paths scrubbed from user-facing reason','/tmp' not in e.reason,e.reason)
    # 4 TimeoutExpired style (production OCR failure shape)
    try: await run_worker([sys.executable,'-c',"import subprocess;raise subprocess.TimeoutExpired(['tesseract'],35)"],d/'d.log',10)
    except WorkerFailed as e: chk('TimeoutExpired reason extracted',e.reason.startswith("Command '['tesseract']' timed out"),e.reason)
    # 5 timeout kills child AND grandchild
    pidf=d/'gc.pid'; t=time.time()
    try: await run_worker(['sh','-c',f'sleep 300 & echo $! > {pidf}; wait'],d/'e.log',2); chk('timeout raises',False)
    except WorkerTimeout: chk('hard timeout enforced',2<=time.time()-t<4,f'{time.time()-t:.1f}s')
    await asyncio.sleep(.3); gc=int(pidf.read_text()); chk('grandchild (like soffice.bin) killed on timeout',not alive(gc),f'pid {gc}')
    # 6 cancellation kills immediately, frees the slot
    pidf2=d/'gc2.pid'; n=[0]
    async def cancelled():
        n[0]+=1; return time.time()-t0>1
    t0=time.time()
    try: await run_worker(['sh','-c',f'sleep 300 & echo $! > {pidf2}; wait'],d/'f.log',60,is_cancelled=cancelled); chk('cancel raises',False)
    except WorkerCancelled: chk('client-cancel stops job promptly (not 60s timeout)',time.time()-t0<3,f'{time.time()-t0:.1f}s')
    await asyncio.sleep(.3); chk('grandchild killed on cancel',not alive(int(pidf2.read_text())))
    # 7 slot is reusable right after cancel (the Patch 15 failure mode)
    t1=time.time(); await run_worker([sys.executable,'-c','print(1)'],d/'g.log',10); chk('next job starts immediately after a cancel',time.time()-t1<2,f'{time.time()-t1:.2f}s')
    # 8 signal-killed child (e.g. OOM SIGKILL) -> failure, generic reason
    try: await run_worker(['sh','-c','kill -9 $$'],d/'h.log',10)
    except WorkerFailed as e: chk('OOM-style SIGKILL reported as failure with safe message','server log' in e.reason,e.reason)
asyncio.run(main()); print('\nSUMMARY: %d/%d passed'%(sum(R),len(R)))
