"""
The Tribler-specifc Exceptions the Core may throw.

Author(s): Arno Bakker
"""


class TriblerException(Exception):
    """Super class for all Tribler-specific Exceptions the Tribler Core throws."""


class OperationNotPossibleAtRuntimeException(TriblerException):
    """The requested operation is not possible after the Session or Download has been started."""


class InvalidSignatureException(TriblerException):
    """Raised when encountering an invalid signature. """


class InvalidChannelNodeException(TriblerException):
    """Raised when trying to create an inconsistent GigaChannel entry    """


class SaveResumeDataError(TriblerException):
    """This error is used when the resume data of a download fails to save."""


class InvalidConfigException(TriblerException):
    """The config file doesn't adhere to the config specification."""


class TrustGraphException(TriblerException):
    """Exception specific to Trust graph."""


class TriblerCoreTestException(TriblerException):
    """Can be intentionally generated in Core by pressing Ctrl+Alt+Shift+C"""
