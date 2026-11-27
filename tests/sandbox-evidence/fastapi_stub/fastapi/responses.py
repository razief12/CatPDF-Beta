class Response:
    def __init__(self,content,media_type=None,headers=None): self.body=content; self.media_type=media_type; self.headers=headers or {}
