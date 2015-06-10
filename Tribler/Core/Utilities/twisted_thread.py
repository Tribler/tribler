"""
Helpers to run the reactor in a separate thread, adapted from Nose's twistedtools.py
"""
import sys
from Queue import Empty, Queue
from threading import current_thread

from twisted.internet import reactor
from twisted.python import log


_twisted_thread = None


class TimeExpired(AssertionError):
    pass


def make_decorator(func):
    """
    Wraps a test decorator so as to properly replicate metadata
    of the decorated function, including nose's additional stuff
    (namely, setup and teardown).
    """
    def decorate(newfunc):
        if hasattr(func, 'compat_func_name'):
            name = func.compat_func_name
        else:
            name = func.__name__
        newfunc.__dict__ = func.__dict__
        newfunc.__doc__ = func.__doc__
        newfunc.__module__ = func.__module__
        if not hasattr(newfunc, 'compat_co_firstlineno'):
            newfunc.compat_co_firstlineno = func.func_code.co_firstlineno
        try:
            newfunc.__name__ = name
        except TypeError:
            # can't set func name in 2.3
            newfunc.compat_func_name = name
        return newfunc
    return decorate


def threaded_reactor():
    """
    Start the Twisted reactor in a separate thread, if not already done.
    Returns the reactor.
    """
    global _twisted_thread
    if not _twisted_thread:
        from threading import Thread

        def _reactor_runner():
            reactor.suggestThreadPoolSize(1)
            reactor.run(installSignalHandlers=False)

        _twisted_thread = Thread(target=_reactor_runner, name="Twisted")
        _twisted_thread.setDaemon(True)
        _twisted_thread.start()

        def hook_observer():
            observer = log.PythonLoggingObserver()
            observer.start()
            import logging
            log.msg("PythonLoggingObserver hooked up", logLevel=logging.DEBUG)
        reactor.callFromThread(hook_observer)

    return reactor, _twisted_thread

# Export global reactor variable, as Twisted does
reactor, reactor_thread = threaded_reactor()


def stop_reactor():
    """
    Stop the reactor and join the reactor thread until it stops.
    """
    global _twisted_thread

    def _stop_reactor():
        """"Helper for calling stop from withing the thread."""
        reactor.stop()

    reactor.callFromThread(_stop_reactor)
    reactor_thread.join()
    for p in reactor.getDelayedCalls():
        if p.active():
            p.cancel()
    _twisted_thread = None


def deferred(timeout=None):
    """
    By wrapping a test function with this decorator, you can return a
    twisted Deferred and the test will wait for the deferred to be triggered.
    The whole test function will run inside the Twisted event loop.

    The optional timeout parameter specifies the maximum duration of the test.
    The difference with timed() is that timed() will still wait for the test
    to end, while deferred() will stop the test when its timeout has expired.
    The latter is more desireable when dealing with network tests, because
    the result may actually never arrive.

    If the callback is triggered, the test has passed.
    If the errback is triggered or the timeout expires, the test has failed.

    Example::

        @deferred(timeout=5.0)
        def test_resolve():
            return reactor.resolve("www.python.org")

    Attention! If you combine this decorator with other decorators (like
    "raises"), deferred() must be called *first*!

    In other words, this is good::

        @raises(DNSLookupError)
        @deferred()
        def test_error():
            return reactor.resolve("xxxjhjhj.biz")

    and this is bad::

        @deferred()
        @raises(DNSLookupError)
        def test_error():
            return reactor.resolve("xxxjhjhj.biz")
    """
    reactor, reactor_thread = threaded_reactor()
    if reactor is None:
        raise ImportError("twisted is not available or could not be imported")
    # Check for common syntax mistake
    # (otherwise, tests can be silently ignored
    # if one writes "@deferred" instead of "@deferred()")
    try:
        timeout is None or timeout + 0
    except TypeError:
        raise TypeError("'timeout' argument must be a number or None")

    def decorate(func):
        def wrapper(*args, **kargs):
            q = Queue()

            def callback(value):
                q.put(None)

            def errback(failure):
                # Retrieve and save full exception info
                try:
                    failure.raiseException()
                except:
                    q.put(sys.exc_info())

            def g():
                try:
                    d = func(*args, **kargs)
                    try:
                        d.addCallbacks(callback, errback)
                    # Check for a common mistake and display a nice error
                    # message
                    except AttributeError:
                        raise TypeError("you must return a twisted Deferred "
                                        "from your test case!")
                # Catch exceptions raised in the test body (from the
                # Twisted thread)
                except:
                    q.put(sys.exc_info())
            reactor.callFromThread(g)
            try:
                error = q.get(timeout=timeout)
            except Empty:
                raise TimeExpired("timeout expired before end of test (%f s.)"
                                  % timeout)
            # Re-raise all exceptions
            if error is not None:
                exc_type, exc_value, tb = error
                raise exc_type, exc_value, tb
        wrapper = make_decorator(func)(wrapper)
        return wrapper
    return decorate


def callInThreadPool(fun, *args, **kwargs):
    """
    Calls fun(*args, **kwargs) in the reactor's thread pool.
    """
    reactor.callFromThread(reactor.callInThread, fun,  *args, **kwargs)


def isInThreadPool():
    """
    Check if we are currently on one of twisted threadpool threads.
    """

    return current_thread() in reactor.threadpool.threads
