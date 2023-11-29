from tribler.core.exceptions import CoreError


class CoreConnectionError(CoreError):
    ...


class CoreConnectTimeoutError(CoreError):
    ...


class CoreCrashedError(CoreError):
    """This error raises in case of tribler core finished with error"""


class TriblerGuiTestException(Exception):
    """Can be intentionally generated in GUI by pressing Ctrl+Alt+Shift+G"""


class UpgradeError(CoreError):
    """The error raises by UpgradeManager in GUI process and should stop Tribler"""
