class Logger():
    def __init__(self, log: bool):
        self.log = log
    
    def log_info(self, *args) -> None:
        if self.log is False:
            return
        s = 'LOG INFO:'
        for ss in args:
            s = s + str(ss)
        print(s)
