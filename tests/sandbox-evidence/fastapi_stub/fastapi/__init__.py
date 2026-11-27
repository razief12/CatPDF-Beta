class HTTPException(Exception):
    def __init__(self,status_code,detail=None): self.status_code=status_code; self.detail=detail
class UploadFile:
    def __init__(self,filename,data): self.filename=filename; self._d=data
    async def read(self,n=-1): return self._d[:n] if n>=0 else self._d
class Request:
    def __init__(self,disc=None): self._disc=disc or (lambda:False)
    async def is_disconnected(self): return self._disc()
def File(*a,**k): return None
class FastAPI:
    def __init__(self,**k): pass
    def add_middleware(self,*a,**k): pass
    def get(self,p): return lambda f:f
    def post(self,p): return lambda f:f
