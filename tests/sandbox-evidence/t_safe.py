import sys,importlib
for mod in ('run_import.py','run_import16.py'):
    for k in [k for k in list(sys.modules) if k in('engine',)]: del sys.modules[k]
    exec(open(mod).read())
    import shutil,subprocess,tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        d=Path(d); s=d/'input.xlsx'; shutil.copy('docs/safe.xlsx',s); o=d/'o.pdf'; engine.convert('xlsxpdf',s,o)
        t=subprocess.run(['pdftotext','-layout',str(o),'-'],capture_output=True,text=True).stdout
        print(mod,'->',' | '.join(l.strip() for l in t.splitlines() if l.strip()))
