from Tribler.Core.dispersy.payload import Payload

class ContactPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier):
            assert isinstance(identifier, int)
            assert 0 <= identifier < 2**16
            super(ContactPayload.Implementation, self).__init__(meta)
            self._identifier = identifier

        @property
        def identifier(self):
            return self._identifier
