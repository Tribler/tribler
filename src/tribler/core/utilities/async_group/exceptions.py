class CancelledException(Exception):
    """A coroutine can not be added to a cancelled AsyncGroup"""
