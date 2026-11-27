# Import the REAL engine.py with fitz/weasyprint replaced by inert stubs (module-level only).
import sys, types
for name in ('fitz',):
    m=types.ModuleType(name); sys.modules[name]=m
w=types.ModuleType('weasyprint'); w.HTML=None; sys.modules['weasyprint']=w
sys.path.insert(0,'/home/claude/work/p16')
import engine
