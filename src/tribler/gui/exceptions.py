class CoreConnectionError(Exception):
    pass


class CoreConnectTimeoutError(Exception):
    pass


class CoreCrashedError(Exception):
    """This error raises in case of tribler core finished with error"""


class TriblerGuiTestException(Exception):
    """Can be intentionally generated in GUI by pressing Ctrl+Alt+Shift+G"""


class UpgradeError(Exception):
    """The error raises by UpgradeManager in GUI process and should stop Tribler"""
