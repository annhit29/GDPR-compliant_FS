from queue import Queue
from random import random
import threading
from time import time
from typing import Tuple, List, Set, Union, Dict

from instrlib.pdp import PDP
from instrlib.event import *
from instrlib.pep import PEP
from instrlib.schema import Schema

class Logger:

    def __init__(self, pep : PEP, schema : Schema, pdp : PDP, cache_timeout : int = 10):
        self.pep                                           = pep 
        self.schema     : Schema                           = schema
        self.pdp                                           = pdp
        self.pdp.pep                                       = pep
        for _, event in self.pep.mapping.items():            
            if event.name not in schema.mapping:
                Exception(f"Event {event} is not defined in the schema.") 
        self.sup_events : Set[str]                         = set() #used to store suppressed event names 
        self.cau_events : Set[str]                         = set() #used to store caused event names
        self.sup_enc    : Dict[str, List[Tuple[Any, ...]]] = {}    #used to store suppression cmds returned by the enforcer
        self.cau_enc    : Dict[str, List[Tuple[Any, ...]]] = {}    #used to store causation cmds returned by the enforcer
        self.proc                                          = self.pdp.ocaml_proc
        self.write_prio                                    = self.pdp.write_prio #priority queue
        self.timer                                         = self.pdp.timer
        self.cache_timeout : int                           = cache_timeout # timout seconds for the cache used in log()
        self.cache : Dict[Tuple[Event, ...], Tuple[float, Tuple[bool, bool, Set[str], Set[str]]]]
        self.cache = {}


    def _reset(self):
        self.sup_events = set()
        self.cau_events = set()
        self.sup_enc    = {}
        self.cau_enc    = {}

    def extend_mapping(self, pep : PEP) -> None:
        self.pep     = self.pep | pep
        self.pdp.pep = self.pep | pep

    def extend_schema(self, schema : Schema) -> None:
        self.schema = self.schema | schema

    def make_cache_key(self, events: List[Event]) -> Tuple[Event, ...]:
        return tuple(events)

    def cache_update(self, events: List[Event], ts: float, result: Tuple[bool, bool, Set[str], Set[str]]) -> None:
        """
        update the cache with the given events, timestamp and result
        """
        events_key: Tuple[Event, ...] = self.make_cache_key(events)
        self.cache[events_key] = (ts, result)

    def cache_get(self, events: List[Event], curr_ts: float=time()) -> Union[None, Tuple[bool, bool, Set[str], Set[str]]]:
        """
        get the cached result for the given events
        """
        events_key: Tuple[Event, ...] = self.make_cache_key(events)
        if events_key in self.cache:
            ts, result = self.cache[events_key]
            if ts + self.cache_timeout > curr_ts:
                return result
            else:
                return None
        else:
            return None

    def clean_cache(self) -> None:
        """
        clean outdated cache entries from the logger cache
        """
        for k, (ts, _) in list(self.cache.items()):
            if ts + self.cache_timeout < time():
                del self.cache[k]

                
    """
    generate events to be sent to the priority queue and returns result of their processing: 
    cau_flag, sup_flag : if causation or suppression was triggered 
    cau_events, sup_events: the event names of the triggered events (args stored in self.sup_enc/self.cau_enc)
    """
    def log(self, events : List[Event], event : threading.Event, flag_q : bool) -> Union[None, Tuple[bool, bool, Set[str], Set[str]]]:
        ts = time()
        events = list(set(events))
        if random() < 0.01: 
            self.clean_cache()
        cached = self.cache_get(events, ts)
        if cached is not None:
            event.set()
            return cached
        events = list(set(events))
        self.check_type(events)
        all_events = ' '.join(map(str, events))        
        cau_flag = False
        sup_flag = False
        singleQueue : Queue = Queue()
        with self.timer.current_time_lock:
            stm = self.pdp.ts_bytes((all_events), self.timer.current_time, flag_q)
            tsp = self.timer.current_time
            event_flag = threading.Event()
            item = TimedTuple(tsp + 0.1, (event_flag, singleQueue, stm))
            self.write_prio.put(item)
        event_flag.wait()
        cau_flag, sup_flag = self.get_command(cau_flag, sup_flag, singleQueue)    
        event.set()
        result = (cau_flag, sup_flag, self.cau_events, self.sup_events)
        self.cache_update(events, ts, result) # cache the result
        return result
    
    def get_command(self, cau_flag : bool, sup_flag : bool, singleQueue : Queue) -> Tuple[bool, bool]:
        self._reset()
        while not singleQueue.empty():
            stms = singleQueue.get()
            while not stms.empty():
                msg = stms.get()
                for cau_event in msg.get("cause", {}):
                    name = cau_event["name"]
                    args = cau_event["args"]
                    cau_flag = True
                    self.parse_event(name, args, 'Cause')
                for sup_event in msg.get("suppress", {}):
                    name = sup_event["name"]
                    args = sup_event["args"]
                    sup_flag = True
                    self.parse_event(name, args, 'Suppress')
        return cau_flag, sup_flag

    def parse_args(self, name : str, args : Tuple[str, ...]) -> Tuple[Any, ...]:
        if name not in self.schema: 
            raise Exception(f'the event {name} is not defined in the schema')
        schema_types = self.schema.get_types(name)
        new_args : List[Any] = []
        for arg_idx, (arg, arg_type) in enumerate(zip(args, schema_types)):
            if arg_type is str:
                new_args.append(arg)
            elif arg_type is float and arg.isnumeric():
                new_args.append(float(arg))
            elif arg_type is int and arg.isnumeric():
                new_args.append(int(arg))
            else:
                raise Exception(f'Type mismatch for event {name}. Expected {arg_type} for arg {arg_idx}, got {type(arg)}.')
        return tuple(new_args)

    def parse_event(self, name : str, args : Tuple[str, ...], cmd : str) -> None:
        args_tuple = self.parse_args(name, args)
        if cmd == 'Suppress':
            if name in self.pep.sup_event_map:
                if name not in self.sup_enc:
                    self.sup_enc[name] = [args_tuple]
                else:
                    self.sup_enc[name].append(args_tuple)
                self.sup_events.add(name)
            else:
                raise Exception(f'No suppression handler defined for suppressed event {name}')
        if cmd == 'Cause':
            if name in self.pep.cau_event_map: 
                if name not in self.cau_enc:
                    self.cau_enc[name] = [args_tuple]
                else:
                    self.cau_enc[name].append(args_tuple)
                self.cau_events.add(name)
            else:
                raise Exception(f'No causation handler defined for caused event {name}')

    """
    check for each event that the event is defined through the schema and 
    has the same type as defined in the schema 
    """
    def check_type(self, events : List[Event]):
         for idx, event in enumerate(events):
            # print('current event', event)
            if event.name not in self.schema: 
                raise Exception(f'The event {event.name} is not defined in the schema')
            num_actual_args = event.get_num_args()
            schema_types = self.schema.get_types(event.name)
            num_expected_args = len(schema_types)
            if num_expected_args != num_actual_args:
                raise Exception(f'The event {event.name} has a different number of args than specified in the schema')
            mapped_event = list(event.args)
            new_args = []
            for arg_idx, (arg, arg_type) in enumerate(zip(mapped_event, schema_types)):
                if type(arg) is not arg_type and arg_type is not str:
                    raise Exception(f'Type mismatch for event {event.name}. Expected {arg_type} for arg {arg_idx}, got {type(arg)}.')
                elif arg_type is str:
                    new_args.append(str(arg))
                else:
                    new_args.append(arg)
            events[idx].args = tuple(new_args)