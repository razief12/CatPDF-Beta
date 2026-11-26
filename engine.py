from pathlib import Path
import subprocess, zipfile, io, html, re, warnings, base64, math
from copy import copy
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.pagebreak import Break
import fitz
from PIL import Image, ImageOps
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import RGBColor
from bs4 import BeautifulSoup
from pptx import Presentation
from pptx.util import Inches as PI
from weasyprint import HTML

KINDS={'pdfdocx':'docx','pdfxlsx':'xlsx','pdfpptx':'pptx','pdfimg':'zip','pdftxt':'txt','pdfhtml':'html','pdfsemantic':'html','pdfmd':'md','docxpdf':'pdf','xlsxpdf':'pdf','pptxpdf':'pdf','imgpdf':'pdf','txtpdf':'pdf','htmlpdf':'pdf','jpgpng':'png','pngjpg':'jpg','webp':'webp'}
Image.MAX_IMAGE_PIXELS=20_000_000
warnings.simplefilter("error", Image.DecompressionBombWarning)

def no_fetch(url,*args,**kwargs):
    raise ValueError('External resources disabled')

def prepare_excel_layout(src):
    # Modify only the temporary upload, never the user's original workbook.
    wb = load_workbook(src)
    cached = load_workbook(src, data_only=True)
    try:
        # Approximate Excel General display before automatic column resizing.
        # Explicit number formats and underlying numeric values remain untouched.
        for ws in wb.worksheets:
            if ws.sheet_state != 'visible': continue
            for row in ws.iter_rows():
                for cell in row:
                    if cell.number_format != 'General': continue
                    value = cached[ws.title][cell.coordinate].value if cell.data_type == 'f' else cell.value
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value): continue
                    if value == int(value) or abs(value) < 0.0001 or abs(value) >= 1e11: continue
                    width = next((d.width for d in ws.column_dimensions.values() if d.min and d.min <= cell.column <= d.max), ws.sheet_format.defaultColWidth or 8.43)
                    budget = min(11, max(1, int(width * 11 / (cell.font.sz or 11))))
                    integer_digits = len(str(int(abs(value)))) + (value < 0)
                    decimals = budget - integer_digits - 1
                    if decimals > 0 and round(value, decimals) != 0:
                        cell.number_format = '0.' + '#' * decimals

        for ws in wb.worksheets:
            if ws.sheet_state != 'visible':
                continue
            if ws.page_setup.orientation or ws.page_setup.scale or ws.page_setup.fitToWidth is not None:
                continue
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.page_setup.scale = None
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0
            if not ws.page_setup.paperSize:
                ws.page_setup.paperSize = ws.PAPERSIZE_A4
            if ws.max_column >= 6:
                ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
            elif not ws.page_setup.orientation:
                ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
            ws.col_breaks.brk = []
            # Compact only automatically laid out sheets; keep explicit print settings.
            header = next((r for r in range(1,min(ws.max_row,8)+1)
                           if str(ws.cell(r,1).value).strip().lower() in ('item no.','bill item','no.','element type')),None)
            if header:
                labels=[str(ws.cell(header,c).value or '').lower() for c in range(1,ws.max_column+1)]
                if ws.max_column>=6:
                    # Wrap text instead of shrinking an excessively wide table.
                    for c,label in enumerate(labels,1):
                        width=(55 if ws.max_column<=6 else 29) if any(x in label for x in ('description','remarks','location','reinforcement','dimensions')) else 10 if 'item' in label or label=='no.' else 16 if ws.max_column<=6 else 12
                        dim=ws.column_dimensions[get_column_letter(c)]; dim.min=dim.max=c; dim.width=width
                    for row in ws.iter_rows(min_row=header):
                        lines=1
                        for cell in row:
                            if cell.value is None or cell.__class__.__name__=='MergedCell': continue
                            if any(m.min_row<=cell.row<=m.max_row and m.min_col<=cell.column<=m.max_col for m in ws.merged_cells.ranges): continue
                            a=copy(cell.alignment); a.wrap_text=True; cell.alignment=a
                            if isinstance(cell.value,str) and cell.data_type!='f':
                                width=ws.column_dimensions[get_column_letter(cell.column)].width
                                lines=max(lines,math.ceil(len(cell.value)/max(1,width-3)))
                        ws.row_dimensions[row[0].row].height=max(ws.row_dimensions[row[0].row].height or 15,lines*14+4)
                    ws.print_title_rows=f'{header}:{header}'
                summary=next((r for r in range(header+1,ws.max_row+1) if str(ws.cell(r,1).value or '').upper().startswith('GRAND SUMMARY')),None)
                if summary and ws.max_row-summary<=15:
                    # Fixed scaling lets Calc honor manual page breaks.
                    widths=sum(next((d.width for d in ws.column_dimensions.values() if d.min and d.min<=c<=d.max),13) for c in range(1,ws.max_column+1))
                    ws.sheet_properties.pageSetUpPr.fitToPage=False
                    ws.page_setup.fitToWidth=None; ws.page_setup.fitToHeight=None
                    ws.page_setup.scale=max(10,min(100,int(100* (841.89-72)/(widths*7.5))))
                    ws.row_breaks.append(Break(id=summary-1))

        wb.save(src)
    finally:
        wb.close()
        cached.close()

