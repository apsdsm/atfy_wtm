class Response:
    def __init__(self, ok:bool, res, status:str = ""):
        self.ok = ok
        self.status = status
        self.res = res