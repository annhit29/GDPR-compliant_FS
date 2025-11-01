#!/usr/bin/env python
import os
import sys

def set_custom_env_vars():
    for arg in sys.argv[:]:
        if arg.startswith('--INSTRLIB_EXE='):
            os.environ['INSTRLIB_EXE'] = arg.split('=', 1)[1]
            sys.argv.remove(arg)
        elif arg.startswith('--INSTRLIB_FORMULA='):
            os.environ['INSTRLIB_FORMULA'] = arg.split('=', 1)[1]
            sys.argv.remove(arg)
        elif arg.startswith('--INSTRLIB_SIG='):
            os.environ['INSTRLIB_SIG'] = arg.split('=', 1)[1]
            sys.argv.remove(arg)
        elif arg.startswith('--INSTRLIB_LOG='):
            os.environ['INSTRLIB_LOG'] = arg.split('=', 1)[1]
            sys.argv.remove(arg)

if __name__ == "__main__":
    set_custom_env_vars()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Twitter.settings")

    if "runserver" in sys.argv:
        from twitt.enforcer import pdp
        pdp.start_threads()

    from django.core.management import execute_from_command_line # type: ignore
    execute_from_command_line(sys.argv)
