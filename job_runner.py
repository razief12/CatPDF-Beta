import sys
from pathlib import Path
if __name__ == '__main__':
    mode, kind, source, output = sys.argv[1:]
    src, out = Path(source), Path(output)
    if mode == 'convert':
        from engine import convert
        convert(kind, src, out)
    else:
        from compression_engine import compress_pdf
        out.write_bytes(compress_pdf(src.read_bytes(), kind))
