import sys

def parse_cmd():
    i = 0
    formula  = ""
    sig      = ""
    exe      = ""
    log      = ""
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg.startswith('-exe='):
            exe = arg.split('=')[1]
            sys.argv.pop(i)
            continue
        elif arg.startswith('-formula='):
            formula = arg.split('=')[1]
            sys.argv.pop(i) 
            continue 
        elif arg.startswith('-sig='):
            sig = arg.split('=')[1]
            sys.argv.pop(i)  
            continue
        elif arg.startswith('-log='):
            log = arg.split('=')[1]
            sys.argv.pop(i)  
            continue
        i += 1
    return exe, sig, formula, log
