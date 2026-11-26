import fitz

PRESETS={'low':(300,95),'medium':(200,90),'high':(150,80)}
def compress_pdf(data, mode):
    dpi, quality=PRESETS[mode]
    with fitz.open(stream=data,filetype='pdf') as doc:
        if doc.needs_pass: raise ValueError('Encrypted PDF is not supported')
        doc.rewrite_images(dpi_threshold=int(dpi*1.25),dpi_target=dpi,quality=quality,lossy=True,lossless=False,bitonal=False)
        result=doc.tobytes(garbage=3,deflate=True)
    return result if len(result)<len(data) else data
