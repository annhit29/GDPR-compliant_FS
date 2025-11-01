from instrlib.schema import Schema

orm_schema = Schema()
orm_schema.add('create', [str, str, str, str])
orm_schema.add('delete', [str, str, str, str, str])
orm_schema.add('execute', [str, str, str, str, str, str])
orm_schema.add('read', [str, str, str, str, str, str])
orm_schema.add('write', [str, str, str, str, str, str, str])

url_schema = Schema()
url_schema.add('input', [str, str, str, str, str])
url_schema.add('output', [str, str, str, str, str])