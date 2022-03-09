from asyncio import Future

from ipv8.requestcache import NumberCache, RandomNumberCache


class BalanceRequestCache(NumberCache):

    def __init__(self, community, circuit_id, balance_future):
        super().__init__(community.request_cache, "balance-request", circuit_id)
        self.circuit_id = circuit_id
        self.balance_future = balance_future
        self.register_future(self.balance_future)

    def on_timeout(self):
        pass


class HTTPRequestCache(RandomNumberCache):

    def __init__(self, community, circuit_id):
        super().__init__(community.request_cache, "http-request")
        self.circuit_id = circuit_id
        self.response = {}
        self.response_future = Future()
        self.register_future(self.response_future)

    def add_response(self, payload):
        self.response[payload.part] = payload.response
        if len(self.response) == payload.total:
            self.response_future.set_result(b''.join([t[1] for t in sorted(self.response.items())]))
            return True
        return False

    def on_timeout(self):
        pass
