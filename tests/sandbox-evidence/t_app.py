import os, sys, asyncio, subprocess, tempfile, time
os.environ['PYTHONPATH']='/home/claude/work/stubs_ok:/home/claude/work/p16'
sys.path[:0]=['/home/claude/work/fastapi_stub','/home/claude/work/stubs_ok','/home/claude/work/p16']
import app
from fastapi import UploadFile, Request, HTTPException
R=[]
def chk(l,ok,d=''): R.append(ok); print(('PASS ' if ok else 'FAIL ')+l+(' | '+d if d else ''))
def up(path,name=None): return UploadFile(name or os.path.basename(path),open(path,'rb').read())
async def call(kind,file,disc=None):
    try: return await app.run(kind,Request(disc),file)
    except HTTPException as e: return e
async def main():
    h=app.health(); chk('/health reports version + kinds',h['version']=='4.5.6.5.23' and 'pdfdocx' in h['kinds'],str(h['version']))
    # success path through the real subprocess
    t=time.time(); r=await call('docxpdf',up('docs/t.docx')); 
    ok=hasattr(r,'body') and r.body[:5]==b'%PDF-'
    chk('docxpdf end-to-end via worker subprocess',ok,f'{time.time()-t:.1f}s' if ok else f'{getattr(r,"status_code",r)} {getattr(r,"detail","")}')
    if ok:
        open('out/app_docx.pdf','wb').write(r.body); txt=subprocess.run(['pdftotext','out/app_docx.pdf','-'],capture_output=True,text=True).stdout
        chk('content check on API output (tokens)',all(k in txt for k in ['HEADER-TOKEN-AAA','PAGE-TWO-TOKEN','LANDSCAPE-SECTION-TOKEN','café']))
    # Xlsx with shape via API (regression for silent loss)
    r=await call('xlsxpdf',up('docs/t_shape.xlsx')); ok=hasattr(r,'body'); 
    if ok:
        open('out/app_shape.pdf','wb').write(r.body); txt=subprocess.run(['pdftotext','out/app_shape.pdf','-'],capture_output=True,text=True).stdout
        chk('xlsxpdf via API keeps text box + cached value',('SHAPE-TEXTBOX-TOKEN' in txt) and ('stale' in txt and '5' in txt))
    else: chk('xlsxpdf via API',False,str(r.detail))
    # engine error is surfaced to the client verbatim-safe
    bad=app.UploadFile('x.docx',b'this is not a zip'); r=await call('docxpdf',bad)
    chk('corrupt input -> 422 with real reason',getattr(r,'status_code',0)==422 and 'zip' in r.detail.lower(),str(getattr(r,'detail',r)))
    # engine unavailable deps (stub fitz) -> reason, not "check server logs"
    pdf=app.UploadFile('x.pdf',open('docs/marker.png','rb').read()); r=await call('pdftxt',pdf)
    chk('PDF-path error surfaced with specific reason',getattr(r,'status_code',0)==422 and 'check server logs' not in r.detail.lower(),str(getattr(r,'detail',r))[:120])
    # validation
    chk('unknown kind 404',(await call('nope',up('docs/t.docx'))).status_code==404)
    chk('wrong extension 400',(await call('docxpdf',up('docs/t.xlsx','a.xlsx'))).status_code==400)
    chk('empty file 413',(await call('docxpdf',UploadFile('a.docx',b''))).status_code==413)
    # client already gone -> job never starts
    t=time.time(); r=await call('docxpdf',up('docs/t.docx'),disc=lambda:True); chk('disconnected client: job not started (499)',getattr(r,'status_code',0)==499 and time.time()-t<1)
    # queue: client disconnects while waiting behind another job -> released without running
    async def slow():
        return await call('docxpdf',up('docs/t.docx'))
    a=asyncio.create_task(slow()); await asyncio.sleep(.05)
    flag={'d':False}; b=asyncio.create_task(call('docxpdf',up('docs/t.docx'),disc=lambda:flag['d'])); await asyncio.sleep(.1); flag['d']=True
    ra,rb=await asyncio.gather(a,b); chk('queued request abandoned by client is skipped; first job unaffected',hasattr(ra,'body') and getattr(rb,'status_code',0)==499,f'{type(ra).__name__}/{getattr(rb,"status_code",type(rb).__name__)}')
asyncio.run(main()); print('\nSUMMARY: %d/%d passed'%(sum(R),len(R)))
