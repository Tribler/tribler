from asyncio import Future

from ipv8.requestcache import RandomNumberCache


class HTTPRequestCache(RandomNumberCache):

    def __init__(self, community, circuit_id):
        super().__init__(community.request_cache, "http-request")
        self.circuit_id = circuit_id
        self.response = {}
        self.response_future = Future()
        self.register_future(self.response_future)

    def add_response(self, payload):
        self.response[payload.part] = payload.response
        if len(self.response) == payload.total and not self.response_future.done():
            self.response_future.set_result(b''.join([t[1] for t in sorted(self.response.items())]))
            return True
        return False

    def on_timeout(self):
        pass
