exec(open('run_import.py').read())
import tempfile, shutil, subprocess, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw
from pypdf import PdfReader
def conv(kind,img,suffix):
    with tempfile.TemporaryDirectory() as d:
        d=Path(d); s=d/('input'+suffix); img(s); o=d/('output.'+engine.KINDS[kind]); engine.convert(kind,s,o)
        keep=Path('out')/f'{kind}{suffix}.{engine.KINDS[kind]}'; shutil.copy(o,keep); srck=Path('out')/f'src_{kind}{suffix}'; shutil.copy(s,srck); return keep,srck
def mk_photo(path,fmt,size=(640,480),**kw):
    rng=np.random.default_rng(1); y,x=np.mgrid[0:size[1],0:size[0]]
    a=np.stack([(x*255/size[0]),(y*255/size[1]),((x+y)*127/(size[0]+size[1]))+rng.integers(0,30,(size[1],size[0]))],-1).clip(0,255).astype('uint8')
    im=Image.fromarray(a); d=ImageDraw.Draw(im); d.rectangle([50,50,300,200],outline=(255,0,0),width=1); d.text((60,100),'Sharp text 12345',fill=(0,0,0)); im.save(path,fmt,**kw)
def err(a,b):
    A=np.asarray(a.convert('RGB'),float); B=np.asarray(b.convert('RGB'),float); return np.abs(A-B).max(), np.abs(A-B).mean()
def chk(l,ok,d=''): print(('PASS ' if ok else 'FAIL ')+l+(' | '+d if d else ''))
# JPG->PNG lossless
o,s=conv('jpgpng',lambda p:mk_photo(p,'JPEG',quality=90),'.jpg'); mx,mean=err(Image.open(s),Image.open(o)); chk('jpgpng pixel-identical decode',mx==0,f'maxerr={mx}')
# PNG->JPG
o,s=conv('pngjpg',lambda p:mk_photo(p,'PNG'),'.png'); mx,mean=err(Image.open(s),Image.open(o)); print(f'INFO pngjpg q95 maxerr={mx:.0f} meanerr={mean:.2f} (lossy by nature)')
# PNG alpha -> JPG flatten
def alpha(p): im=Image.new('RGBA',(100,100),(255,0,0,0)); ImageDraw.Draw(im).ellipse([20,20,80,80],fill=(0,0,255,255)); im.save(p)
o,s=conv('pngjpg',alpha,'.png'); px=Image.open(o).getpixel((2,2)); chk('pngjpg transparent->white (documented flatten)',px[0]>245 and px[1]>245 and px[2]>245,str(px))
# WebP lossless incl alpha
o,s=conv('webp',alpha,'.png'); a=np.asarray(Image.open(s).convert('RGBA')).astype(int); b=np.asarray(Image.open(o).convert('RGBA')).astype(int)
vis=a[...,3]>0; chk('webp lossless RGBA: alpha identical and every visible pixel identical (hidden RGB under alpha=0 may differ - libwebp behaviour)',np.array_equal(a[...,3],b[...,3]) and np.array_equal(a[vis],b[vis]))
o,s=conv('webp',lambda p:mk_photo(p,'PNG'),'.png'); chk('webp lossless RGB identical',np.array_equal(np.asarray(Image.open(s).convert('RGB')),np.asarray(Image.open(o).convert('RGB'))))
# metadata: ICC + DPI + EXIF orientation
def meta(p):
    im=Image.new('RGB',(200,100),'white'); ImageDraw.Draw(im).rectangle([0,0,50,50],fill='red')
    ex=Image.Exif(); ex[274]=6; im.save(p,'JPEG',dpi=(300,300),exif=ex)
o,s=conv('jpgpng',meta,'.jpg'); r=Image.open(o); print(f'INFO jpgpng EXIF-rotated size {Image.open(s).size}->{r.size}; dpi kept={r.info.get("dpi")}')
chk('jpgpng preserves DPI metadata',r.info.get('dpi') is not None,str(r.info.get('dpi')))
# imgpdf: page size & quality
def a4(p): mk_photo(p,'PNG',size=(2480,3508),dpi=(300,300))
o,s=conv('imgpdf',a4,'.png'); pg=PdfReader(str(o)).pages[0]; w,h=float(pg.mediabox.width),float(pg.mediabox.height)
chk('imgpdf A4@300dpi PNG -> A4 page (595x842pt)',abs(w-595)<2 and abs(h-842)<2,f'got {w:.0f}x{h:.0f}pt = {w/72*25.4:.0f}x{h/72*25.4:.0f}mm')
subprocess.run(['pdftoppm','-r','72','-png',str(o),'out/imgpdf_render'],check=True)
def sharp(p): mk_photo(p,'PNG',size=(800,600))
o,s=conv('imgpdf',sharp,'.png'); lst=subprocess.run(['pdfimages','-list',str(o)],capture_output=True,text=True).stdout.splitlines()[2]; print('INFO imgpdf embedded image stream:',' '.join(lst.split()[:10]))
subprocess.run(['pdfimages','-all',str(o),'out/imgpdf_extract'],check=True); ex=sorted(Path('out').glob('imgpdf_extract*'))[0]
mx,mean=err(Image.open(s),Image.open(ex)); chk('imgpdf lossless embedding of PNG source',mx==0,f'extracted {ex.suffix} maxerr={mx:.0f} meanerr={mean:.2f}')
# oversize
def big(p): Image.new('RGB',(6000,4000),'gray').save(p,'JPEG')
with tempfile.TemporaryDirectory() as d:
    d=Path(d); s=d/'input.jpg'; big(s)
    try: engine.convert('jpgpng',s,d/'o.png'); print('INFO 24MP jpg accepted')
    except Exception as e: print('INFO 24MP jpg rejected (explicit, not silent):',str(e)[:90])
