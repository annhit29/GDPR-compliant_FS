import sys
import os

from tester import Tester
from reporter import Reporter

if __name__ == '__main__':

    assert(len(sys.argv) > 3)
    
    baseline = __import__(f'drivers.{sys.argv[1]}', globals(), locals(), [sys.argv[1]])

    will_test = True
    will_generate = True
    folder = None
    bs = None
    policy = None
    sig = None
    exe = None

    for i in range(2, len(sys.argv), 2):
        if sys.argv[i] == '-o':
            if sys.argv[i+1] == 'test':
                will_generate = False
            elif sys.argv[i+1] == 'generate':
                will_test = False
        if sys.argv[i] == '-f':
            folder = sys.argv[i+1]
        if sys.argv[i] == '-b':
            bs = sys.argv[i+1]
        if sys.argv[i] == '-p':
            policy = sys.argv[i+1]
        if sys.argv[i] == '-bs':
            bs = sys.argv[i+1]
        if sys.argv[i] == '-e':
            exe = sys.argv[i+1]
            
            
    t = Tester(sys.argv[1], baseline.Application, Reporter, folder, policy, exe)

    if will_test:
        t.test(folder=folder)

    if will_generate:
         if t.reporter is None:
             t.load()
         t.generate(baseline=bs)
