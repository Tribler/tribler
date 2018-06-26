from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from Tribler.pyipv8.ipv8.requestcache import RandomNumberCache


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
