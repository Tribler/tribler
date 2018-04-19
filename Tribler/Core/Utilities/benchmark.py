import functools
import logging
import time
from collections import OrderedDict
from contextlib import contextmanager

benchmarked = OrderedDict()

@contextmanager
def timed_context(name):
    start_time = time.time()
    yield
    end_time = time.time()
    diff_time = (end_time - start_time) * 1000
    benchmarked[name] = (start_time, diff_time)
    logging.info('[%s] finished in %.3f ms', name, diff_time)


def timed(func):
    @functools.wraps(func)
    def newfunc(*args, **kwargs):
        start_time = time.time()
        func(*args, **kwargs)
        end_time = time.time()
        diff_time = (end_time - start_time) * 1000
        benchmarked["<%s>" %func.__name__] = (start_time, diff_time)
        logging.info('function [%s] finished in %.3f ms', func.__name__, diff_time)
    return newfunc
