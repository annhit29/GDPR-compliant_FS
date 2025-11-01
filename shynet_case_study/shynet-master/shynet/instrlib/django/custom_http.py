from django.http import HttpResponseRedirect
from django.shortcuts import render as django_render
from django.shortcuts import redirect as django_redirect
import inspect

class Wrapped_Http_Response_Redirect(HttpResponseRedirect):
    def __init__(self, redirect_to, additional_info):
        self.redirect = redirect_to
        self.additional_info = additional_info or {}
        super().__init__(redirect_to)
        
    def get_response(self):
        return self.http_response
        
class Wrapped_Http_Reponse():
    def __init__(self, http_response, additional_info, request, template_name, context, content_type, status, using):
        self.http_response = http_response
        self.additional_info = additional_info or {}
    
    def get_response(self, request):
        return self.http_response
    
"""
 return a wrapped version of the render function containing additional information
"""       
def render(request, template_name, context=None, content_type=None, status=None, using=None):
    response = django_render(request, template_name, context, content_type, status, using)
    caller_frame = inspect.currentframe().f_back
    caller_info = inspect.getframeinfo(caller_frame)
    additional_info = {
        'type': 'render',
        'template': template_name,
        'context_keys': context if context else None,
        'context': str(context),
        'func': caller_info.function
    }
    return Wrapped_Http_Reponse(response, additional_info, request, template_name, context, content_type, status, using)

"""
return a wrapped redirect containing additional information
"""
def redirect(to, *args, **kwargs):
    response = django_redirect(to, *args, **kwargs) 
    if isinstance(response, HttpResponseRedirect):
        caller_frame = inspect.currentframe().f_back
        caller_info = inspect.getframeinfo(caller_frame)
        additional_info = {
            'type': 'redirect',
            'template': to,
            'context_keys': kwargs,
            'func': caller_info.function
        }
        # print(f"additional info {additional_info}")
        return Wrapped_Http_Response_Redirect(response.url, additional_info)
    return response 

