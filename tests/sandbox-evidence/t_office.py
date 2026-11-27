exec(open('run_import.py').read())
import shutil, subprocess, time, tempfile
from pathlib import Path
from pypdf import PdfReader
D=Path('docs')
def run(kind,srcname):
    with tempfile.TemporaryDirectory() as d:
        d=Path(d); src=d/('input'+Path(srcname).suffix); shutil.copy(D/srcname,src); out=d/'output.pdf'
        t=time.time(); engine.convert(kind,src,out); el=time.time()-t
        keep=Path('out')/(kind+'_'+srcname+'.pdf'); shutil.copy(out,keep)
        return keep,el
def info(pdf):
    r=PdfReader(str(pdf)); sizes=[(round(float(p.mediabox.width)),round(float(p.mediabox.height))) for p in r.pages]
    txt=subprocess.run(['pdftotext','-layout',str(pdf),'-'],capture_output=True,text=True).stdout
    imgs=subprocess.run(['pdfimages','-list',str(pdf)],capture_output=True,text=True).stdout.strip().splitlines()[2:]
    return len(r.pages),sizes,txt,len(imgs)
def check(label,ok,detail=''): print(('PASS ' if ok else 'FAIL ')+label+(' | '+detail if detail else ''))
# DOCX
pdf,el=run('docxpdf','t.docx'); n,sz,txt,ni=info(pdf); print(f'--- docxpdf ({el:.1f}s) pages={n} sizes={sz} images={ni}')
for tok in ['Title Alpha 2026','HEADER-TOKEN-AAA','FOOTER-TOKEN-BBB','caf\u00e9','\u20ac','\u00b5m','\u2264','\u00b2','\u00b0C','\u03a9','\u00bd','1,234.56','0.00012','007','-45.50','MERGED-HDR','R1C0','R2C2','PAGE-TWO-TOKEN','LANDSCAPE-SECTION-TOKEN']:
    check('docx token '+repr(tok),tok in txt)
check('docx page count (expect 3)',n==3,str(n)); check('docx page1 Letter 612x792',sz[0]==(612,792),str(sz[0])); check('docx last page landscape 792x612',sz[-1]==(792,612),str(sz[-1])); check('docx image count==1',ni==1,str(ni))
# PPTX
pdf,el=run('pptxpdf','t.pptx'); n,sz,txt,ni=info(pdf); print(f'--- pptxpdf ({el:.1f}s) pages={n} sizes={sz} images={ni}')
for tok in ['SLIDE-1-TITLE','SLIDE-2-TITLE','SLIDE-3-TITLE','1,234.56','TBL-A','TBL-D','\u20ac']: check('pptx token '+repr(tok),tok in txt)
check('pptx slide count==3',n==3,str(n)); check('pptx size 960x540',sz[0]==(960,540),str(sz[0])); check('pptx image>=1',ni>=1,str(ni))
check('pptx notes NOT in output (LO default; informational)','NOTES-TOKEN' not in txt)
