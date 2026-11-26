from pathlib import Path
from tempfile import TemporaryDirectory
import asyncio, os, sys, signal, logging
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
KINDS={'pdfdocx':'docx','pdfxlsx':'xlsx','pdfpptx':'pptx','pdfimg':'zip','pdftxt':'txt','pdfhtml':'html','pdfsemantic':'html','pdfmd':'md','docxpdf':'pdf','xlsxpdf':'pdf','pptxpdf':'pdf','imgpdf':'pdf','txtpdf':'pdf','htmlpdf':'pdf','jpgpng':'png','pngjpg':'jpg','webp':'webp'}
logger=logging.getLogger("uvicorn.error")
app=FastAPI(title='CatPDF Conversion API')
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CATPDF_ORIGINS','https://razief12.github.io,http://localhost:8000').split(','),allow_methods=['POST','GET'],allow_headers=['*'])
slots=asyncio.Semaphore(1)
async def run_job(request, mode, kind, src, out):
    log_path=out.parent/'worker.log'
    with log_path.open('wb') as log:
        proc = await asyncio.create_subprocess_exec(sys.executable, str(Path(__file__).resolve().with_name('job_runner.py')), mode, kind, str(src), str(out), start_new_session=True, stdout=log, stderr=log)
    try:
        deadline = asyncio.get_running_loop().time() + 150
        while proc.returncode is None:
            if await request.is_disconnected():
                raise HTTPException(499, 'Client disconnected')
            if asyncio.get_running_loop().time() >= deadline:
                raise HTTPException(504, 'Processing timed out')
            await asyncio.sleep(.2)
        if proc.returncode != 0:
            with log_path.open('rb') as f:
                f.seek(max(0,log_path.stat().st_size-8192))
                logger.error('Worker %s/%s exit %s: %s',mode,kind,proc.returncode,f.read().decode('utf-8',errors='replace'))
            raise ValueError(f'Conversion worker failed (exit {proc.returncode}). Check server logs.')
    finally:
        if proc.returncode is None:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        await proc.wait()

@app.get('/health')
def health(): return {'status':'ok','version':'4.5.6.5.19'}
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
    if mode not in ('low','medium','high'): raise HTTPException(400,'Unknown compression mode')
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
