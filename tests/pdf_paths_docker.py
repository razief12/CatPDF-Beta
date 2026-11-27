#!/usr/bin/env python3
"""Content-verified regression for every PDF->X converter (run inside the Docker image, where PyMuPDF exists):
    docker run --rm -v "$PWD:/app" -w /app catpdf-beta python tests/pdf_paths_docker.py
HTTP 200 / file-exists is never counted as PASS. `--selftest` exercises the checkers on fabricated outputs (no PyMuPDF needed).
Status FAIL lines tagged [AUDIT Sx] are defects identified by static review of engine.py; this harness is what confirms or refutes them."""
import sys, io, zipfile, re, base64, tempfile, shutil, time
from pathlib import Path
HERE=Path(__file__).resolve().parent; sys.path.insert(0,str(HERE.parent))
SCAN_B64=(HERE/'scan.b64').read_text().strip()
def build_pdf(pages):
    """pages: list of dict(w,h,ops=content stream str, image=bool). Pure-python PDF writer (independent of PyMuPDF)."""
    objs={}; n=len(pages); kids=[]; nxt=4+2*n
    objs[1]=b'<< /Type /Catalog /Pages 2 0 R >>'; objs[3]=b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
    for i,p in enumerate(pages):
        pid,cid=4+2*i,5+2*i; kids.append(pid); res='/Font << /F1 3 0 R >>'; content=p['ops']
        if p.get('image'):
            iid=nxt; nxt+=1; res+=f' /XObject << /Im0 {iid} 0 R >>'; content+=' q 400 0 0 114 100 %d cm /Im0 Do Q'%p.get('imy',560)
            jpg=base64.b64decode(SCAN_B64); objs[iid]=(f'<< /Type /XObject /Subtype /Image /Width 420 /Height 120 /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /DCTDecode /Length {len(jpg)} >>'.encode(),jpg)
        objs[pid]=f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {p["w"]} {p["h"]}] /Contents {cid} 0 R /Resources << {res} >> >>'.encode()
        c=content.encode(); objs[cid]=(f'<< /Length {len(c)} >>'.encode(),c)
    objs[2]=f'<< /Type /Pages /Kids [{" ".join(f"{k} 0 R" for k in kids)}] /Count {n} >>'.encode()
    out=bytearray(b'%PDF-1.4\n'); off={}
    for k in sorted(objs):
        off[k]=len(out); o=objs[k]
        if isinstance(o,tuple): out+=f'{k} 0 obj\n'.encode()+o[0]+b'\nstream\n'+o[1]+b'\nendstream\nendobj\n'
        else: out+=f'{k} 0 obj\n'.encode()+o+b'\nendobj\n'
    x=len(out); m=max(objs)+1; out+=f'xref\n0 {m}\n0000000000 65535 f \n'.encode()+b''.join(f'{off[k]:010d} 00000 n \n'.encode() for k in range(1,m))+f'trailer\n<< /Size {m} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n'.encode()
    return bytes(out)
def txt(x,y,s,sz=11): return f'BT /F1 {sz} Tf {x} {y} Td ({s}) Tj ET '
def table(x,y,rows,cw=(120,90,110),rh=24):
    ops=''; W=sum(cw); H=rh*len(rows)
    for r in range(len(rows)+1): ops+=f'0.6 w {x} {y-r*rh} m {x+W} {y-r*rh} l S '
    xx=x
    for w in (0,)+cw: xx+=w if w else 0; ops+=f'0.6 w {xx if w else x} {y} m {xx if w else x} {y-H} l S '
    for r,row in enumerate(rows):
        xx=x
        for c,v in enumerate(row): ops+=txt(xx+6,y-r*rh-16,v); xx+=cw[c]
    return ops
ROWS=[['Item','Qty','Amount'],['A1','007','RM 1,234.567'],['A2','12.500','RM 99.999'],['A3','1,234','RM 1,234']]
def fixture():
    p1=dict(w=612,h=792,ops=txt(72,740,'CATPDF-P1-TEXT total RM 1,234.567 code 007',12)+table(72,700,ROWS))
    p2=dict(w=612,h=792,ops=txt(72,740,'CATPDF-P2-FIGURE-CAPTION'),image=True,imy=560)
    p3=dict(w=612,h=792,ops='',image=True,imy=600)          # image-only (scanned) page
    p4=dict(w=792,h=612,ops=txt(72,560,'CATPDF-P4-LANDSCAPE'))
    return build_pdf([p1,p2,p3,p4])
