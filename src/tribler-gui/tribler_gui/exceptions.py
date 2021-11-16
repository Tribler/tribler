class CoreError(Exception):
    """This is the base class for exceptions that causes GUI shutdown"""


class CoreConnectTimeoutError(CoreError):
    ...


class CoreCrashedError(CoreError):
    """This error raises in case of tribler core finished with error"""
