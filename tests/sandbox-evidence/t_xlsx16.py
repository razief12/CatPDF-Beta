exec(open('run_import16.py').read())
import shutil, subprocess, tempfile
from pathlib import Path
from pypdf import PdfReader
def raw_lo(src,outpdf):
    with tempfile.TemporaryDirectory() as d:
        d=Path(d); s=d/'input.xlsx'; shutil.copy(src,s)
        subprocess.run(['libreoffice','-env:UserInstallation='+(d/'p').as_uri(),'--headless','--convert-to','pdf','--outdir',str(d),str(s)],capture_output=True,timeout=120)
        shutil.copy(d/'input.pdf',outpdf)
def repo(src,outpdf):
    with tempfile.TemporaryDirectory() as d:
        d=Path(d); s=d/'input.xlsx'; shutil.copy(src,s); o=d/'output.pdf'; engine.convert('xlsxpdf',s,o); shutil.copy(o,outpdf)
def txt(p): return subprocess.run(['pdftotext','-layout',str(p),'-'],capture_output=True,text=True).stdout
def imgs(p): return len(subprocess.run(['pdfimages','-list',str(p)],capture_output=True,text=True).stdout.strip().splitlines()[2:])
for name in ['t.xlsx','t_shape.xlsx']:
    raw_lo('docs/'+name,f'out/raw_{name}.pdf'); repo('docs/'+name,f'out/repo16_{name}.pdf')
    a,b=txt(f'out/raw_{name}.pdf'),txt(f'out/repo16_{name}.pdf')
    print(f'\n===== {name}: pages raw={len(PdfReader(f"out/raw_{name}.pdf").pages)} repo={len(PdfReader(f"out/repo16_{name}.pdf").pages)}')
    print('--- RAW LibreOffice text (ground truth of source as LO renders it):'); print(a[:900])
    print('--- REPO office() text:'); print(b[:900])
    for tok in ['SHAPE-TEXTBOX-TOKEN','CHART-TITLE-XYZ','MERGED-XL','HIDDEN-SHEET-TOKEN']:
        print(f'  token {tok:22s} raw={tok in a!s:5} repo={tok in b!s:5}')
