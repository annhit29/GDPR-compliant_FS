from itertools import chain
from typing import Any, Callable, Dict, Tuple, Union

from instrlib.handler_graph import generate_graph
from instrlib.event import Event

    
class InstrumentationMapping:

    def __init__(self, mapper : dict[str, Callable[[Event], list[Event] | Event | None]], ignore_other : bool = False):
        self.mapper       = mapper
        self.ignore_other = ignore_other
    
    def __call__(self, f : Callable[..., list[Event]]) -> Callable[..., list[Event]]:
        def wrapper(*args, **kwargs):
            events = f(*args, **kwargs)
            new_events = []
            for event in events:
                if event.name in self.mapper:
                    mapped_events = self.mapper[event.name](event)
                    if mapped_events is not None:
                        if isinstance(mapped_events, Event):
                            new_events += [mapped_events]
                        else:
                            new_events += mapped_events
                elif not self.ignore_other:
                    new_events += [event]
            return new_events
        return wrapper
    
    def __or__(self, other : "InstrumentationMapping") -> "InstrumentationMapping":
        return InstrumentationMapping(
            mapper = dict(chain(self.mapper.items(), other.mapper.items())),
            ignore_other = self.ignore_other and other.ignore_other)

class PEP:

    def __init__(
        self, 
        # todo: 1. do mapping from function to action(s) 2. then do instrumentation_mapping with the read action using FUSE
        mapping                 : Dict[Tuple[str, str], Callable[..., list[Event]]] = {},  # map from function to action(s)
        suppression_handlers    : Dict[Union[str, Tuple[str, ...]], Any]            = {}, 
        causation_handlers      : Dict[Union[str, Tuple[str, ...]], Any]            = {},
        instrumentation_mapping : InstrumentationMapping | None                     = None, #eg: Tuple[str, str] = [le user "read", "User.first_name"] =mapsTo> Callable[argument(s) des fonctions] et retourne list[Event] aka les evenements

    ):
        self.mapping : Dict[Tuple[str, str], Any] = {}
        if isinstance(mapping, dict):
            for (key, f) in mapping.items():
                self.populate(key, f)
        self.sup_event_map = suppression_handlers
        self.cau_event_map = causation_handlers
        self.sup_graph     = generate_graph(self.sup_event_map)
        self.cau_graph     = generate_graph(self.cau_event_map)
        self.event_mapper  = instrumentation_mapping if instrumentation_mapping is not None else InstrumentationMapping({})

    def __or__(self, other : "PEP") -> "PEP":
        return PEP(
            mapping       = dict(chain(self.mapping.items(),       other.mapping.items())),
            suppression_handlers = dict(chain(self.sup_event_map.items(), other.sup_event_map.items())),
            causation_handlers = dict(chain(self.cau_event_map.items(), other.cau_event_map.items())),
            instrumentation_mapping  = self.event_mapper | other.event_mapper,
        )
    
    def populate(self, tuple : Tuple[str, str], f : Any) -> None:
        self.mapping[tuple] = f
    
    def __getitem__(self, key : Tuple[str, str]) -> Callable[..., list[Event]]:
        if key not in self.mapping:
            Exception(f'key {key} is not in InstrMapping')
        return self.event_mapper(self.mapping[key])

    def __iter__(self):
        return iter(self.mapping)
    
