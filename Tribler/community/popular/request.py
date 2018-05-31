import time
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from Tribler.pyipv8.ipv8.requestcache import RandomNumberCache


class Request(RandomNumberCache):
    """
    This request cache keeps track of all outstanding requests within the PopularCommunity.
    """
    def __init__(self, community, peer, params=None):
        super(Request, self).__init__(community.request_cache, u'request')
        self.peer = peer
        self.params = params
        self.deferred = Deferred()
        self.start_time = time.time()

    @property
    def timeout_delay(self):
        return 5.0

    def on_timeout(self):
        if not self.deferred.called:
            self._logger.error('Request to %s timed out', self.peer.address)
            self.peer.failed += 1
            self.deferred.errback(Failure(RuntimeError("Peer timeout")))

    def on_complete(self):
        self.peer.last_response = time.time()
        self.peer.failed = 0
        self.peer.rtt = time.time() - self.start_time


class SearchRequest(RandomNumberCache):
    """
    This request cache keeps track of all outstanding search requests
    """
    def __init__(self, request_cache, search_type, query):
        super(SearchRequest, self).__init__(request_cache, u"request")
        self.query = query
        self.search_type = search_type
        self.response = None
        self.deferred = Deferred()

    @property
    def timeout_delay(self):
        return 30.0

    def append_response(self, response):
        self.response.extend(response)

    def finish(self):
        self.deferred.callback(self.response)

    def on_timeout(self):
        self.deferred.errback(Failure(RuntimeError("Search timeout for query: %s" % self.query)))
