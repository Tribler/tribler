"""
The Libtorrent package contains code to manage the torrent library.
"""


def checkHandleAndSynchronize(default=None):
    """
    Return the libtorrent handle if it's available, else return the default value
    """
    def wrap(f):
        def invoke_func(*args, **kwargs):
            download = args[0]
            with download.dllock:
                if download.handle and download.handle.is_valid():
                    return f(*args, **kwargs)
            return default
        return invoke_func
    return wrap
