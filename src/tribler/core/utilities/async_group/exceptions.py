class DoneException(Exception):
    """A coroutine can not be added to a finished AsyncGroup"""
