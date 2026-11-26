from pathlib import Path
from tempfile import TemporaryDirectory
import asyncio, os, sys, signal
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from engine import convert, KINDS
app=FastAPI(title='CatPDF Conversion API')
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CATPDF_ORIGINS','https://razief12.github.io,http://localhost:8000').split(','),allow_methods=['POST','GET'],allow_headers=['*'])
slots=asyncio.Semaphore(1)
async def run_job(request, mode, kind, src, out):
    proc = await asyncio.create_subprocess_exec(sys.executable, str(Path(__file__).with_name('job_runner.py')), mode, kind, str(src), str(out), start_new_session=True, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    try:
        deadline = asyncio.get_running_loop().time() + 150
        while proc.returncode is None:
            if await request.is_disconnected():
                raise HTTPException(499, 'Client disconnected')
            if asyncio.get_running_loop().time() >= deadline:
                raise HTTPException(504, 'Processing timed out')
            await asyncio.sleep(.2)
        if proc.returncode != 0:
            raise ValueError('Conversion worker failed')
    finally:
        if proc.returncode is None:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        await proc.wait()

@app.get('/health')
def health(): return {'status':'ok','version':'4.5.6.5.18'}
@app.post('/convert/{kind}')
async def run(kind:str,request:Request,file:UploadFile=File(...)):
    if kind not in KINDS: raise HTTPException(404,'Unknown converter')
    data=await file.read(20*1024*1024+1)
    if not data or len(data)>20*1024*1024: raise HTTPException(413,'File limit: 20 MB')
    suffix=Path(file.filename or '').suffix.lower()
    allowed={'docxpdf':{'.docx'},'xlsxpdf':{'.xlsx'},'pptxpdf':{'.pptx'},'txtpdf':{'.txt'},'htmlpdf':{'.html','.htm'},'jpgpng':{'.jpg','.jpeg'},'pngjpg':{'.png'},'webp':{'.png','.jpg','.jpeg','.webp'},'imgpdf':{'.png','.jpg','.jpeg','.webp'}}
    if suffix not in allowed.get(kind,{'.pdf'}): raise HTTPException(400,'Unsupported extension')
    async with slots:
        if await request.is_disconnected(): raise HTTPException(499, "Client disconnected")
        with TemporaryDirectory() as d:
            src=Path(d)/('input'+suffix); out=Path(d)/('output.'+KINDS[kind]); src.write_bytes(data)
            try:
                await run_job(request,'convert',kind,src,out)
                if not out.exists() or not out.stat().st_size: raise ValueError('Empty output')
                if out.stat().st_size>100*1024*1024: raise ValueError('Output exceeds 100 MB')
                return Response(out.read_bytes(),media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="converted.{KINDS[kind]}"','Cache-Control':'no-store'})
            except HTTPException: raise
            except Exception as e: raise HTTPException(422,'Conversion failed: '+str(e)[:200]) from None

@app.post('/compress/{mode}')
async def compress(mode:str,request:Request,file:UploadFile=File(...)):
    from compression_engine import compress_pdf, PRESETS
    if mode not in PRESETS: raise HTTPException(400,'Unknown compression mode')
    data=await file.read(20*1024*1024+1)
    if not data or len(data)>20*1024*1024: raise HTTPException(413,'File limit: 20 MB')
    async with slots:
        if await request.is_disconnected(): raise HTTPException(499, "Client disconnected")
        try:
            with TemporaryDirectory() as d:
                src=Path(d)/'input.pdf'; out=Path(d)/'output.pdf'; src.write_bytes(data)
                await run_job(request,'compress',mode,src,out)
                result=out.read_bytes()
            return Response(result,media_type='application/pdf',headers={'Cache-Control':'no-store'})
        except HTTPException: raise
        except Exception as e: raise HTTPException(422,str(e)[:200]) from None
