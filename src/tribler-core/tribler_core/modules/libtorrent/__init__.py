"""
The Libtorrent package contains code to manage the torrent library.

Author(s): Egbert Bouman
"""
from asyncio import CancelledError, Future
from contextlib import suppress


def check_handle(default=None):
    """
    Return the libtorrent handle if it's available, else return the default value.
    """
    def wrap(f):
        def invoke_func(*args, **kwargs):
            download = args[0]
            if download.handle and download.handle.is_valid():
                return f(*args, **kwargs)
            return default
        return invoke_func
    return wrap


def require_handle(func):
    """
    Invoke the function once the handle is available. Returns a future that will fire once the function has completed.
    """
    def invoke_func(*args, **kwargs):
        result_future = Future()

        def done_cb(fut):
            with suppress(CancelledError):
                handle = fut.result()
            if not fut.cancelled() and not result_future.done() and handle == download.handle and handle.is_valid():
                result_future.set_result(func(*args, **kwargs))
        download = args[0]
        handle_future = download.get_handle()
        handle_future.add_done_callback(done_cb)
        return result_future
    return invoke_func


def check_vod(default=None):
    """
    Check if torrent is vod mode, else return default
    """
    def wrap(f):
        def invoke_func(self, *args, **kwargs):
            if self.enabled:
                return f(self, *args, **kwargs)
            return default
        return invoke_func
    return wrap
