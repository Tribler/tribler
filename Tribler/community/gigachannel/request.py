from __future__ import absolute_import

from binascii import hexlify

from Tribler.pyipv8.ipv8.requestcache import RandomNumberCache


class SearchRequestCache(RandomNumberCache):
    """
    This request cache keeps track of all outstanding search requests within the GigaChannelCommunity.
    """
    def __init__(self, request_cache, uuid, peers):
        super(SearchRequestCache, self).__init__(request_cache, u"remote-search-request")
        self.request_cache = request_cache
        self.requested_peers = {hexlify(peer.mid): False for peer in peers}
        self.uuid = uuid

    @property
    def timeout_delay(self):
        return 30.0

    def on_timeout(self):
        pass

    def process_peer_response(self, peer):
        """
        Returns whether to process this response from the given peer in the community. If the peer response has
        already been processed then it is skipped. Moreover, if all the responses from the expected peers are received,
        the request is removed from the request cache.
        :param peer: Peer
        :return: True if peer has not been processed before, else False
        """
        mid = hexlify(peer.mid)
        if mid in self.requested_peers and not self.requested_peers[mid]:
            self.requested_peers[mid] = True

            # Check if all expected responses are received
            if all(self.requested_peers.values()):
                self.remove_request()

            return True
        return False

    def remove_request(self):
        if self.request_cache.has(self.prefix, self.number):
            try:
                self.request_cache.pop(self.prefix, self.number)
            except KeyError:
                pass
