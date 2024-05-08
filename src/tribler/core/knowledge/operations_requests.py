from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ipv8.types import Peer


class PeerValidationError(ValueError):
    """
    A peer has exceeded their number of responses.
    """


class OperationsRequests:
    """
    This class is design for controlling requests during pull-based gossip.

    The main idea:
        * Before a request, a client registered a peer with some number of expected responses
        * While a response, the controller decrements number of expected responses for this peer
        * The controller validates response by checking that expected responses for this peer is greater then 0
    """

    def __init__(self) -> None:
        """
        Create a new dictionary to keep track of responses.
        """
        self.requests: dict[Peer, int] = defaultdict(int)

    def register_peer(self, peer: Peer, number_of_responses: int) -> None:
        """
        Set the number of allowed responses for a given peer.
        """
        self.requests[peer] = number_of_responses

    def validate_peer(self, peer: Peer) -> None:
        """
        Decrement the number of responses of a Peer and check if the given peer has exceeded their allowed responses.

        :raises PeerValidationError: When the given peer has less than 0 responses remaining.
        """
        if self.requests[peer] <= 0:
            msg = f"Peer has exhausted his response count {peer}"
            raise PeerValidationError(msg)

        self.requests[peer] -= 1

    def clear_requests(self) -> None:
        """
        Reset all allowed responses for all peers to 0.
        """
        self.requests = defaultdict(int)
