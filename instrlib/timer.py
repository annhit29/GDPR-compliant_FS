from threading import Lock, Event

class Timer:

    def __init__(self):
        self.current_time      = 0
        self.current_time_lock = Lock()
        self.timerflag         = Event()
        self.first_time        = True