from __future__ import annotations

from asyncio import Future
from typing import TYPE_CHECKING

from ipv8.requestcache import RandomNumberCache

if TYPE_CHECKING:
    from tribler.core.tunnel.community import TriblerTunnelCommunity
    from tribler.core.tunnel.payload import HTTPResponsePayload


class HTTPRequestCache(RandomNumberCache):
    """
    A cache to keep track of an HTTP request.
    """

    def __init__(self, community: TriblerTunnelCommunity, circuit_id: int) -> None:
        """
        Create a new HTTP request cache.
        """
        super().__init__(community.request_cache, "http-request")
        self.circuit_id = circuit_id
        self.response: dict[int, bytes] = {}
        self.response_future: Future[bytes] = Future()
        self.register_future(self.response_future)

    def add_response(self, payload: HTTPResponsePayload) -> bool:
        """
        Add a received response payload that belongs to this cache.
        """
        self.response[payload.part] = payload.response
        if len(self.response) == payload.total and not self.response_future.done():
            self.response_future.set_result(b"".join([t[1] for t in sorted(self.response.items())]))
            return True
        return False

    def on_timeout(self) -> None:
        """
        We don't need to do anything on timeout.
        """
