from pathlib import Path
from tempfile import TemporaryDirectory
import asyncio, os, sys, logging, re, time
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from kinds import KINDS, ALLOWED
from worker import run_worker, WorkerCancelled, WorkerTimeout, WorkerFailed
VERSION='4.5.6.5.37'; WORKER_TIMEOUT=300; COMPRESSION_TIMEOUT=150; MAX_BYTES=20*1024*1024
log=logging.getLogger('uvicorn.error'); RUNNER=str(Path(__file__).resolve().with_name('job_runner.py'))
app=FastAPI(title='CatPDF Conversion API')
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CATPDF_ORIGINS','https://razief12.github.io,http://localhost:8000').split(','),allow_methods=['POST','GET'],allow_headers=['*'])
from payment import router as payment_router, startup_verify
app.include_router(payment_router)
@app.on_event('startup')
async def verify_payment_prices():
    asyncio.create_task(startup_verify())

slots=asyncio.Semaphore(1)
active_progress={}
cancelled={}

def prune_cancelled():
    now=asyncio.get_running_loop().time()
    for key, expiry in list(cancelled.items()):
        if expiry<=now: cancelled.pop(key,None)

@app.post("/cancel/{token}")
async def cancel(token:str):
    if not re.fullmatch(r"[a-f0-9]{32}",token): raise HTTPException(400,"Invalid token")
    prune_cancelled()
    if len(cancelled)>=4096 and token not in cancelled: raise HTTPException(429,"Too many cancellations")
    cancelled[token]=asyncio.get_running_loop().time()+300
    return {"cancelled":True}

@app.get('/progress/{token}')
async def progress(token:str):
    return Response(__import__('json').dumps({'stage':active_progress.get(token,'unknown')}),media_type='application/json',headers={'Cache-Control':'no-store'})


@app.get('/health')
def health(): return {'status':'ok','version':VERSION,'kinds':sorted(KINDS),'compress':['low','medium','high'],'progress':True,'explicit_cancel':True}

async def job(request, mode, kind, src, out, workdir, token=None):
    async def stopped():
        return (token is not None and token in cancelled) or await request.is_disconnected()
    started=time.monotonic()
    timeout=WORKER_TIMEOUT if mode=='convert' else COMPRESSION_TIMEOUT
    log.info("Job start %s/%s bytes=%s",mode,kind,src.stat().st_size)
    try:
        await run_worker([sys.executable,RUNNER,mode,kind,str(src),str(out)], workdir/'worker.log', timeout, is_cancelled=stopped)
    except WorkerCancelled:
        log.info('Job cancelled %s/%s after %.1fs',mode,kind,time.monotonic()-started)
        raise HTTPException(499,'Client disconnected')
    except WorkerTimeout:
        log.warning('Job timeout %s/%s after %.1fs',mode,kind,time.monotonic()-started)
        raise HTTPException(504,f'Processing timed out after {timeout} s')
    except WorkerFailed as e:
        log.error('Worker %s/%s failed: %s',mode,kind,e.tail[-4000:])
        raise HTTPException(422,'Conversion failed: '+e.reason) from None
    else:
        log.info('Job completed %s/%s after %.1fs',mode,kind,time.monotonic()-started)

async def check_access(request, kind):
    import urllib.request, urllib.error, json
    token=request.headers.get('authorization','')
    if not token:
        if kind in ('pdfdocx','pdfxlsx','pdfpptx'): raise HTTPException(403,'Premium account required')
        return
    if not token.startswith('Bearer '): raise HTTPException(401,'Invalid authorization')
    def call():
        req=urllib.request.Request('https://unauvicwfjnfqyrtexhy.supabase.co/rest/v1/rpc/catpdf_quota',data=json.dumps({'p_consume':False,'p_tool':kind,'p_device':request.headers.get('x-catpdf-device'),'p_activate':False}).encode(),headers={'apikey':'sb_publishable_y9pVKZ47UfWibxYaoOcoAg_3mlqpDPs','Authorization':token,'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=10) as r: return json.load(r)
    try: result=await asyncio.to_thread(call)
    except urllib.error.HTTPError as e: raise HTTPException(401 if e.code in (401,403) else 503,'Account quota verification failed') from None
    except Exception: raise HTTPException(503,'Quota service unavailable') from None
    if not result.get('allowed'): raise HTTPException(403,result.get('reason','Access denied'))

@app.post('/convert/{kind}')
async def run(kind:str,request:Request,file:UploadFile=File(...)):
    if kind not in KINDS: raise HTTPException(404,'Unknown converter')
    await check_access(request,kind)
    data=await file.read(MAX_BYTES+1)
    if not data or len(data)>MAX_BYTES: raise HTTPException(413,'File limit: 20 MB')
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in ALLOWED.get(kind,{'.pdf'}): raise HTTPException(400,'Unsupported extension')
    token=request.query_params.get('progress','')
    tracked=bool(re.fullmatch(r'[a-f0-9]{32}',token)) and token not in active_progress
    def stage(value):
        if tracked: active_progress[token]=value
    prune_cancelled()
    stage('queued')
    queued_at=time.monotonic()
    log.info('Conversion queued kind=%s bytes=%s',kind,len(data))
    acquired=False
    try:
        while not acquired:
            if (tracked and token in cancelled) or await request.is_disconnected(): raise HTTPException(499,'Cancelled')
            try:
                await asyncio.wait_for(slots.acquire(),0.25)
                acquired=True
            except asyncio.TimeoutError: pass
        if acquired:
            log.info('Conversion acquired worker kind=%s wait=%.1fs',kind,time.monotonic()-queued_at)
            if (tracked and token in cancelled) or await request.is_disconnected(): raise HTTPException(499,'Cancelled')
            with TemporaryDirectory() as d:
                d=Path(d); src=d/('input'+suffix); out=d/('output.'+KINDS[kind]); src.write_bytes(data); stage('processing')
                try:
                    await job(request,'convert',kind,src,out,d,token if tracked else None)
                    stage('finalizing')
                    if not out.exists() or not out.stat().st_size: raise HTTPException(422,'Conversion failed: converter produced an empty file')
                    if out.stat().st_size>100*1024*1024: raise HTTPException(422,'Conversion failed: output exceeds 100 MB')
                    return Response(out.read_bytes(),media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="converted.{KINDS[kind]}"','Cache-Control':'no-store'})
                except HTTPException: raise
                except Exception:
                    log.exception('Unexpected server error: %s',kind); raise HTTPException(500,'Unexpected server error. Details are in the server log.') from None
    finally:
        if acquired: slots.release()
        if tracked: active_progress.pop(token,None)

@app.post('/compress/{mode}')
async def compress(mode:str,request:Request,file:UploadFile=File(...)):
    if mode not in ('low','medium','high'): raise HTTPException(400,'Unknown compression mode')
    data=await file.read(MAX_BYTES+1)
    if not data or len(data)>MAX_BYTES: raise HTTPException(413,'File limit: 20 MB')
    async with slots:
        if await request.is_disconnected(): raise HTTPException(499,'Client disconnected')
        with TemporaryDirectory() as d:
            d=Path(d); src=d/'input.pdf'; out=d/'output.pdf'; src.write_bytes(data)
            try:
                await job(request,'compress',mode,src,out,d)
                return Response(out.read_bytes(),media_type='application/pdf',headers={'Cache-Control':'no-store'})
            except HTTPException: raise
            except Exception:
                log.exception('Unexpected server error: compress'); raise HTTPException(500,'Unexpected server error. Details are in the server log.') from None