def office(src,out):
    with zipfile.ZipFile(src) as z:
        if len(z.infolist())>5000 or sum(i.file_size for i in z.infolist())>150_000_000: raise ValueError('Office archive too large')
        if any('vbaProject' in i.filename or 'externalLinks/' in i.filename for i in z.infolist()): raise ValueError('Macros and external workbook links are not supported')
    if src.suffix.lower() == '.xlsx': prepare_excel_layout(src)
    p=subprocess.run(['libreoffice','-env:UserInstallation='+ (out.parent/'profile').as_uri(),'--headless','--convert-to','pdf','--outdir',str(out.parent),str(src)],capture_output=True,timeout=90)
    generated=src.with_suffix('.pdf')
    if p.returncode or not generated.exists(): raise ValueError('Office rendering failed')
    generated.replace(out)

def page_blocks(page):
    tables=page.find_tables(strategy="lines_strict").tables or page.find_tables().tables
    blocks=[]
    for t in tables: blocks.append((t.bbox[1],t.bbox[0],'table',t))
    for b in page.get_text('blocks',sort=True):
        if b[6]!=0: continue
        # Keep text outside detected table bounds, including partially overlapping blocks.
        lines=[]
        for line in page.get_text('dict',clip=fitz.Rect(b[:4]))['blocks']:
            for l in line.get('lines',[]):
                r=fitz.Rect(l['bbox']); center=( (r.x0+r.x1)/2,(r.y0+r.y1)/2 )
                if not any(fitz.Rect(t.bbox).contains(fitz.Point(*center)) for t in tables): lines.append(''.join(s['text'] for s in l['spans']))
        if lines: blocks.append((b[1],b[0],'text','\n'.join(lines)))
    return sorted(blocks,key=lambda b:(b[0],b[1]))

def clean_cell(v):
    return re.sub(r'\b(SECTIO)\s*\n\s*N\b', 'SECTION', re.sub(r'\bSUBTO\s*\n\s*TAL\b','SUBTOTAL',v))

def cell_style(page,rect,drawings,allspans):
    if not rect: return None,'000000',False
    r=fitz.Rect(rect); pt=fitz.Point((r.x0+r.x1)/2,(r.y0+r.y1)/2); bg=None
    for d in drawings:
        if d.get('fill') is not None and d.get('fill_opacity',1) >= .95 and r.get_area()>0 and any(item[0]=='re' and (fitz.Rect(item[1]) & r).get_area() >= .85*r.get_area() for item in d['items']):
            bg=''.join(f'{round(c*255):02X}' for c in d['fill'][:3])
    spans=[s for s in allspans if r.contains(fitz.Point((s['bbox'][0]+s['bbox'][2])/2,(s['bbox'][1]+s['bbox'][3])/2))]
    s=max(spans,key=lambda x:len(x['text']),default={})
    return bg,f"{s.get('color',0):06X}",bool(s.get('flags',0)&16)

def legacy_html(soup,pages):
    parts=[]
    for i,p in enumerate(pages):
        w,h=re.search(r'width:([\d.]+)pt;height:([\d.]+)pt',p['style']).groups()
        p['id']=f'page{i}'; p['style']+=f';position:relative;page:cat{i};break-after:page'
        for line in p.find_all('p',recursive=False):
            line['style']=line.get('style','')+';position:absolute;margin:0;white-space:nowrap'
            for span in line.find_all('span'):
                span['style']=span.get('style','').replace('color:#ffffff','color:#000000')
        parts.append(f'<style>@page cat{i}{{size:{w}pt {h}pt;margin:0}}</style>'+str(p))
    return '<!doctype html><meta charset=utf-8><style>body{margin:0}div:last-child{break-after:auto}</style>'+''.join(parts)

