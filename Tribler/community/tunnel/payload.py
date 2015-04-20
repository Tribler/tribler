from Tribler.dispersy.payload import Payload, IntroductionRequestPayload,\
    IntroductionResponsePayload


class TunnelIntroductionRequestPayload(IntroductionRequestPayload):
    
    class Implementation(IntroductionRequestPayload.Implementation):

        def __init__(self, meta, destination_address, source_lan_address, source_wan_address, advice, connection_type, sync, identifier, exitnode = False):
            super(TunnelIntroductionRequestPayload.Implementation, self).__init__(meta, destination_address, source_lan_address, source_wan_address, advice, connection_type, sync, identifier)
            assert isinstance(exitnode, bool), type(exitnode)
            self._exitnode = exitnode
        
        @property 
        def exitnode(self):
            return self._exitnode
            

class TunnelIntroductionResponsePayload(IntroductionResponsePayload):
    
    class Implementation(IntroductionResponsePayload.Implementation):

        def __init__(self, meta, destination_address, source_lan_address, source_wan_address, lan_introduction_address, wan_introduction_address, connection_type, tunnel, identifier, exitnode = False):
            super(TunnelIntroductionResponsePayload.Implementation, self).__init__(meta, destination_address, source_lan_address, source_wan_address, lan_introduction_address, wan_introduction_address, connection_type, tunnel, identifier)
            assert isinstance(exitnode, bool), type(exitnode)
            self._exitnode = exitnode
        
        
        @property 
        def exitnode(self):
            return self._exitnode
         

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

        def __init__(self, meta, circuit_id, node_id, node_public_key, key):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(node_id, basestring), type(node_id)
            assert isinstance(node_public_key, basestring), type(node_public_key)
            assert isinstance(key, basestring), type(key)

            super(CreatePayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._node_id = node_id
            self._node_public_key = node_public_key
            self._key = key

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def node_id(self):
            return self._node_id

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

        def __init__(self, meta, circuit_id, node_id, node_public_key, node_addr, key):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(node_id, basestring), type(node_id)
            assert isinstance(node_public_key, basestring), type(node_public_key)
            assert node_addr is None or isinstance(node_addr, tuple), type(node_addr)
            assert isinstance(key, basestring), type(key)

            super(ExtendPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._node_id = node_id
            self._node_public_key = node_public_key
            self._node_addr = node_addr
            self._key = key

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def node_id(self):
            return self._node_id

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

        def __init__(self, meta, identifier, public_key):
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(public_key, basestring), type(public_key)

            super(KeyResponsePayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._public_key = public_key

        @property
        def identifier(self):
            return self._identifier

        @property
        def public_key(self):
            return self._public_key


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
