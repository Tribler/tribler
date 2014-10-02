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
        def __init__(self, meta, circuit_id, key="\0"*336):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(key, basestring), type(key)

            super(CreatePayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._key = key

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def key(self):
            return self._key


class CreatedPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, key, candidate_list):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(key, basestring), type(key)
            assert all(isinstance(key, basestring) for key in candidate_list)

            super(CreatedPayload.Implementation, self).__init__(meta)
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
        def __init__(self, meta, circuit_id, identifier, service_key):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(service_key, basestring), type(service_key)

            super(EstablishIntroPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier
            self._service_key = service_key

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier

        @property
        def service_key(self):
            return self._service_key


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
        def __init__(self, meta, circuit_id, identifier):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)

            super(RendezvousEstablishedPayload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier

        @property
        def circuit_id(self):
            return self._circuit_id

        @property
        def identifier(self):
            return self._identifier


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
        def __init__(self, meta, circuit_id, identifier, key, cookie):
            assert isinstance(circuit_id, (int, long)), type(circuit_id)
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(key, basestring), type(key)
            assert isinstance(cookie, basestring), type(cookie)

            super(Rendezvous1Payload.Implementation, self).__init__(meta)
            self._circuit_id = circuit_id
            self._identifier = identifier
            self._key = key
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
