from Tribler.dispersy.payload import Payload

class PingPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, ip, port, time):
            super(PingPayload.Implementation, self).__init__(meta)
            self._ip = ip
            self._port = port
            self._time = time

        @property
        def ip(self):
            return self._ip

        @property
        def port(self):
            return self._port

        @property
        def time(self):
            return self._time

class PongPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, ip, port, time):
            super(PongPayload.Implementation, self).__init__(meta)
            self._ip = ip
            self._port = port
            self._time = time

        @property
        def ip(self):
            return self._ip

        @property
        def port(self):
            return self._port

        @property
        def time(self):
            return self._time

class RequestLatenciesPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, ip, port, hops, relay_list):
            super(RequestLatenciesPayload.Implementation, self).__init__(meta)
            self._ip = ip
            self._port = port
            self._hops = hops
            self._relay_list = relay_list

        @property
        def ip(self):
            return self._ip

        @property
        def port(self):
            return self._port

        @property
        def hops(self):
            return self._hops

        @property
        def relay_list(self):
            return self._relay_list

class ResponseLatenciesPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, ip, port, latencies, relay_list):
            super(ResponseLatenciesPayload.Implementation, self).__init__(meta)
            self._ip = ip
            self._port = port
            self._latencies = latencies
            self._relay_list = relay_list

        @property
        def ip(self):
            return self._ip

        @property
        def port(self):
            return self._port

        @property
        def latencies(self):
            return self._latencies

        @property
        def relay_list(self):
            return self._relay_list