TOK=['CATPDF-P1-TEXT','1,234.567','CATPDF-P2-FIGURE-CAPTION','CATPDF-P4-LANDSCAPE']
NUMS=['RM 1,234.567','RM 99.999','12.500','007']
R=[]
def rec(kind,name,ok,detail='',tag=''): R.append((kind,name,'PASS' if ok else 'FAIL',detail,tag)); print(f'{"PASS" if ok else "FAIL"}  {kind:12s} {name}'+(f'  [{detail}]' if detail else '')+(f'  {tag}' if tag and not ok else ''))
# ---------- checkers (pure functions over output bytes) ----------
def chk_txt(data):
    t=data.decode('utf-8'); out=[('all text tokens present',all(k in t for k in TOK),''),('numbers verbatim',all(n in t for n in NUMS if n!='RM 99.999' or True) ,''),('4 pages => 3 page separators',t.count('\f')==3,str(t.count('\f'))),('image-only page flagged, not silent',bool(re.search(r'NOT extracted|OCR',t)),'')]
    return [(a,b,c,'') for a,b,c in out]
def chk_docx(data):
    from docx import Document
    d=Document(io.BytesIO(data)); text='\n'.join([p.text for p in d.paragraphs]+[c.text for t in d.tables for r in t.rows for c in r.cells]); pics=len(d.inline_shapes); s=d.sections[0]
    return [('all text tokens present',all(k in text for k in TOK),''),('numbers verbatim',all(n in text for n in NUMS),''),('real Word table(s) created',len(d.tables)>=1,str(len(d.tables))),
            ('image-only page keeps its picture',pics>=1,f'{pics} pictures'),('figure on text page (P2) preserved: >=2 pictures',pics>=2,f'{pics} pictures','[AUDIT S1]'),
            ('page 1 size 612x792',abs(s.page_width.pt-612)<1 and abs(s.page_height.pt-792)<1,''),('landscape page 4 has its own landscape section',any(x.page_width.pt>x.page_height.pt for x in d.sections),f'{len(d.sections)} sections','[AUDIT S4]'),
            ('scan page notice present',bool(re.search(r'NOT extracted',text)),'')]
def chk_xlsx(data):
    from openpyxl import load_workbook
    wb=load_workbook(io.BytesIO(data)); cells=[(c.value,c.number_format) for ws in wb for row in ws.iter_rows() for c in row if c.value is not None]; vals=[v for v,_ in cells]; imgs=sum(len(ws._images) for ws in wb)
    num=[(v,f) for v,f in cells if isinstance(v,(int,float))]; shown=lambda v,f:(f.count('0')-f.split('.')[0].count('0')) if '.' in f else 0
    return [('4 sheets (one per page)',len(wb.sheetnames)==4,str(wb.sheetnames)),('CATPDF tokens present',all(any(isinstance(v,str) and k in v for v in vals) for k in ['CATPDF-P1-TEXT','CATPDF-P4-LANDSCAPE']),''),
            ('1234.567 kept with 3 displayed decimals (no rounding)',any(abs(v-1234.567)<1e-9 and shown(v,f)>=3 for v,f in num) or any(isinstance(v,str) and '1,234.567' in v for v in vals),str([(v,f) for v,f in num][:3]),'[AUDIT S2]'),
            ("'007' not turned into 7",'007' in vals or '007' in [str(v) for v in vals],'' ,'[AUDIT S2]'),('figure on text page preserved (>=1 image in workbook)',imgs>=1,f'{imgs} images','[AUDIT S1]')]
def chk_md(data):
    t=data.decode('utf-8'); return [('tokens present',all(k in t for k in TOK),''),('table kept as pipe table with exact numbers',bool(re.search(r'\|.*1,234\.567.*\|',t)),''),('image-only page flagged',bool(re.search(r'NOT extracted',t)),''),('figure on text page preserved (![ or <img)',bool(re.search(r'!\[|<img',t)),'','[AUDIT S1]')]
def chk_html_semantic(data):
    t=data.decode('utf-8'); return [('tokens present',all(k in t for k in TOK),''),('<table> reconstructed',t.count('<table')>=1,''),('images embedded (figure + scan page >=2)',t.count('<img')>=2,str(t.count('<img'))),('4 sections',t.count('<section')==4,str(t.count('<section')))]
