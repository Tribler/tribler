from Tribler.dispersy.payload import Payload


class CreatePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, key="\0"*336, public_key="", destination_key=""):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(key, basestring), type(key)
            assert isinstance(public_key, basestring)

            super(CreatePayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._key = key
            self._public_key = public_key
            self._destination_key = destination_key

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def key(self):
            return self._key

        @property
        def public_key(self):
            return self._public_key

        @property
        def destination_key(self):
            return self._destination_key


class CreatedPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, key, candidate_list, reply_to=None):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(key, basestring), type(key)
            assert all(isinstance(key, basestring) for key in candidate_list)
            assert reply_to is None or isinstance(reply_to.payload, CreatePayload.Implementation), type(reply_to)

            super(CreatedPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._key = key
            self._candidate_list = candidate_list
            self._reply_to = reply_to

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def key(self):
            return self._key

        @property
        def candidate_list(self):
            return self._candidate_list

        @property
        def reply_to(self):
            return self._reply_to


class ExtendPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, key, extend_with):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(key, basestring), type(key)
            assert extend_with is None or isinstance(extend_with, basestring), type(extend_with)

            super(ExtendPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._key = key
            self._extend_with = extend_with

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def key(self):
            return self._key

        @property
        def extend_with(self):
            return self._extend_with


class ExtendedPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, key, candidate_list):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(key, basestring), type(key)
            assert all(isinstance(key, basestring) for key in candidate_list)

            super(ExtendedPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._key = key
            self._candidate_list = candidate_list

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def key(self):
            return self._key

        @property
        def candidate_list(self):
            return self._candidate_list


class DataPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, destination, data, origin=None):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert destination is None or isinstance(destination[0], basestring) and isinstance(destination[1], int)
            assert isinstance(data, basestring)
            assert origin is None or isinstance(origin[0], basestring) and isinstance(origin[1], int)

            super(DataPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._destination = destination
            self._data = data
            self._origin = origin

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def destination(self):
            return self._destination

        @property
        def data(self):
            return self._data

        @property
        def origin(self):
            return self._origin


class PingPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)

            super(PingPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id

        @property
        def circuit_id(self):
            return self._circuit_id


class PongPayload(PingPayload):
    pass


class StatsPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, stats):
            super(StatsPayload.Implementation, self).__init__(meta)
            self.stats = stats
