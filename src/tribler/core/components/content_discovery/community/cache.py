from asyncio import Future

from ipv8.requestcache import RandomNumberCache


class SelectRequest(RandomNumberCache):
    def __init__(self, request_cache, prefix, request_kwargs, peer, processing_callback=None, timeout_callback=None):
        super().__init__(request_cache, prefix)
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

    def on_timeout(self):
        if self.timeout_callback is not None:
            self.timeout_callback(self)


class RequestTimeoutException(Exception):
    pass


class EvaSelectRequest(SelectRequest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # For EVA transfer it is meaningless to send more than one message
        self.packets_limit = 1

        self.processing_results = Future()
        self.register_future(self.processing_results, on_timeout=RequestTimeoutException())
