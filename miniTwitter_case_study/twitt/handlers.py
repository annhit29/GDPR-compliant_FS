def none_handler(orig, event_args, response, *args, **kwargs):
    print(f"None handler -- args: {event_args}, kwargs: {kwargs}")
    return None