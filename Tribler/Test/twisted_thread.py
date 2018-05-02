"""
Helpers to run the reactor in a separate thread, adapted from Nose's twistedtools.py
"""
from Tribler.pyipv8.ipv8.test.util import deferred, threaded_reactor


# Export global reactor variable, as Twisted does
reactor, reactor_thread = threaded_reactor()
deferred = deferred


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
