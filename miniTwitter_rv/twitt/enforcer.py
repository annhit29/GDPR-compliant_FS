from typing import Any

from instrlib.event import Event
from instrlib.pdp import EnfGuard
from instrlib.logger import Logger
from instrlib.pep import InstrumentationMapping, PEP
from instrlib.schema import Schema

from Twitter.settings import INSTRLIB_EXE, INSTRLIB_FORMULA, INSTRLIB_LOG, INSTRLIB_SIG

# Handlers

def none_handler(event_name, event_args, response, *args, **kwargs):
    return None

def delete_handler(events):
    from twitt.models import User

    for event in events:

        user_name = event['args'][0]
        try:
            user = User.objects.get(username=user_name)
        except User.DoesNotExist:
            return
        
        user.delete_data()

# Schema

schema = Schema()
schema.add('Use', [str, str])
schema.add('Consent', [str, str])
schema.add('Request', [str])
schema.add('Delete', [str])
schema.add('Revoke', [str, str])

# PDP

pdp = EnfGuard(INSTRLIB_EXE, INSTRLIB_SIG, INSTRLIB_FORMULA, log_file = INSTRLIB_LOG)

# PEP

suppression_handlers : dict[str | tuple[str, ...], Any] = {    
    ('Use')    : none_handler,
}
causation_handlers : dict[str | tuple[str, ...], Any] = {
    ('Delete') : delete_handler,
}

def read_mapping(action):
    return Event('Use', action.args[4], action.args[5])

def write_mapping(action):
    return Event('Use', action.args[5], action.args[6])

def input_mapping(action):
    if action.args[:3] == ('SetCookieConsentView', 'accept', 'true'):
        return Event('Consent', action.args[3], 'marketing')
    elif action.args[:3] == ('SetCookieConsentView', 'decline', 'true'):
        return Event('Revoke', action.args[3], 'marketing')
    elif action.args[:3] == ('DeleteAllView', 'delete', 'true'):
        return Event('Request', action.args[3])
    else:
        return None
    
def execute_mapping(action):
    if action.args[:2] == ('User', 'delete_data'):
        return Event('Delete', action.args[3])
    else:
        return None

instrumentation_mapping = InstrumentationMapping({
    'read':    read_mapping,
    'write':   write_mapping,
    'input':   input_mapping,
    'execute': execute_mapping,
})

pep = PEP(
    suppression_handlers    = suppression_handlers, 
    causation_handlers      = causation_handlers, 
    instrumentation_mapping = instrumentation_mapping
)

# Logger

logger = Logger(pep, schema, pdp)