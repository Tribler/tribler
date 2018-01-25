from Tribler.dispersy.payload import Payload


class EstablishIntroPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, circuit_id, identifier, info_hash):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(info_hash, basestring), type(info_hash)

            super(EstablishIntroPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier
            self._info_hash = info_hash

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier

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


class KeyRequestPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, identifier, info_hash):
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(info_hash, basestring), type(info_hash)
            assert len(info_hash) == 20, len(info_hash)

            super(KeyRequestPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._info_hash = info_hash

        @property
        def identifier(self):
            return self._identifier

        @property
        def info_hash(self):
            return self._info_hash


class KeyResponsePayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, identifier, public_key, pex_peers):
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(public_key, basestring), type(public_key)
            assert all(isinstance(pex_peer, basestring) for pex_peer in pex_peers)

            super(KeyResponsePayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._public_key = public_key
            self._pex_peers = pex_peers

        @property
        def identifier(self):
            return self._identifier

        @property
        def public_key(self):
            return self._public_key

        @property
        def pex_peers(self):
            return self._pex_peers


class CreateE2EPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, identifier, info_hash, node_id, node_public_key, key):
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(info_hash, basestring), type(info_hash)
            assert len(info_hash) == 20, len(info_hash)
            assert isinstance(node_id, basestring), type(node_id)
            assert isinstance(node_public_key, basestring), type(node_public_key)
            assert isinstance(key, basestring), type(key)

            super(CreateE2EPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._info_hash = info_hash
            self._node_id = node_id
            self._node_public_key = node_public_key
            self._key = key

        @property
        def identifier(self):
            return self._identifier

        @property
        def info_hash(self):
            return self._info_hash

        @property
        def node_id(self):
            return self._node_id

        @property
        def node_public_key(self):
            return self._node_public_key

        @property
        def key(self):
            return self._key


class CreatedE2EPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, identifier, key, auth, rp_sock_addr):
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(key, basestring), type(key)
            assert isinstance(auth, basestring), type(auth)

            super(CreatedE2EPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._key = key
            self._auth = auth
            self._rp_sock_addr = rp_sock_addr

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
        def rp_sock_addr(self):
            return self._rp_sock_addr


class DHTRequestPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, circuit_id, identifier, info_hash):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(info_hash, basestring), type(info_hash)
            assert len(info_hash) == 20, len(info_hash)

            super(DHTRequestPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier
            self._info_hash = info_hash

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier

        @property
        def info_hash(self):
            return self._info_hash


class DHTResponsePayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, circuit_id, identifier, info_hash, peers):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(info_hash, basestring), type(info_hash)
            assert len(info_hash) == 20, len(info_hash)
            assert all(isinstance(peer, basestring) for peer in peers)

            super(DHTResponsePayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier
            self._info_hash = info_hash
            self._peers = peers

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier

        @property
        def info_hash(self):
            return self._info_hash

        @property
        def peers(self):
            return self._peers


class LinkE2EPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, circuit_id, identifier, cookie):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(cookie, basestring), type(cookie)

            super(LinkE2EPayload.Implementation, self).__init__(meta)
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


class LinkedE2EPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, circuit_id, identifier):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)

            super(LinkedE2EPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier
