from tempfile import TemporaryDirectory
from pathlib import Path
from engine import convert,KINDS
from docx import Document
from PIL import Image
import fitz,zipfile
with TemporaryDirectory() as d:
 p=Path(d); doc=Document();doc.add_paragraph('CatPDF test');doc.save(p/'test.docx');Image.new('RGB',(100,100),'red').save(p/'test.png');Image.new('RGB',(100,100),'red').save(p/'test.jpg');(p/'test.txt').write_text('CatPDF test');(p/'test.html').write_text('<h1>CatPDF test</h1>');base=Path('/mnt/data');pdf=base/'quantity_taking_off_report_smk_ambrose.pdf'; sources={'docxpdf':p/'test.docx','xlsxpdf':base/'bq_taking_off_smk_ambrose_en-v5.xlsx','pptxpdf':base/'chapter5part2implementationofmanagementinconstructionproject.pptx','imgpdf':p/'test.png','txtpdf':p/'test.txt','htmlpdf':p/'test.html','jpgpng':p/'test.jpg','pngjpg':p/'test.png','webp':p/'test.png'}
 import shutil
 for k,ext in KINDS.items():
  try:
   folder=p/k;folder.mkdir();src=folder/('input'+sources.get(k,pdf).suffix);shutil.copy(sources.get(k,pdf),src);out=folder/('output.'+ext);convert(k,src,out);assert out.stat().st_size>0
   if ext=='pdf':
    with fitz.open(out) as f: assert len(f)>0
   elif ext in ('docx','xlsx','pptx','zip'):
    with zipfile.ZipFile(out) as z: assert z.testzip() is None
   elif ext in ('jpg','png','webp'):
    with Image.open(out) as im: im.verify()
   print(k,'PASS smoke',out.stat().st_size,flush=True)
  except Exception as e: print(k,'FAIL',repr(e),flush=True)
