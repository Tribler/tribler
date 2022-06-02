from __future__ import annotations

from typing import Optional, TYPE_CHECKING, Type

if TYPE_CHECKING:
    from tribler.core.components.ipv8.eva.transfer.base import Transfer


class TransferException(Exception):
    def __init__(self, message: str = '', transfer: Optional[Transfer] = None, remote: bool = False):
        super().__init__(message)
        self.transfer = transfer
        self.remote = remote


class SizeException(TransferException):
    pass


class TimeoutException(TransferException):
    pass


class ValueException(TransferException):
    pass


class TransferLimitException(TransferException):
    """Maximum simultaneous transfers limit exceeded"""


class TransferCancelledException(TransferException):
    """Raised in the case that future was cancelled"""


class RequestRejected(TransferException):
    """The request was rejected on a sender's side"""


# This codes are using for `TransferException` serialization. Don't change existing numbers.
# If you want to add a new one, then increase the most latest number.
codes_for_serialization = {
    0: TransferException,
    1: SizeException,
    2: TimeoutException,
    3: ValueException,
    5: TransferLimitException,
    6: TransferCancelledException,
    7: RequestRejected,
}

# this variable is a swapped codes_for_serialization dictionary
_class_to_code = {codes_for_serialization[code]: code for code in codes_for_serialization}


def to_code(exception: Type[TransferException]) -> int:
    """Convert the exception to the code"""
    return _class_to_code.get(exception, 0)


def to_class(code: int) -> Type[TransferException]:
    """Convert the code to the exception"""
    return codes_for_serialization.get(code, TransferException)
