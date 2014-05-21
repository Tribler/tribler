"""
Helpers to run the reactor in a separate thread, adapted from Nose's twistedtools.py
"""
from twisted.internet import reactor
from twisted.python import log

_twisted_thread = None

def threaded_reactor():
    """
    Start the Twisted reactor in a separate thread, if not already done.
    Returns the reactor.
    """
    global _twisted_thread
    if not _twisted_thread:
        from twisted.python import threadable
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

    def stop_reactor():
        """"Helper for calling stop from withing the thread."""
        reactor.stop()

    reactor.callFromThread(stop_reactor)
    reactor_thread.join()
    for p in reactor.getDelayedCalls():
        if p.active():
            p.cancel()
    _twisted_thread = None
