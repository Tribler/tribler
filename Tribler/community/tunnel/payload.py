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
        def __init__(self, meta, circuit_id, nodeid, node_public_key, key):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(nodeid, basestring), type(nodeid)
            assert isinstance(node_public_key, basestring), type(node_public_key)
            assert isinstance(key, basestring), type(key)

            super(CreatePayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._nodeid = nodeid
            self._node_public_key = node_public_key
            self._key = key

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def nodeid(self):
            return self._nodeid

        @property
        def node_public_key(self):
            return self._node_public_key

        @property
        def key(self):
            return self._key


class CreatedPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, key, auth, candidate_list):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(key, basestring), type(key)
            assert isinstance(auth, basestring), type(auth)
            assert all(isinstance(key, basestring) for key in candidate_list)

            super(CreatedPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._key = key
            self._auth = auth
            self._candidate_list = candidate_list

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def key(self):
            return self._key

        @property
        def auth(self):
            return self._auth

        @property
        def candidate_list(self):
            return self._candidate_list


class ExtendPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, nodeid, node_public_key, node_addr, key):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(nodeid, basestring), type(nodeid)
            assert isinstance(node_public_key, basestring), type(node_public_key)
            assert node_addr == None or isinstance(node_addr, tuple), type(node_addr)
            assert isinstance(key, basestring), type(key)

            super(ExtendPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._nodeid = nodeid
            self._node_public_key = node_public_key
            self._node_addr = node_addr
            self._key = key

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def nodeid(self):
            return self._nodeid

        @property
        def node_public_key(self):
            return self._node_public_key

        @property
        def node_addr(self):
            return self._node_addr

        @property
        def key(self):
            return self._key


class ExtendedPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, key, auth, candidate_list):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(key, basestring), type(key)
            assert isinstance(auth, basestring), type(auth)
            assert all(isinstance(key, basestring) for key in candidate_list)

            super(ExtendedPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._key = key
            self._auth = auth
            self._candidate_list = candidate_list

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def key(self):
            return self._key

        @property
        def auth(self):
            return self._auth

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


class DestroyPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, reason):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(reason, int), type(reason)

            super(DestroyPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._reason = reason

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def reason(self):
            return self._reason


class StatsRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier):
            assert isinstance(identifier, int), type(identifier)

            super(StatsRequestPayload.Implementation, self).__init__(meta)
            self._identifier = identifier

        @property
        def identifier(self):
            return self._identifier


class StatsResponsePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, stats):
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(stats, dict), type(stats)

            super(StatsResponsePayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._stats = stats

        @property
        def identifier(self):
            return self._identifier

        @property
        def stats(self):
            return self._stats


class EstablishIntroPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, identifier, service_key, info_hash):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(service_key, basestring), type(service_key)
            assert isinstance(info_hash, basestring), type(info_hash)

            super(EstablishIntroPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier
            self._service_key = service_key
            self._info_hash = info_hash

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier

        @property
        def service_key(self):
            return self._service_key

        @property
        def info_hash(self):
            return self._info_hash


class IntroEstablishedPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, identifier):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)

            super(IntroEstablishedPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier


class EstablishRendezvousPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, identifier, cookie):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(cookie, basestring), type(cookie)

            super(EstablishRendezvousPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier
            self._cookie = cookie

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier

        @property
        def cookie(self):
            return self._cookie


class RendezvousEstablishedPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, identifier, rendezvous_point_addr):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(rendezvous_point_addr, tuple), type(rendezvous_point_addr)

            super(RendezvousEstablishedPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier
            self._rendezvous_point_addr = rendezvous_point_addr

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier

        @property
        def rendezvous_point_addr(self):
            return self._rendezvous_point_addr


class KeysRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, info_hash):
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(info_hash, basestring), type(info_hash)

            super(KeysRequestPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._info_hash = info_hash

        @property
        def identifier(self):
            return self._identifier

        @property
        def info_hash(self):
            return self._info_hash


class KeysResponsePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, ip_key, service_key):
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(ip_key, basestring), type(ip_key)
            assert isinstance(service_key, basestring), type(service_key)

            super(KeysResponsePayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._ip_key = ip_key
            self._service_key = service_key

        @property
        def identifier(self):
            return self._identifier

        @property
        def ip_key(self):
            return self._ip_key

        @property
        def service_key(self):
            return self._service_key


class Intro1Payload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, identifier, key, cookie, rendezvous_point, service_key):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(key, basestring), type(key)
            assert isinstance(cookie, basestring), type(cookie)
            assert isinstance(rendezvous_point, basestring), type(rendezvous_point)
            assert isinstance(service_key, basestring), type(service_key)

            super(Intro1Payload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier
            self._key = key
            self._cookie = cookie
            self._rendezvous_point = rendezvous_point
            self._service_key = service_key

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier

        @property
        def key(self):
            return self._key

        @property
        def cookie(self):
            return self._cookie

        @property
        def rendezvous_point(self):
            return self._rendezvous_point

        @property
        def service_key(self):
            return self._service_key


class Intro2Payload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, identifier, key, cookie, rendezvous_point):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(key, basestring), type(key)
            assert isinstance(cookie, basestring), type(cookie)
            assert isinstance(rendezvous_point, basestring), type(rendezvous_point)

            super(Intro2Payload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier
            self._key = key
            self._cookie = cookie
            self._rendezvous_point = rendezvous_point

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier

        @property
        def key(self):
            return self._key

        @property
        def cookie(self):
            return self._cookie

        @property
        def rendezvous_point(self):
            return self._rendezvous_point


class Rendezvous1Payload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, identifier, key, auth, cookie):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(key, basestring), type(key)
            assert isinstance(auth, basestring), type(auth)
            assert isinstance(cookie, basestring), type(cookie)

            super(Rendezvous1Payload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier
            self._key = key
            self._auth = auth
            self._cookie = cookie

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier

        @property
        def key(self):
            return self._key

        @property
        def auth(self):
            return self._auth

        @property
        def cookie(self):
            return self._cookie


class Rendezvous2Payload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, identifier, key):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(key, basestring), type(key)

            super(Rendezvous2Payload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier
            self._key = key

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier

        @property
        def key(self):
            return self._key
