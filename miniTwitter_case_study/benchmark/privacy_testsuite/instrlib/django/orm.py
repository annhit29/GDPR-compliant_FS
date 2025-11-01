from threading import local
from typing import Set, Union
from instrlib.instrument import Instrument
from instrlib.event import Generic
from instrlib.pep import PEP
from instrlib.logger import Logger

from django.db import models
from django.db.models import Manager
from ambient_toolbox.models import CommonInfo # type: ignore

from instrlib.django.schemas import orm_schema

class InstrumentORM(Instrument):
    
    def __init__(self, logger : Logger, mapping : Set[str], info = None, events : Union[Set[str], None] = None, condition = None):
        self.target = None
        super(InstrumentORM, self).__init__(logger)
        self.mapping = mapping
        self.info = info or (lambda x: "")
        self.events = events or {'read', 'write', 'create', 'delete', 'execute'}
        self.logger.extend_schema(orm_schema)

    def __call__(self, target):
        orm_mp = self.generate_full_map(target, self.mapping)
        self.logger.extend_mapping(orm_mp)
        self.target = target
        self.add_filter_check(self, target)
        self.overwrite_getattribute(self, target)
        return self.instrument_cls(target)

    def __str__(self): 
        def wrapper(*args, **kwargs):
            return self.target.pk.fget(*args, **kwargs)
        return wrapper

    """
    wrapper for function calls, with special handling of the save method to represent writes to the database
    """
    def decorate_function(self, x, f, target, qualname):
        def wrapper(inst, *args, **kwargs):
            if qualname == 'save':
                class_name = inst.__class__.__name__
                setattr(inst, '_read_ok', False)
                field_names = kwargs['update_fields'] if 'update_fields' in kwargs.keys() else inst._meta.fields
                inst_str = str(object.__getattribute__(inst, 'pk'))
                events = []
                for field_name in field_names:
                    field_value = getattr(inst, field_name) if isinstance(field_name, str) else object.__getattribute__(inst, field_name.name)
                    field_name = field_name if isinstance(field_name, str) else field_name.name
                    if (class_name, field_name, 'write') in self.logger.pep:
                        # write(cls: string, field: string, id: string, caller: string, value: string, owner: string, purpose: string)-
                        f = self.logger.pep[(class_name, field_name, 'write')]
                        events += f(class_name, field_name, inst_str, self.info(inst), field_value)
                cau_flag, sup_flag, cau_events, sup_events = self.check_round_trip_time_attr(self, events, 'write', field_name, 1)
                if cau_flag:
                    self.invoke_handler(
                        self.logger.pep.cau_graph, 
                        cau_events, 
                        self.logger.cau_enc, 
                        self.logger.pep.cau_event_map, 
                        x(inst, *args, **kwargs), *args, **kwargs)
                if sup_flag:
                    # Can only have suppressed 'write' events; find out which items need to be removed
                    if 'write' in self.logger.sup_enc: # 'write' not mapped away -- precise suppression
                        bad_fields = {t[1]: t for t in self.logger.sup_enc['write']}
                        for field, sup_event in bad_fields.items():
                            value = self.invoke_handler(
                                self.logger.pep.sup_graph, 
                                [sup_event],
                                self.logger.sup_enc, 
                                self.logger.pep.sup_event_map, 
                                object.__getattribute__(inst, field), *args, **kwargs)
                            object.__setattr__(inst, field, value)
                    else: # 'write' mapped away -- suppress everything
                        for field in inst._meta.fields:
                            value = self.invoke_handler(
                                self.logger.pep.sup_graph,
                                sup_events,
                                self.logger.sup_enc,
                                self.logger.pep.sup_event_map,
                                object.__getattribute__(inst, field), *args, **kwargs)
                            object.__setattr__(inst, field, value)
                return x(inst, *args, **kwargs)
            else:
                events = f(target, qualname, str(inst))
                cau_flag, sup_flag, cau_events, sup_events = self.check_round_trip_time( events, qualname, 1, target.__qualname__, False, *args, **kwargs)
                if cau_flag:
                    self.invoke_handler(
                        self.logger.pep.cau_graph, 
                        cau_events, 
                        self.logger.cau_enc, 
                        self.logger.pep.cau_event_map, 
                        x(inst, *args, **kwargs), *args, **kwargs)
                if sup_flag:
                    return self.invoke_handler(
                        self.logger.pep.sup_graph, 
                        sup_events, 
                        self.logger.sup_enc, 
                        self.logger.pep.sup_event_map, 
                        x(inst, *args, **kwargs), *args, **kwargs)
                return x(inst, *args, **kwargs)
        return wrapper
    
    """
    adds filter_check primitive
    """
    def add_filter_check(self, instr : "InstrumentORM", cls):
        qualname = cls.__qualname__
        names_to_check = [t[1] for t in instr.logger.pep if len(t) == 3 and t[0] == qualname and t[2] == 'read']
        @classmethod
        def filter_check(cls, queryset):
            objects = list(queryset)
            for obj in objects:
                setattr(obj, '_read_ok', True)
            events = []
            for name in names_to_check:
                f = instr.logger.pep[(qualname, name, 'read')]
                for obj in objects:
                    obj_str = str(object.__getattribute__(obj, 'pk'))
                    events += f(qualname, name, obj_str, instr.info(obj))
            cau_flag, sup_flag, cau_events, sup_events = instr.check_round_trip_time_attr(instr, events, qualname, name, 1)
            if cau_flag:
                instr.invoke_handler(
                    instr.logger.pep.cau_graph, 
                    cau_events, 
                    instr.logger.cau_enc, 
                    instr.logger.pep.cau_event_map, 
                    object.__getattribute__(self, 'filter_check'))
            if sup_flag:
                # Can only have suppressed 'read' events; find out which items need to be removed
                if 'read' in instr.logger.sup_enc: # 'read' not mapped away -- precise suppression
                    assert('read' in instr.logger.sup_enc)
                    bad_pks = {int(t[2]) for t in instr.logger.sup_enc['read']}
                    return [obj for obj in objects if obj.pk not in bad_pks]
                else:
                    return [] # 'read' mapped away -- suppress everything
            else:
                return objects
        @classmethod
        def object_check(cls, obj):
            setattr(obj, '_read_ok', True)
            events = []
            for name in names_to_check:
                f = instr.logger.pep[(qualname, name, 'read')]
                obj_str = str(object.__getattribute__(obj, 'pk'))
                events += f(qualname, name, obj_str, instr.info(obj))
            cau_flag, sup_flag, cau_events, sup_events = instr.check_round_trip_time_attr(instr, events, qualname, name, 1)
            if cau_flag:
                instr.invoke_handler(
                    instr.logger.pep.cau_graph, 
                    cau_events, 
                    instr.logger.cau_enc, 
                    instr.logger.pep.cau_event_map, 
                    object.__getattribute__(self, 'object_check'))
            if sup_flag:
                # Can only have suppressed 'read' events
                return None
            else:
                return obj
        cls.filter_check = filter_check
        cls.object_check = object_check
    
    """
    overwrites __getattribute__ method
    """
    def overwrite_getattribute(self, instr, cls):
        def custom_getattribute(self, name):
            if name.startswith('_'):
                return object.__getattribute__(self, name)
            if hasattr(cls, name) and not isinstance(getattr(cls, name), property) and not callable(getattr(cls, name)) and not hasattr(self, '_read_ok'):
                qualname = cls.__qualname__
                if (qualname, name, 'read') in instr.logger.pep:
                    f = instr.logger.pep[(qualname, name, 'read')]
                    self_str = str(object.__getattribute__(self, 'pk'))
                    events = f(qualname, name, self_str, instr.info(self))
                    if self_str is not None:
                        cau_flag, sup_flag, cau_events, sup_events = instr.check_round_trip_time_attr(instr, events, qualname, name, 1)
                        if cau_flag:
                            instr.invoke_handler(
                                instr.logger.pep.cau_graph, 
                                cau_events, 
                                instr.logger.cau_enc, 
                                instr.logger.pep.cau_event_map, 
                                object.__getattribute__(self, name))
                        if sup_flag:
                            return instr.invoke_handler(
                                instr.logger.pep.sup_graph, 
                                sup_events, 
                                instr.logger.sup_enc, 
                                instr.logger.pep.sup_event_map, 
                                object.__getattribute__(self, name))
            return object.__getattribute__(self, name)
        cls.__getattribute__ = custom_getattribute


    """
    generates fToEvent
    """    
    def generate_full_map(self, cls, set=None):
        mapping = PEP()
        if not (issubclass(cls, models.Model)):
            raise Exception("This instrumentation should only be used for ORM models")
        if not hasattr(cls, "_instrumented"):
            print(f"Instrumenting class {cls.__qualname__}" )
            for expr in (dir(cls)):
                key = (cls.__qualname__, expr)
                x = getattr(cls, expr)
                if expr == '__init__':
                    if set is not None and cls.__qualname__ not in set:
                        continue
                    if 'create' in self.events:
                        mapping.populate(
                            key, 
                            Generic(
                                'create', 
                                lambda *l, **kw : str(l[0]),
                                lambda *l, **kw: CommonInfo.get_current_user(),
                                lambda *l, **kw: self.info(l[0]),
                                with_purpose = True,
                            )
                        )
                elif expr == 'save':
                    if 'write' in self.events:
                        mapping.populate(key, None)
                else:
                    if expr.startswith("__"):
                        continue
                    if set is not None and cls.__qualname__ + '.' + expr not in set:
                        continue
                    elif callable(x): #function call
                        if 'execute' in self.events:
                            mapping.populate(
                                key, 
                                Generic(
                                    'execute', 
                                    lambda *l, **kw: l[0].__qualname__, 
                                    lambda *l, **kw: str(l[1]),
                                    lambda *l, **kw: str(l[0].pk), 
                                    lambda *l, **kw: str(CommonInfo.get_current_user()),
                                    lambda *l, **kw: self.info(l[0]),
                                    with_purpose = True,
                                )
                            )
                    else: #attribute
                        key_r = (cls.__qualname__, expr, 'read')
                        key_w = (cls.__qualname__, expr, 'write')
                        if 'read' in self.events:
                            # l = (qualname, name, self_str, instr.info(self))
                            # read(cls: string, field: string, id: string, caller: string, owner: string, purpose: string)-
                            mapping.populate(
                                key_r, 
                                Generic(
                                    'read', 
                                    lambda *l, **kw: l[0], 
                                    lambda *l, **kw: l[1], 
                                    lambda *l, **kw: str(l[2]),
                                    lambda *l, **kw: str(CommonInfo.get_current_user()),
                                    lambda *l, **kw: str(l[3]),
                                    with_purpose = True,
                                )
                            )
                        if 'write' in self.events:
                            # l = (qualname, name, self_str, instr.info(self), value)
                            # write(cls: string, field: string, id: string, caller: string, value: string, owner: string, purpose: string)-
                            mapping.populate(
                                key_w, 
                                Generic(
                                    'write', 
                                    lambda *l, **kw: l[0], 
                                    lambda *l, **kw: l[1], 
                                    lambda *l, **kw: str(l[2]), 
                                    lambda *l, **kw: str(CommonInfo.get_current_user()),  
                                    lambda *l, **kw: str(l[4]),
                                    lambda *l, **kw: str(l[3]),
                                    with_purpose = True,
                                )
                            )
            cls._instrumented = True
        return mapping
