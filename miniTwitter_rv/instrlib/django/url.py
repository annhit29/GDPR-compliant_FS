from typing import Set, Union
from django.http import HttpRequest
from django.urls import URLPattern, URLResolver
from django.template.response import TemplateResponse
from collections.abc import Iterable
import uuid

from instrlib.django.custom_http import Wrapped_Http_Reponse, Wrapped_Http_Response_Redirect
from instrlib.django.purposes import with_purpose
from instrlib.handler_graph import max_element
from instrlib.pep import PEP
from instrlib.instrument import Instrument
from instrlib.logger import Logger
from instrlib.django.schemas import url_schema
from instrlib.event import Event, Functional, Generic

class InstrumentURL(Instrument):

    def __init__(self, logger : Logger, mapping : Set[str], events : Union[Set[str], None] = None, bypass : Union[Set[str], None] = None):
        super(InstrumentURL, self).__init__(logger)
        self.mapping = mapping
        self.events = events or {'input', 'output'}
        self.bypass = bypass or set()
        self.logger.extend_schema(url_schema)
   
    """
    generate mapping of input and output events for the specified views in mappings/all 
    """
    def generate_url_map(self, urlpatterns, mp, mapping = PEP()):
        for pattern in urlpatterns:
            if isinstance(pattern, URLPattern):
                view = pattern.callback.view_class if hasattr(pattern.callback, 'view_class') else pattern.callback
                qualname = view.__qualname__ if hasattr(view, '__qualname__') else view.__class__.__name__
                if mp is not None and pattern.lookup_str not in mp:
                    continue
                def f(view, request, *args, **kwargs):
                    def unlist(l):
                        if type(l) is list and len(l) == 1:
                            return l[0]
                        else:
                            return l
                    qualname = view.__qualname__ if hasattr(view, '__qualname__') else view.__class__.__name__
                    events = [
                        Generic(
                            'input', 
                            qualname, 
                            key, 
                            unlist(val), 
                            self.get_caller(request),
                            with_purpose = True,
                        ) 
                        for key, val in kwargs.items()
                    ]
                    return events
                if 'input' in self.events:
                    mapping.populate((qualname, 'input'),  Functional('input',  f))
                if 'output' in self.events:
                    mapping.populate((qualname, 'output'), Functional('output', f))
            elif isinstance(pattern, URLResolver):
                self.generate_url_map(pattern.url_patterns, mp, mapping)
        return mapping    
    
    def __call__(self, urlpatterns):
        url_mp = self.generate_url_map(urlpatterns, self.mapping)
        self.logger.extend_mapping(url_mp)
        return self.decorate_all_views(urlpatterns)
    
    """
    return current caller of request
    """
    def get_caller(self, request):
        if request.user.is_authenticated:
            return str(request.user)
        else:
            if not request.session.session_key:
                request.session.create()
            anonymous_id_key = 'anonymous_user_id'
            anonymous_id = request.session.get(anonymous_id_key)
            if not anonymous_id:
                anonymous_id = str(uuid.uuid4())  # Generate a unique identifier
                request.session[anonymous_id_key] = anonymous_id
            return anonymous_id
    
    """
    for all url patterns decorate the view
    """
    def decorate_all_views(self, urlpatterns):
        for pattern in urlpatterns:
            if isinstance(pattern, URLPattern):
                pattern.callback = self.decorate_view(pattern.callback)
            elif isinstance(pattern, URLResolver):
                self.decorate_all_views(pattern.url_patterns)
        return urlpatterns
    
    """
    decorate class based view by overwriting dispatch method 
    """
    def decorate_view_class(self, view):
        def class_decorator(view_dispatch):
            qualname = view.__qualname__ if hasattr(view, '__qualname__') else view.__class__.__name__
            qualname = qualname.replace(".as_view.<locals>.view", "")
            def wrapper(obj, request, *args, **kwargs):
                nonlocal qualname
                if not isinstance(request, HttpRequest):
                    raise Exception("only request objects are allowed")
                # print(f"Class-based view dispatch method called for {self.__class__.__name__}")
                res = self.generate_input(obj.__class__.__name__, 'input', obj, request, **kwargs)
                if qualname in self.bypass:
                    response = with_purpose('bypass')(view_dispatch)(obj, request, *args, **kwargs)
                else:
                    response = view_dispatch(obj, request, *args, **kwargs)
                response = self.generate_output(obj.__class__.__name__, response, request, *args, **kwargs)
                response = response.get_response(request) if isinstance(response, Wrapped_Http_Reponse) else response
                if isinstance(response, TemplateResponse):
                    if qualname in self.bypass:
                        response.render = with_purpose('bypass')(response.render)
                return response
            return wrapper
        return class_decorator
    
    """
    decorate function based view
    """
    def decorate_view_func(self, view):
        qualname = view.__qualname__ if hasattr(view, '__qualname__') else view.__class__.__name__
        def dec_func(request, *args, **kwargs):
            nonlocal qualname
            if not isinstance(request, HttpRequest):
                raise Exception("only request object are allowed")
            res = self.generate_input(qualname, 'input', view, request, **kwargs)
            if qualname in self.bypass:
                response = with_purpose('bypass')(view)(request, *args, **kwargs)
            else:
                response = view(request, *args, **kwargs)
            response = self.generate_output(qualname, response, request, *args, **kwargs)
            response = response.get_response(request) if isinstance(response, Wrapped_Http_Reponse) else response
            if isinstance(response, TemplateResponse):
                if qualname in self.bypass:
                    response.render = with_purpose('bypass')(response.render)
            return response
        ans = dec_func
        return ans
    
    """
    decorate all views
    """
    def decorate_view(self, view):
        if hasattr(view, 'view_class'):
            # print(f"Inside a class based view named {view.view_class.__class__.__name__}")
            view_class = view.view_class
            if not getattr(view_class, '_is_dispatch_decorated', False):
                dispatch_method = getattr(view_class, 'dispatch', None)
                if callable(dispatch_method):
                    setattr(view_class, 'dispatch', self.decorate_view_class(view.view_class)(dispatch_method))
            setattr(view_class, '_is_dispatch_decorated', True)
            return view
        else:      
            return self.decorate_view_func(view)
    
    """
    generate input events and invoke handler for suppression/causation of events
    """
    def generate_input(self, qualname, io, view, request, **kwargs):
        events = []
        if (qualname, 'input') in self.logger.pep and (request.method == "GET" or request.method == "POST"):
            x = self.logger.pep[(qualname, io)]
            updated_kwargs = {**kwargs, **request.GET, **request.POST}
            events = x(view, request, **updated_kwargs)
        cause_flag, supr_flag, self.logger.cau_events, self.logger.sup_events = self.send_events(events, qualname)
        if supr_flag:
            self.invoke_handler(
                self.logger.pep.sup_graph, 
                self.sup_events, 
                self.logger.sup_enc, 
                self.logger.pep.sup_event_map, 
                qualname, **kwargs)
        elif cause_flag:
            self.invoke_handler(
                self.logger.pep.cau_graph, 
                self.cau_events, 
                self.logger.cau_enc, 
                self.logger.pep.cau_event_map, 
                qualname, **kwargs)
            
    def send_events(self, events, qualname):
        cau_flag, sup_flag = False, False
        if events:
            cau_flag, sup_flag, self.logger.cau_events, self.logger.sup_events = super().check_round_trip_time(events, qualname, 1, qualname)
        return cau_flag, sup_flag, self.logger.cau_events, self.logger.sup_events
    
    def generate_output(self, qualname, response, request, *args, **kwargs):
        events = []
        if (qualname, 'output') in self.logger.pep:
            if isinstance(response, Wrapped_Http_Reponse):
                keys = response.additional_info['context_keys']
                name = response.additional_info['template']
                if keys:
                    for key, val in keys.items():
                        events += Event('output', name, key, val, str(self.get_caller(request)), with_purpose = True).copies_with_purposes()
            elif isinstance(response, TemplateResponse):
                context = {}
                if hasattr(response, 'get_context_data'):
                    context = response.get_context_data(**kwargs)
                elif hasattr(response, 'context_data'):
                    context = response.context_data
                template_names = response.template_name if isinstance(response.template_name, Iterable) and not isinstance(response.template_name, str) else [response.template_name]
                for template in template_names:
                    for key, val in context.items():
                        events += Event('output', template, key, val, str(self.get_caller(request)), with_purpose = True).copies_with_purposes()
            elif hasattr(response, 'rendered_content'):
                events = Event('output',  qualname, 'response', response.rendered_content, str(self.get_caller(request)), with_purpose = True).copies_with_purposes()
            elif isinstance(response, Wrapped_Http_Response_Redirect):
                events = []
                if response.additional_info['context_keys']:
                    for key, val in response.additional_info['context_keys']:
                        events += Event('output', f'"{(response.redirect)}"', key, val, str(self.get_caller(request)), with_purpose = True).copies_with_purposes()
                else:
                    events += Event('output', f'"{"redirect"}"', f'"{(response.redirect)}"',  f'"{response.additional_info["func"]}"', str(self.get_caller(request)), with_purpose = True).copies_with_purposes()
            else:
                events = Event('output', qualname, 'response', request.body.decode(), str(self.get_caller(request)), with_purpose = True).copies_with_purposes()
            cau_flag, sup_flag, self.cau_events, self.sup_events = self.send_events(events, qualname)
            if sup_flag:
                response = self.handler_output(self.sup_events, self.logger.pep.sup_event_map, request, response, qualname, *args, **kwargs)
            elif cau_flag:
                response = self.handler_output(self.cau_events, self.logger.pep.cau_event_map, request, response, qualname, *args, **kwargs)
        return response
    
    def handler_output(self, events, mp, request, response, qualname, *args, **kwargs):
        max = max_element(self.logger.pep.sup_graph, events)
        for el in max:
            handler = mp.get(el) 
            response = handler(request, response, self.logger.sup_enc.get(el), *args, **kwargs)
            response = self.generate_output(qualname, response, request, *args, **kwargs)
        return response  
       
