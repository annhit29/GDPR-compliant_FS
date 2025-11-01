from typing import Any

from instrlib.enforcer import EnfGuard
from instrlib.logger import Logger
from instrlib.mapping import PEP
from instrlib.django.handlers import default_handler
from instrlib.schema import Schema

from twitt.handlers import none_handler

from Twitter.settings import INSTRLIB_EXE, INSTRLIB_FORMULA, INSTRLIB_LOG, INSTRLIB_SIG

# Enforcer

enfpal = EnfGuard(INSTRLIB_EXE, INSTRLIB_SIG, INSTRLIB_FORMULA, log_file = INSTRLIB_LOG)

# Mapping

sup_event_map : dict[str | tuple[str, ...], Any] = {    
    ('read')                       : none_handler,
    ('write')                      : none_handler,
    ('input')                      : default_handler,
}
cau_event_map : dict[str | tuple[str, ...], Any] = {}

mp = PEP(suppression_handlers = sup_event_map, causation_handlers = cau_event_map)

# Logger

logger = Logger(mp, Schema(), enfpal)