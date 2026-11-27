"""Editable geometry-aware PDF export for unrotated text/table pages."""
import re
import fitz
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def xml(parent, tag, **attrs):
    e=OxmlElement('w:'+tag)
    for k,v in attrs.items(): e.set(qn('w:'+k),str(v))
    parent.append(e); return e

def fmt(p, spans, x0=0, x1=None):
    f=p.paragraph_format; f.space_before=f.space_after=Pt(0)
    size=max((s['size'] for s in spans),default=9); f.line_spacing=Pt(size*1.12)
    if spans and x1 is not None:
        left=min(s['bbox'][0] for s in spans)-x0; right=x1-max(s['bbox'][2] for s in spans)
        if abs(left-right)<3 and left>3: p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        elif right<left and right<9: p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    for s in spans:
        r=p.add_run(s['text']); font=s['font'].split('+')[-1]; font=re.sub(r'[-,]?(BoldItalic|BoldOblique|Regular|Bold|Italic|Oblique|PSMT|MT)$','',font)
        font={'LiberationSerif':'Liberation Serif','LiberationSans':'Liberation Sans','TimesNewRoman':'Times New Roman','Arial':'Arial'}.get(font,font)
        r.font.name=font; r.font.size=Pt(s['size']); r.bold=bool(s['flags']&16); r.italic=bool(s['flags']&2); r.font.color.rgb=RGBColor.from_string(f"{s['color']:06X}")

def center(s):
    b=s['bbox']; return fitz.Point((b[0]+b[2])/2,(b[1]+b[3])/2)

def detect(page):
    # Ignore filled background rectangles when locating actual table borders.
    strict=page.find_tables(strategy='lines_strict').tables
    return strict if strict else page.find_tables().tables

def export(pdf,out):
    # Keep legacy mixed/scan handling and rotated pages intact.
    if any(p.rotation or p.get_images() or any(b['type']==1 for b in p.get_text('dict')['blocks']) for p in pdf): return False
    # Keep only the first positive detection; avoid retaining every page in memory.
    first_index=None; first_page=None; first_tables=None
    for i,p in enumerate(pdf):
        found=detect(p)
        if found:
            first_index,first_page,first_tables=i,p,found
            break
    if first_index is None: return False
    doc=Document(); normal=doc.styles['Normal']; normal.font.size=Pt(1); normal.paragraph_format.space_after=Pt(0); normal.paragraph_format.space_before=Pt(0); normal.paragraph_format.line_spacing=Pt(1)
    for i,page in enumerate(pdf):
        sec=doc.sections[0] if i==0 else doc.add_section(WD_SECTION.NEW_PAGE)
        sec.page_width=Pt(page.rect.width); sec.page_height=Pt(page.rect.height); sec.left_margin=sec.right_margin=Pt(0); sec.top_margin=sec.bottom_margin=Pt(0)
        lines=[l for b in page.get_text('dict')['blocks'] for l in b.get('lines',[]) if l.get('spans')]; spans=[s for l in lines for s in l['spans'] if s['text'].strip()]
        centered=[[(s,center(s)) for s in l['spans']] for l in lines]
        tables=first_tables if i==first_index else ([] if i<first_index else detect(page)); drawings=page.get_drawings(); events=[(t.bbox[1],t.bbox[0],t.bbox[3],t) for t in tables]
        for l in lines:
            ss=[s for s in l['spans'] if not any(fitz.Rect(t.bbox).contains(center(s)) for t in tables)]
            if ss: events.append((l['bbox'][1],l['bbox'][0],l['bbox'][3],ss))
        cursor=0
        for y,x,bottom,obj in sorted(events,key=lambda e:(e[0],e[1])):
            gap=max(0,y-cursor)
            if isinstance(obj,list):
                p=doc.add_paragraph(); fmt(p,obj); p.paragraph_format.left_indent=Pt(max(0,x)); p.paragraph_format.space_before=Pt(gap); cursor=max(cursor,y+max(s['size'] for s in obj)*1.12); continue
            if gap>1:
                p=doc.add_paragraph(); p.paragraph_format.line_spacing=Pt(gap)
            t=obj; n=t.col_count; edges=sorted({round(c[0],1) for r in t.rows for c in r.cells if c}|{round(t.bbox[2],1)})
            if len(edges)!=n+1: edges=[t.bbox[0]+j*(t.bbox[2]-t.bbox[0])/n for j in range(n+1)]
            widths=[edges[j+1]-edges[j] for j in range(n)]; table=doc.add_table(rows=t.row_count,cols=n); table.autofit=False; table.alignment=WD_TABLE_ALIGNMENT.LEFT
            pr=table._tbl.tblPr; xml(pr,'tblInd',w=round(x*20),type='dxa'); margins=xml(pr,'tblCellMar')
            for side in ('top','bottom','left','right'): xml(margins,side,w=0,type='dxa')
            borders=xml(pr,'tblBorders')
            for side in ('top','left','bottom','right','insideH','insideV'): xml(borders,side,val='single',sz=2,color='C5CBD3')
            for col,w in zip(table.columns,widths): col.width=Pt(w)
            for ri,row in enumerate(t.rows):
                rr=table.rows[ri]; rr.height=Pt(row.bbox[3]-row.bbox[1]); rr.height_rule=WD_ROW_HEIGHT_RULE.EXACTLY; xml(rr._tr.get_or_add_trPr(),'cantSplit')
                for cell,w in zip(rr.cells,widths): cell.width=Pt(w)
                for ci,rect in enumerate(row.cells):
                    if rect is None: continue
                    end=ci
                    while end+1<n and row.cells[end+1] is None and rect[2]>=edges[end+2]-2: end+=1
                    cell=rr.cells[ci]
                    if end>ci: cell=cell.merge(rr.cells[end])
                    cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER; r=fitz.Rect(rect); cp=cell._tc.get_or_add_tcPr()
                    for d in drawings:
                        if d.get('fill') is not None and d.get('fill_opacity',1)>=.95 and any(it[0]=='re' and (fitz.Rect(it[1])&r).get_area()>=.85*r.get_area() for it in d['items']):
                            fill=''.join(f'{round(c*255):02X}' for c in d['fill'][:3]); old=cp.find(qn('w:shd'))
                            if old is not None: cp.remove(old)
                            xml(cp,'shd',fill=fill)
                    cell_lines=[[s for s,pt in line if r.contains(pt)] for line in centered]; cell_lines=[ss for ss in cell_lines if ss]
                    for j,ss in enumerate(cell_lines):
                        p=cell.paragraphs[0] if j==0 else cell.add_paragraph(); fmt(p,ss,r.x0,r.x1)
                        if p.alignment is None: p.paragraph_format.left_indent=Pt(max(0,min(s['bbox'][0] for s in ss)-r.x0))
            cursor=max(cursor,bottom)
        if not events: doc.add_paragraph()
    doc.save(out); return True
