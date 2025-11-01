from typing import Set
from instrlib.middleware import _thread_locals

def with_purposes(purposes : Set[str]):
    def decorator(function):
        def wrapper(*args, **kwargs):
            if hasattr(_thread_locals, 'request'):
                current_purposes = _thread_locals.request.META.get("purposes", {"service"})
                _thread_locals.request.META['purposes'] = current_purposes | purposes
            result = function(*args, **kwargs)
            if hasattr(_thread_locals, 'request'):
                _thread_locals.request.META['purposes'] = current_purposes
            return result
        wrapper.__name__ = function.__name__
        wrapper.__qualname__ = function.__qualname__
        return wrapper
    return decorator

def with_purpose(purpose : str):
    return with_purposes({purpose})