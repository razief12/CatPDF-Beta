from pathlib import Path
from tempfile import TemporaryDirectory
import asyncio, os, sys, logging
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from kinds import KINDS, ALLOWED
from worker import run_worker, WorkerCancelled, WorkerTimeout, WorkerFailed
VERSION='4.5.6.5.24'; WORKER_TIMEOUT=150; MAX_BYTES=20*1024*1024
log=logging.getLogger('uvicorn.error'); RUNNER=str(Path(__file__).resolve().with_name('job_runner.py'))
app=FastAPI(title='CatPDF Conversion API')
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CATPDF_ORIGINS','https://razief12.github.io,http://localhost:8000').split(','),allow_methods=['POST','GET'],allow_headers=['*'])
slots=asyncio.Semaphore(1)

@app.get('/health')
def health(): return {'status':'ok','version':VERSION,'kinds':sorted(KINDS),'compress':['low','medium','high']}

async def job(request, mode, kind, src, out, workdir):
    try:
        await run_worker([sys.executable,RUNNER,mode,kind,str(src),str(out)], workdir/'worker.log', WORKER_TIMEOUT, is_cancelled=request.is_disconnected)
    except WorkerCancelled: raise HTTPException(499,'Client disconnected')
    except WorkerTimeout: raise HTTPException(504,f'Processing timed out after {WORKER_TIMEOUT} s')
    except WorkerFailed as e:
        log.error('Worker %s/%s failed: %s',mode,kind,e.tail[-4000:])
        raise HTTPException(422,'Conversion failed: '+e.reason) from None

@app.post('/convert/{kind}')
async def run(kind:str,request:Request,file:UploadFile=File(...)):
    if kind not in KINDS: raise HTTPException(404,'Unknown converter')
    data=await file.read(MAX_BYTES+1)
    if not data or len(data)>MAX_BYTES: raise HTTPException(413,'File limit: 20 MB')
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in ALLOWED.get(kind,{'.pdf'}): raise HTTPException(400,'Unsupported extension')
    async with slots:
        if await request.is_disconnected(): raise HTTPException(499,'Client disconnected')
        with TemporaryDirectory() as d:
            d=Path(d); src=d/('input'+suffix); out=d/('output.'+KINDS[kind]); src.write_bytes(data)
            try:
                await job(request,'convert',kind,src,out,d)
                if not out.exists() or not out.stat().st_size: raise HTTPException(422,'Conversion failed: converter produced an empty file')
                if out.stat().st_size>100*1024*1024: raise HTTPException(422,'Conversion failed: output exceeds 100 MB')
                return Response(out.read_bytes(),media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="converted.{KINDS[kind]}"','Cache-Control':'no-store'})
            except HTTPException: raise
            except Exception:
                log.exception('Unexpected server error: %s',kind); raise HTTPException(500,'Unexpected server error. Details are in the server log.') from None

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
