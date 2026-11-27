import io, zipfile
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.section import WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image, ImageDraw
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Font, PatternFill, Alignment
from pptx import Presentation
from pptx.util import Inches as PI, Pt as PP
D=Path('/home/claude/work/docs'); D.mkdir(exist_ok=True)
# marker image
im=Image.new('RGB',(300,120),'white'); d=ImageDraw.Draw(im); d.rectangle([5,5,294,114],outline='red',width=4); d.text((20,50),'IMG-MARKER-7731',fill='blue'); im.save(D/'marker.png')
# ---- DOCX
doc=Document(); s=doc.sections[0]; s.page_width=Inches(8.5); s.page_height=Inches(11)
s.header.paragraphs[0].text='HEADER-TOKEN-AAA'; s.footer.paragraphs[0].text='FOOTER-TOKEN-BBB'
doc.add_heading('Title Alpha 2026',0)
doc.add_paragraph('Unicode: caf\u00e9 \u00f1 \u20ac \u00b5m \u2264 \u00b2 \u00b0C \u03a9 \u00bd \u201cquoted\u201d \u2014 dash. Numbers: 1,234.56 0.00012 007 -45.50')
t=doc.add_table(rows=3,cols=3); t.style='Table Grid'
for r in range(3):
    for c in range(3): t.cell(r,c).text=f'R{r}C{c}'
t.cell(0,0).merge(t.cell(0,1)); t.cell(0,0).text='MERGED-HDR'
sh=OxmlElement('w:shd'); sh.set(qn('w:fill'),'FFFF00'); t.cell(1,0)._tc.get_or_add_tcPr().append(sh)
doc.add_picture(str(D/'marker.png'),width=Inches(2))
doc.add_page_break(); doc.add_paragraph('PAGE-TWO-TOKEN')
ns=doc.add_section(); ns.orientation=WD_ORIENT.LANDSCAPE; ns.page_width=Inches(11); ns.page_height=Inches(8.5)
doc.add_paragraph('LANDSCAPE-SECTION-TOKEN')
doc.save(D/'t.docx')
# calibri-dense doc for font test
d2=Document(); st=d2.styles['Normal']; st.font.name='Calibri'; st.font.size=Pt(11)
for i in range(60): d2.add_paragraph(f'Line {i}: The quick brown fox jumps over the lazy dog while measuring widths of Calibri text across wrapped lines to expose substitution differences. '*2)
d2.save(D/'calibri.docx')
# ---- XLSX
wb=Workbook(); ws=wb.active; ws.title='Data'
rows=[('Label','Value'),('currency',1234.5),('currency3',1234.567),('pct',0.1234),('general_long',1234.56789012345),('general_narrow',3.14159265358979),('float_sum',0.1+0.2),('bigint',12345678901234),('text007','007'),('formula','=SUM(B2:B3)'),('stale','=1+1')]
for r in rows: ws.append(r)
ws['B2'].number_format='"RM" #,##0.00'; ws['B3'].number_format='"RM" #,##0.00'; ws['B4'].number_format='0.0%'
ws.column_dimensions['B'].width=9; ws['B6'].number_format='General'
ws['A1'].font=Font(bold=True,color='FFFFFF'); ws['A1'].fill=PatternFill('solid',fgColor='1F4E78')
ws.merge_cells('D1:E1'); ws['D1']='MERGED-XL'
ch=BarChart(); ch.title='CHART-TITLE-XYZ'; ch.add_data(Reference(ws,min_col=2,min_row=1,max_row=4),titles_from_data=True); ws.add_chart(ch,'G2')
hid=wb.create_sheet('HiddenSheet'); hid['A1']='HIDDEN-SHEET-TOKEN'; hid.sheet_state='hidden'
wb.save(D/'t.xlsx')
# inject text-box shape (xdr:sp) into the drawing + stale cached value
zin=zipfile.ZipFile(D/'t.xlsx'); zout=zipfile.ZipFile(D/'t_shape.xlsx','w',zipfile.ZIP_DEFLATED)
for it in zin.infolist():
    data=zin.read(it.filename)
    if it.filename.startswith('xl/drawings/drawing') and it.filename.endswith('.xml'):
        s=data.decode()
        sp=('<xdr:twoCellAnchor><xdr:from><xdr:col>0</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>14</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>'
            '<xdr:to><xdr:col>4</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>18</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to>'
            '<xdr:sp macro="" textlink=""><xdr:nvSpPr><xdr:cNvPr id="99" name="TextBox 99"/><xdr:cNvSpPr txBox="1"/></xdr:nvSpPr>'
            '<xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1000000" cy="500000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="FFFF99"/></a:solidFill></xdr:spPr>'
            '<xdr:txBody><a:bodyPr/><a:p><a:r><a:rPr lang="en-US"/><a:t>SHAPE-TEXTBOX-TOKEN</a:t></a:r></a:p></xdr:txBody></xdr:sp><xdr:clientData/></xdr:twoCellAnchor>')
        s=s.replace('</xdr:wsDr>',sp+'</xdr:wsDr>'); data=s.encode()
    if it.filename=='xl/worksheets/sheet1.xml':
        s=data.decode(); s=s.replace('<f>1+1</f><v></v>','<f>1+1</f><v>5</v>').replace('<f>1+1</f><v />','<f>1+1</f><v>5</v>')
        if '<f>1+1</f><v>' not in s: s=s.replace('<f>1+1</f>','<f>1+1</f><v>5</v>')
        data=s.encode()
    zout.writestr(it,data)
zout.close()
# ---- PPTX
p=Presentation(); p.slide_width=PI(13.333); p.slide_height=PI(7.5)
for i in range(3):
    sl=p.slides.add_slide(p.slide_layouts[5]); sl.shapes.title.text=f'SLIDE-{i+1}-TITLE'
    tb=sl.shapes.add_textbox(PI(1),PI(2),PI(6),PI(1)); tb.text_frame.text=f'Body \u00e9\u00f1 \u20ac 1,234.56 slide {i+1}'
    if i==1: sl.shapes.add_picture(str(D/'marker.png'),PI(2),PI(3.5),width=PI(3))
    if i==2:
        tbl=sl.shapes.add_table(2,2,PI(1),PI(3.5),PI(5),PI(1.2)).table; tbl.cell(0,0).text='TBL-A'; tbl.cell(1,1).text='TBL-D'
    sl.notes_slide.notes_text_frame.text='NOTES-TOKEN'
p.save(D/'t.pptx')
print('docs built', sorted(x.name for x in D.iterdir()))
