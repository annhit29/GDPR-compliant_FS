"""
An event consists of a name and some potential arguments
"""
from typing import Any, Callable, List, Tuple

from instrlib.middleware import _thread_locals

class Event:

    def __init__(self, name : str, *args : Any, with_purpose : bool = False):
        self.name         : str             = name
        self.args         : Tuple[Any, ...] = args
        self.with_purpose : bool            = with_purpose

    def copies_with_purposes(self):
        if self.with_purpose:
            if hasattr(_thread_locals, 'request'):
                purposes = _thread_locals.request.META.get("purposes", {"service"})
                if "bypass" in purposes:
                    return []
                else:
                    return [Event(self.name, *(list(self.args) + [purpose])) for purpose in purposes]
            else:
                return [Event(self.name, *(list(self.args) + ["internal"]))]
        else:
            return [self]

    def get_num_args(self) -> int:
        return len(self.args)
    
    def format(self, s : Any) -> str:
        s = str(s)
        if not s.isnumeric():
            return '"' + s.replace('"', '\\"') + '"'
        else:
            return s
        
    def __str__(self) -> str:
        args = [arg if not callable(arg) else arg.__name__ for arg in self.args]
        args_str = ', '.join(map(self.format, args))
        return f"{self.name}({args_str})"
        
    def __repr__(self) -> str:
        return self.__str__()
    
    def __hash__(self) -> int:
        return hash(repr(self))
    
    def __eq__(self, other) -> bool:
        return hash(self) == hash(other)


"""
returns event with a specified name and a list of events, 
with the specified functions applied to its arguments
"""
class Generic(Event):

    def __init__(self, name : str, *args : Callable[..., Any], with_purpose : bool = False):
        super().__init__(name, *args, with_purpose = with_purpose)

    def __call__(self, *args : List[Any]) -> List[Event]:
        list = [f(*args) for f in self.args]
        return Event(self.name, *list, with_purpose = self.with_purpose).copies_with_purposes()
                

"""returns Event with no arguments, only the name"""
class Simple(Generic):

    def __init__(self, name : str, with_purpose : bool = False):
        super().__init__(name, with_purpose = with_purpose)
        
    def __call__(self, *args : Any) -> List[Event]:
        return Event(self.name, with_purpose = self.with_purpose).copies_with_purposes()


class Functional(Event):

    def __init__(self, name : str, f : Callable[..., List[Event]], with_purpose : bool = False):
        super().__init__(name, f, with_purpose = with_purpose)
    
    def __call__(self, *args : Any, **kwargs : Any) -> List[Event]:
        events : List[Event] = self.args[0](*args, **kwargs)
        return [event_copy for event in events for event_copy in event.copies_with_purposes()]
    

class TimedTuple:

    def __init__(self, tsp : float, event_tuple : Tuple[Any, ...], expects_response : bool = True):
        self.tsp              = tsp
        self.event_tuple      = event_tuple
        self.expects_response = expects_response

    def __lt__(self, other : "TimedTuple") -> bool:
        return self.tsp < other.tsp
