"""
Contains everything related to non-tunnel downloading.
"""


def check_handle_and_synchronize(default=None):
    """
    Return the libtorrent handle if it's available, else return the default value.
    """
    def wrap(f):
        def invoke_func(*args, **kwargs):
            download = args[0]
            with download.lock:
                if download.handle and download.handle.is_valid():
                    return f(*args, **kwargs)
            return default
        return invoke_func
    return wrap