def unique_svg(svg, page):
    prefix=f'p{page}_'
    svg=re.sub(r'\bid="([^"]+)"',lambda m:f'id="{prefix}{m[1]}"',svg)
    svg=re.sub(r'(href="\#|url\(#)([^"\)]+)',lambda m:m[1]+prefix+m[2],svg)
    return svg

def scanned(p):
    return not p.get_text().strip() and bool(p.get_images())

def ocr_page(p):
    scale=min(2.5, 2400/max(p.rect.width,p.rect.height))
    png=p.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).tobytes('png')
    result=subprocess.run(['tesseract','stdin','stdout','-l','eng+msa'],input=png,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=35,check=True)
    return result.stdout.decode('utf-8',errors='replace').strip()

def convert(kind,src,out):
    if kind in ('docxpdf','xlsxpdf','pptxpdf'): office(src,out); return
    if kind in ('txtpdf','htmlpdf'):
        text=src.read_text(encoding='utf-8-sig');
        if kind=='txtpdf': text='<meta charset=utf-8><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+html.escape(text)+'</pre>'
        if kind=='htmlpdf':
            soup=BeautifulSoup(text,'html.parser')
            # Repair legacy PyMuPDF exports only, not arbitrary HTML.
            pages=soup.find_all('div',id=re.compile(r'^page\d+$'),recursive=False)
            if pages and all(re.search(r'width:[\d.]+pt;height:[\d.]+pt',x.get('style','')) for x in pages):
                text=legacy_html(soup,pages)
            else:
                text='<style>@page{size:A4;margin:12mm}img,svg{max-width:100%}table{max-width:100%;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'+text
        HTML(string=text,url_fetcher=no_fetch).write_pdf(out); return
    if kind in ('jpgpng','pngjpg','webp','imgpdf'):
        with Image.open(src) as im:
            im=ImageOps.exif_transpose(im); im.load()
            if kind in ('pngjpg','imgpdf'):
                rgba=im.convert('RGBA'); bg=Image.new('RGB',rgba.size,'white'); bg.paste(rgba,mask=rgba.getchannel('A')); im=bg
            else: im=im.convert('RGBA' if 'A' in im.getbands() or 'transparency' in im.info else 'RGB')
            im.save(out,format={'jpgpng':'PNG','pngjpg':'JPEG','webp':'WEBP','imgpdf':'PDF'}[kind],**({'quality':95} if kind=='pngjpg' else {'lossless':True} if kind=='webp' else {})); return
    with fitz.open(src) as pdf:
        if pdf.needs_pass or not 1<=len(pdf)<=100: raise ValueError('Encrypted PDF or page limit exceeded (100)')
        if kind=='pdftxt':
            pages=[(ocr_page(p) or '[OCR: no readable text detected]') if scanned(p) else p.get_text('text',sort=True) for p in pdf]
            out.write_text('\n\f\n'.join(pages),encoding='utf-8'); return
        if kind=='pdfimg':
            with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
                for i,p in enumerate(pdf): z.writestr(f'page-{i+1:03}.png',p.get_pixmap(matrix=fitz.Matrix(min(2, 2200/max(p.rect.width,p.rect.height)),min(2, 2200/max(p.rect.width,p.rect.height))),alpha=False).tobytes('png'))
            return
        if kind=='pdfpptx':
            deck=Presentation(); r=pdf[0].rect; deck.slide_width=PI(10); deck.slide_height=PI(10*r.height/r.width)
            for p in pdf:
                slide=deck.slides.add_slide(deck.slide_layouts[6]); r=p.rect; k=min(deck.slide_width/r.width,deck.slide_height/r.height); w=int(r.width*k); h=int(r.height*k); slide.shapes.add_picture(io.BytesIO(p.get_pixmap(matrix=fitz.Matrix(min(2, 2200/max(p.rect.width,p.rect.height)),min(2, 2200/max(p.rect.width,p.rect.height))),alpha=False).tobytes('png')),int((deck.slide_width-w)/2),int((deck.slide_height-h)/2),width=w,height=h)
            deck.save(out); return
        if kind=='pdfhtml':
            parts=[]
            for i,p in enumerate(pdf):
                # SVG preserves vector artwork, backgrounds and text positioning.
                w,h=p.rect.width,p.rect.height
                parts.append(f'<style>@page cat{i}{{size:{w}pt {h}pt;margin:0}}</style><section style="page:cat{i};width:{w}pt;height:{h}pt;break-after:page">'+unique_svg(p.get_svg_image(text_as_path=False),i)+'</section>')
            out.write_text('<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0}svg{display:block;width:100%;height:100%}section:last-child{break-after:auto}</style></head><body>'+''.join(parts)+'</body></html>',encoding='utf-8'); return
        if kind=='pdfsemantic':
            parts=[]
            for i,p in enumerate(pdf):
                parts.append(f'<section><h2>Page {i+1}</h2>')
                if scanned(p):
                    parts.append('<p>OCR transcription: '+html.escape(ocr_page(p) or '[No readable text detected]').replace('\n','<br>')+'</p>')
                drawings=p.get_drawings()
                spans=[sp for b in p.get_text('dict',flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)['blocks'] for l in b.get('lines',[]) for sp in l['spans']]
                blocks=page_blocks(p)
                for b in p.get_text('dict')['blocks']:
                    if b['type']==1:
                        blocks.append((b['bbox'][1],b['bbox'][0],'image',b))
                for _,__,typ,data in sorted(blocks,key=lambda b:(b[0],b[1])):
                    if typ=='image':
                        with Image.open(io.BytesIO(data['image'])) as im:
                            buf=io.BytesIO(); im.convert('RGBA').save(buf,format='PNG')
                        encoded=base64.b64encode(buf.getvalue()).decode('ascii')
                        width=data['bbox'][2]-data['bbox'][0]
                        parts.append(f'<figure><img alt="Embedded PDF image" style="max-width:100%;height:auto;width:{width}pt" src="data:image/png;base64,{encoded}"></figure>')
                        continue
                    if typ=='text':
                        parts.append('<p>'+html.escape(data).replace('\n','<br>')+'</p>'); continue
                    parts.append('<table><tbody>')
                    for ri,row in enumerate(data.extract()):
                        tag='th' if ri==0 else 'td'
                        cells=[]
                        for ci,v in enumerate(row):
                            rect=data.rows[ri].cells[ci]
                            bg,fg,bold=cell_style(p,rect,drawings,spans)
                            if bg==fg: fg='FFFFFF' if bg=='000000' else '000000'
                            style=f'color:#{fg};'+(f'background-color:#{bg};' if bg else '')+('font-weight:bold;' if bold else '')
                            cells.append(f'<{tag} style="{style}">'+html.escape(clean_cell(v or '')).replace('\n','<br>')+f'</{tag}>')
                        parts.append('<tr>'+''.join(cells)+'</tr>')
                    parts.append('</tbody></table>')
                parts.append('</section>')
            out.write_text('<!doctype html><html><head><meta charset="utf-8"><title>Editable PDF export</title><style>body{font:14px sans-serif;margin:24px}table{border-collapse:collapse;margin:12px 0;max-width:100%}td,th{border:1px solid #aaa;padding:5px;text-align:left}th{background:#e6edf7}section{break-after:page}section:last-child{break-after:auto}</style></head><body>'+''.join(parts)+'</body></html>',encoding='utf-8'); return
        doc=Document() if kind=='pdfdocx' else None; wb=Workbook() if kind=='pdfxlsx' else None; md=[]
        if wb: wb.remove(wb.active)
        for i,p in enumerate(pdf):
            blocks=page_blocks(p)
            drawings=p.get_drawings(); allspans=[s for b in p.get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if s['text'].strip()]
            if doc and i: doc.add_page_break()
            if doc and i==0:
                sec=doc.sections[0]; sec.page_width=Pt(p.rect.width); sec.page_height=Pt(p.rect.height); sec.left_margin=sec.right_margin=Pt(24); sec.top_margin=sec.bottom_margin=Pt(24)
            if wb: ws=wb.create_sheet(f'Page {i+1}'); row=1
            md.append(f'## Page {i+1}')
            if scanned(p):
                text=ocr_page(p) or '[No readable text detected]'
                if doc:
                    doc.add_paragraph('OCR transcription (review accuracy): '+text)
                    scale=min(2,1800/max(p.rect.width,p.rect.height))
                    doc.add_picture(io.BytesIO(p.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).tobytes('png')),width=Pt(min(400,doc.sections[0].page_width.pt-48)))
                if wb:
                    for line in ('OCR transcription (review accuracy): '+text).splitlines():
                        ws.cell(row,1,line).data_type='s'; row+=1
                md.append('OCR transcription (review accuracy): '+text)
                continue
            for _,__,typ,data in blocks:
                if typ=='text':
                    if doc: doc.add_paragraph(data)
                    if wb: ws.cell(row,1,data).data_type='s'; row+=1
                    md.append(data); continue
                t=data; data=t.extract(); n=t.col_count
                if not n: continue
                widths=[max(1,min((rr.cells[ci][2]-rr.cells[ci][0] for rr in t.rows if rr.cells[ci] is not None),default=(t.bbox[2]-t.bbox[0])/n)) for ci in range(n)]
                if doc:
                    table=doc.add_table(rows=len(data),cols=n); table.style='Table Grid'; table.autofit=False
                    scale=min(1,(p.rect.width-48)/sum(widths))
                    for col,w in zip(table.columns,widths): col.width=Pt(w*scale)
                    for rr in table.rows:
                        for cell,w in zip(rr.cells,widths): cell.width=Pt(w*scale)
                if wb:
                    for ci,w in enumerate(widths):
                        from openpyxl.utils import get_column_letter
                        ws.column_dimensions[get_column_letter(ci+1)].width=max(5,w/5.5)
                for ri,values in enumerate(data):
                    for ci,v in enumerate(values):
                        v=clean_cell(v or '')
                        bg,fg,bold=cell_style(p,t.rows[ri].cells[ci],drawings,allspans)
                        if doc:
                            cell=table.cell(ri,ci); cell.text=v
                            for para in cell.paragraphs:
                                para.paragraph_format.space_after=Pt(0)
                                rect=t.rows[ri].cells[ci]
                                spans=[sp for sp in allspans if rect and fitz.Rect(rect).contains(fitz.Point((sp['bbox'][0]+sp['bbox'][2])/2,(sp['bbox'][1]+sp['bbox'][3])/2))]
                                dominant=max(spans,key=lambda sp:len(sp['text']),default={})
                                if dominant and rect:
                                    left=min(sp['bbox'][0] for sp in spans)-rect[0]; right=rect[2]-max(sp['bbox'][2] for sp in spans)
                                    if abs(left-right)<3 and left>3: para.alignment=WD_ALIGN_PARAGRAPH.CENTER
                                    elif right<left and right<8: para.alignment=WD_ALIGN_PARAGRAPH.RIGHT
                                para.paragraph_format.space_before=Pt(0)
                                para.paragraph_format.line_spacing=1.0
                                for run in para.runs:
                                    run.font.size=Pt(dominant.get('size',8)); run.bold=bold; run.font.color.rgb=RGBColor.from_string(fg)
                            if bg:
                                sh=OxmlElement('w:shd'); sh.set(qn('w:fill'),bg); cell._tc.get_or_add_tcPr().append(sh)
                        if wb:
                            c=ws.cell(row+ri,ci+1,v); c.data_type='s'; c.alignment=Alignment(wrap_text=True,vertical='top'); c.border=Border(**{s:Side(style='thin',color='BBBBBB') for s in ('left','right','top','bottom')}); c.font=Font(bold=bold,color=fg); c.fill=PatternFill('solid',fgColor=bg) if bg else PatternFill();
                            if ci>0 and re.fullmatch(r'RM\s*-?[\d,]+(?:\.\d+)?',v):
                                c.value=float(v[2:].strip().replace(',','')); c.number_format='"RM" #,##0.00'
                            if ci>0 and re.fullmatch(r'-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?',v) and len(v.replace(',','').replace('.','').replace('-',''))<=15:
                                header=(data[0][ci] or '').lower();
                                if re.search(r'qty|quantity|rate|amount|times|weight|factor|\(m\)',header):
                                    c.value=float(v.replace(',','')) if '.' in v else int(v.replace(',','')); c.number_format='#,##0.'+'0'*len(v.rsplit('.',1)[1]) if '.' in v else '#,##0'
                    vals=[clean_cell(v or '').replace('|','\\|').replace('\n','<br>') for v in values]; md.append('| '+' | '.join(vals+['']*(n-len(vals)))+' |')
                    if ri==0: md.append('| '+' | '.join(['---']*n)+' |')
                # Merge only cells whose detected geometry spans adjacent columns.
                for ri,rr in enumerate(t.rows):
                    for ci,rect in enumerate(rr.cells):
                        if rect is None: continue
                        end=ci
                        while end+1<n and rr.cells[end+1] is None and rect[2]>=t.bbox[0]+sum(widths[:end+2])-2: end+=1
                        if end>ci:
                            if doc: table.cell(ri,ci).merge(table.cell(ri,end))
                            if wb: ws.merge_cells(start_row=row+ri,start_column=ci+1,end_row=row+ri,end_column=end+1)
                if wb: row+=len(data)+1
                md.append('')
            if wb:
                for col in ws.columns:
                    pass # table geometry determines widths
        if doc: doc.save(out)
        elif wb: wb.save(out)
        else: out.write_text('\n\n'.join(md).replace(' |\n\n|',' |\n|'),encoding='utf-8')
