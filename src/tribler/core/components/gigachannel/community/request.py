from ipv8.requestcache import RandomNumberCache


class SearchRequestCache(RandomNumberCache):
    """
    This request cache keeps track of all outstanding search requests within the GigaChannelCommunity.
    """

    def __init__(self, request_cache, uuid, peers):
        super().__init__(request_cache, "remote-search-request")
        self.request_cache = request_cache
        self.uuid = uuid

    @property
    def timeout_delay(self):
        return 30.0

    def on_timeout(self):
        pass

    def remove_request(self):
        if self.request_cache.has(self.prefix, self.number):
            try:
                self.request_cache.pop(self.prefix, self.number)
            except KeyError:
                pass
