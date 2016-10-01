# Written by Egbert Bouman

"""
The Libtorrent package contains code to manage the torrent library.
"""


def check_handle_and_synchronize(default=None):
    """
    This method can be used as decorator and checks whether the download handler is valid.
    If so, it executes the function. Else, it returns the default value passed.
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


def wait_for_handle_and_synchronize(default=None):
    """
    This method can be used as decorator and waits until the download handler is available.
    """
    def wrap(f):
        def invoke_func(*args, **kwargs):
            download = args[0]
            with download.dllock:
                if download.handle and download.handle.is_valid():
                    return f(*args, **kwargs)
                else:
                    lambda_f = lambda a = args, kwa = kwargs: invoke_func(*a, **kwa)
                    download.session.lm.threadpool.add_task(lambda_f, 1)
                    return default
        return invoke_func
    return wrap
