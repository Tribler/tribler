# Written by Egbert Bouman

'''
The Libtorrent package contains code to manage the torrent library.
'''
import random
from twisted.internet import reactor


def checkHandleAndSynchronize(default=None):
    def wrap(f):
        def invoke_func(*args, **kwargs):
            download = args[0]
            with download.dllock:
                if download.handle and download.handle.is_valid():
                    return f(*args, **kwargs)
            return default
        return invoke_func
    return wrap


def waitForHandleAndSynchronize(default=None):
    def wrap(f):
        def invoke_func(*args, **kwargs):
            download = args[0]
            with download.dllock:
                if download.handle and download.handle.is_valid():
                    return f(*args, **kwargs)
                elif not download.session.lm.shutdownstarttime:
                    lambda_f = lambda a = args, kwa = kwargs: invoke_func(*a, **kwa)
                    random_id = ''.join(random.choice('0123456789abcdef') for _ in xrange(30))
                    reactor.callFromThread(
                        lambda: download.register_task("check_handle_%s" % random_id, reactor.callLater(1, lambda_f)))
                return default
        return invoke_func

    return wrap
