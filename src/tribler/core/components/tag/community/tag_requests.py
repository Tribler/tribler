from collections import defaultdict


class PeerValidationError(ValueError):
    ...


class TagRequests:
    """ This class is design for controlling requests during pull-based gossip.

    The main idea:
        * Before a request, a client registered a peer with some number of expected responses
        * While a response, the controller decrements number of expected responses for this peer
        * The controller validates response by checking that expected responses for this peer is greater then 0
    """

    def __init__(self):
        self.requests = defaultdict(int)

    def register_peer(self, peer, number_of_responses):
        self.requests[peer] = number_of_responses

    def validate_peer(self, peer):
        if self.requests[peer] <= 0:
            raise PeerValidationError(f'Peer has exhausted his response count {peer}')

        self.requests[peer] -= 1

    def clear_requests(self):
        self.requests = defaultdict(int)