def chk_html_preserve(data):
    t=data.decode('utf-8'); return [('4 page sections',t.count('<section')==4,str(t.count('<section'))),('vector/text SVG present',t.count('<svg')>=4,''),('page sizes preserved in @page rules',all(s in t for s in ['612pt 792pt','792pt 612pt']),'')]
def chk_pptx(data):
    from pptx import Presentation
    p=Presentation(io.BytesIO(data)); pics=[sum(1 for s in sl.shapes if s.shape_type==13) for sl in p.slides]
    return [('4 slides',len(p.slides)==4,str(len(p.slides))),('every slide has its page image',all(x>=1 for x in pics),str(pics)),('(info) slide size follows first page only; mixed orientation letterboxed',True,f'{p.slide_width}x{p.slide_height}')]
def chk_zip(data):
    from PIL import Image
    z=zipfile.ZipFile(io.BytesIO(data)); names=sorted(z.namelist()); sz=[Image.open(io.BytesIO(z.read(n))).size for n in names]
    return [('4 PNG pages',len(names)==4 and all(n.endswith('.png') for n in names),str(names)),('portrait/landscape aspect preserved',sz[0][0]<sz[0][1] and sz[3][0]>sz[3][1],str(sz)),('>=144 dpi (width>=1224 px for 8.5in)',sz[0][0]>=1224,str(sz[0]))]
N=lambda rows:[(r+('',))[:4] for r in rows]
CHECKS={'pdftxt':chk_txt,'pdfmd':chk_md,'pdfdocx':chk_docx,'pdfxlsx':chk_xlsx,'pdfsemantic':chk_html_semantic,'pdfhtml':chk_html_preserve,'pdfpptx':chk_pptx,'pdfimg':chk_zip}
def run_all():
    try: import engine
    except Exception as e: print('NOT RUN: engine cannot import here ->',repr(e)); return 2
    pdf=fixture(); d=Path(tempfile.mkdtemp()); src=d/'input.pdf'; src.write_bytes(pdf)
    for kind,fn in CHECKS.items():
        out=d/('o.'+engine.KINDS[kind]); t=time.time()
        try: engine.convert(kind,src,out); data=out.read_bytes()
        except Exception as e: rec(kind,'conversion completes',False,repr(e)[:160]); continue
        rec(kind,'conversion completes, non-empty',len(data)>0,f'{time.time()-t:.1f}s {len(data)} bytes')
        try:
            for name,ok,detail,tag in N(fn(data)): rec(kind,name,ok,detail,tag)
        except Exception as e: rec(kind,'output opens/parses',False,repr(e)[:160])
    f=sum(1 for r in R if r[2]=='FAIL'); print(f'\nSUMMARY: {len(R)-f} PASS, {f} FAIL'); return 1 if f else 0
def selftest():
    from docx import Document; from docx.shared import Inches
    good=Document(); good.add_paragraph(' '.join(TOK)+' RM 1,234.567 RM 99.999 12.500 007 NOT extracted'); t=good.add_table(2,2); [t.cell(0,0).__setattr__('text','x')]
    from PIL import Image; b=io.BytesIO(); Image.new('RGB',(10,10)).save(b,'PNG'); good.add_picture(io.BytesIO(b.getvalue())); good.add_picture(io.BytesIO(b.getvalue())); g=io.BytesIO(); good.save(g)
    bad=Document(); bad.add_paragraph('CATPDF-P1-TEXT only'); bb=io.BytesIO(); bad.save(bb)
    gp=N(chk_docx(g.getvalue())); bp=N(chk_docx(bb.getvalue()))
    assert all(ok for n,ok,d,t in gp if 'landscape' not in n),gp; assert not any(ok for n,ok,d,t in bp if n in('all text tokens present','numbers verbatim','real Word table(s) created','image-only page keeps its picture')),bp
    assert N(chk_txt(('\f'.join(['A '+' '.join(TOK)+' '+' '.join(NUMS),'b','NOT extracted','c'])).encode()))[0][1]; assert not N(chk_txt(b'nothing'))[0][1]
    pdf=fixture(); assert pdf.startswith(b'%PDF') ; (HERE/'fixture.pdf').write_bytes(pdf); print('SELFTEST OK: checkers accept good output, reject bad output; fixture written to tests/fixture.pdf'); return 0
if __name__=='__main__': sys.exit(selftest() if '--selftest' in sys.argv else run_all())
