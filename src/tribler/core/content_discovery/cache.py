from __future__ import annotations

from binascii import hexlify
from typing import TYPE_CHECKING, Callable

from ipv8.requestcache import RandomNumberCache, RequestCache
from typing_extensions import Self

if TYPE_CHECKING:
    from ipv8.types import Peer

    from tribler.core.database.store import ProcessingResult


class SelectRequest(RandomNumberCache):
    """
    Keep track of the packets to a Peer during the answering of a select request.
    """

    def __init__(self, request_cache: RequestCache, request_kwargs: dict, peer: Peer,
                 processing_callback: Callable[[Self, list[ProcessingResult]], None] | None = None,
                 timeout_callback: Callable[[Self], None] | None = None) -> None:
        """
        Create a new select request cache.
        """
        super().__init__(request_cache, hexlify(peer.mid).decode())
        self.request_kwargs = request_kwargs
        # The callback to call on results of processing of the response payload
        self.processing_callback = processing_callback
        # The maximum number of packets to receive from any given peer from a single request.
        # This limit is imposed as a safety precaution to prevent spam/flooding
        self.packets_limit = 10

        self.peer = peer
        # Indicate if at least a single packet was returned by the queried peer.
        self.peer_responded = False

        self.timeout_callback = timeout_callback

    def on_timeout(self) -> None:
        """
        Call the timeout callback, if one is registered.
        """
        if self.timeout_callback is not None:
            self.timeout_callback(self)
