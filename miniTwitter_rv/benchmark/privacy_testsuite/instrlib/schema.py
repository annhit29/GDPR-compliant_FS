"""
schema maps events to list of types
optional: additional arg intended for adding cau/sup type 
"""
from itertools import chain
from typing import Any, List

class Schema: 
    
    def __init__(self):
        self.mapping = {}
        self.optional_mapping = {}

    def __or__(self, other : "Schema"):
        schema = Schema()
        schema.mapping = dict(chain(self.mapping.items(), other.mapping.items()))
        schema.optional_mapping = dict(self.optional_mapping, **other.optional_mapping)
        return schema
    
    def add(self, name : str, types_list : List[type], opt_args : Any = None):
        if name in self.mapping:
            Exception(f'there already is a event with the name {name} in the schema')
        self.mapping[name] = types_list
        if opt_args:
            self.optional_mapping[name] = opt_args
    
    def remove(self, name : str):
        if name in self.mapping:
            del self.mapping[name]
            if name in self.optional_mapping:
                del self.optional_mapping[name]
    
    def get_types(self, name : str) -> List[type]:
        if name in self.mapping:
            return self.mapping[name]
        else :
            raise Exception(f'event name {name} is not in schema')  
    
    def get_opt_args(self, name : str) -> Any:
        if name in self.optional_mapping:
            return self.optional_mapping[name]
        else:
            raise Exception(f'event name {name} is not in optional mapping')
            
    def __iter__(self):
        return iter(self.mapping)
