"""
Core functionality of the Tribler.

Author(s): Arno Bakker
"""
import logging
from threading import RLock

logger = logging.getLogger(__name__)


def warnIfDispersyThread(func):
    """
    We'd rather not be on the Dispersy thread, but if we are lets continue and
    hope for the best. This was introduced after the database thread stuffs
    caused deadlocks. We weren't sure we got all of them, so we implemented
    warnings instead of errors because they probably wouldn't cause a deadlock,
    but if they did we would have the warning somewhere.

    Niels dixit.
    """
    def invoke_func(*args, **kwargs):
        from twisted.python.threadable import isInIOThread
        from traceback import print_stack

        if isInIOThread():
            import inspect
            caller = inspect.stack()[1]
            callerstr = "%s %s:%s" % (caller[3], caller[1], caller[2])

            from time import time
            logger.error("%d CANNOT BE ON DISPERSYTHREAD %s %s:%s called by %s", long(time()),
                        func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)
            print_stack()

        return func(*args, **kwargs)

    invoke_func.__name__ = func.__name__
    return invoke_func


class NoDispersyRLock():

    def __init__(self):
        self.lock = RLock()
        self.__enter__ = self.lock.__enter__
        self.__exit__ = self.lock.__exit__

    @warnIfDispersyThread
    def acquire(self, blocking=1):
        return self.lock.acquire(blocking)

    @warnIfDispersyThread
    def release(self):
        return self.lock.release()
