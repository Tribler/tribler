from twisted.internet.defer import inlineCallbacks

from Tribler.Test.twisted_thread import deferred


def twisted_wrapper(arg):
    """
    Wrap a twisted test. Optionally supply a test timeout.
    Note that arg might either be a func or the timeout.
    """
    if isinstance(arg, (int, long)):
        return lambda x: deferred(arg)(inlineCallbacks(x))
    return deferred(timeout=10000)(inlineCallbacks(arg))
