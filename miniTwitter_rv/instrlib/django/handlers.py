from .views import error_page_view

def default_handler(request, *args, **kwargs):
    return error_page_view(request, *args, **kwargs)
