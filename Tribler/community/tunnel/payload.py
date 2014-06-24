from Tribler.dispersy.payload import Payload


class CellPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, message_type, encrypted_message=""):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(message_type, basestring)
            assert isinstance(encrypted_message, basestring)

            super(CellPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._message_type = message_type
            self._encrypted_message = encrypted_message

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def message_type(self):
            return self._message_type

        @property
        def encrypted_message(self):
            return self._encrypted_message


class CreatePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, key="\0"*336, public_key=""):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(key, basestring), type(key)
            assert isinstance(public_key, basestring)

            super(CreatePayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._key = key
            self._public_key = public_key

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def key(self):
            return self._key

        @property
        def public_key(self):
            return self._public_key


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


class PingPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, identifier):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)

            super(PingPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier


class PongPayload(PingPayload):
    pass
