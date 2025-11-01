class Task:

    def print_line(self, desc, level=1, end='\n'):
        if end == ' ':
            desc += '...'
        if level == 1:
            print(f'{"["+self.pref+"]":<56} {desc}', end=end)
        elif level == 2:
            print(f'{"["+self.pref+"]":<56}   - {desc}', end=end)

    def print_ok(self):
        print('\033[92m\033[1mok!\033[0m')

    def print_failed(self, level=2):
        if level == 1:
            self.print_line('\033[0;31m\033[1mfailed\033[0m', level=2)
        else:
            print('\033[0;31m\033[1mfailed\033[0m')

    def print_done(self):
        self.print_line('\033[92m\033[1mdone\033[0m', level=2)

    def __init__(self, pref, desc, cplx=False):
        self.pref = pref
        self.desc = desc
        self.cplx = cplx
        
    def __enter__(self):
        if self.cplx:
            self.print_line(self.desc)
        else:
            self.print_line(self.desc, end=' ')
        return self
    
    def subtask(self, desc):
        self.print_line(desc, level=2, end=' ')

    def __exit__(self, exception_type, exception_value, exception_traceback):
        if exception_type is not None:
            if self.cplx:
                self.print_failed(level=1)
            else:
                self.print_failed()
        else:
            if self.cplx:
                self.print_done()
            else:
                self.print_ok()
        
class Subtask:
    def __init__(self, desc, task):
        self.task = task
        self.desc = desc
    def __enter__(self):
        self.task.subtask(self.desc)
    def __exit__(self, exception_type, exception_value, exception_traceback):
        if exception_type is not None:
            self.task.print_failed()
        else:
            self.task.print_ok()
    






