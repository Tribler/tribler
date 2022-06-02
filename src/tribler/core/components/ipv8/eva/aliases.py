from typing import Callable, Coroutine

from ipv8.types import Peer

from tribler.core.components.ipv8.eva.exceptions import TransferException
from tribler.core.components.ipv8.eva.result import TransferResult

TransferCompleteCallback = Callable[[TransferResult], Coroutine]
TransferErrorCallback = Callable[[Peer, TransferException], Coroutine]
TransferRequestCallback = Callable[[Peer, bytes], Coroutine]
