from typing import Any

from instrlib.enforcer import EnfGuard
from instrlib.logger import Logger
from instrlib.mapping import PEP
from instrlib.schema import Schema

from analytics.handlers import none_handler

from shynet.settings import INSTRLIB_EXE, INSTRLIB_FORMULA, INSTRLIB_LOG, INSTRLIB_SIG

# Enforcer

enfpal = EnfGuard(INSTRLIB_EXE, INSTRLIB_SIG, INSTRLIB_FORMULA, log_file = INSTRLIB_LOG)

# Mapping

sup_event_map = {    
    ('read')  : none_handler,
    ('write') : none_handler,
}
cau_event_map = {}

mp = PEP(suppression_handlers = sup_event_map, causation_handlers = cau_event_map)

# Logger

logger = Logger(mp, Schema(), enfpal)