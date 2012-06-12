# Written by Arno Bakker
# see LICENSE.txt for license information
from threading import RLock


def warnDisperyThread(func):
    def invoke_func(*args,**kwargs):
        from threading import currentThread
        from traceback import print_stack
        
        if currentThread().getName()== 'Dispersy':
            import inspect
            caller = inspect.stack()[1]
            callerstr = "%s %s:%s"%(caller[3],caller[1],caller[2])
            
            from time import time
            import sys
            print >> sys.stderr, long(time()), "CANNOT BE ON DISPERSYTHREAD %s %s:%s called by %s"%(func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)
            print_stack()
        
        return func(*args, **kwargs)
    
    invoke_func.__name__ = func.__name__
    return invoke_func

class NoDispersyRLock():
    
    def __init__(self):
        self.lock = RLock()
    
    @warnDisperyThread
    def acquire(self, blocking=1):
        return self.lock.acquire(blocking)
    
    @warnDisperyThread    
    def release(self):
        return self.lock.release()