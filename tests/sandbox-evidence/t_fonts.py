import subprocess, shutil, tempfile, os
from pathlib import Path
from pypdf import PdfReader
def conv(env_extra):
    with tempfile.TemporaryDirectory() as d:
        d=Path(d); s=d/'input.docx'; shutil.copy('docs/calibri.docx',s)
        env=dict(os.environ); env.update(env_extra)
        subprocess.run(['libreoffice','-env:UserInstallation='+(d/'p').as_uri(),'--headless','--convert-to','pdf','--outdir',str(d),str(s)],capture_output=True,timeout=180,env=env)
        pdf=d/'input.pdf'; n=len(PdfReader(str(pdf)).pages); fonts=subprocess.run(['pdffonts',str(pdf)],capture_output=True,text=True).stdout.split('\n')[2:5]
        return n,[' '.join(f.split()[:1]) for f in fonts if f.strip()]
a=conv({}); b=conv({'FONTCONFIG_FILE':str(Path('fonts-dockerlike.conf').resolve())})
print('Calibri docx, sandbox fonts (Carlito present): pages=%d fonts=%s'%a)
print('Calibri docx, Dockerfile-like fonts          : pages=%d fonts=%s'%b)
