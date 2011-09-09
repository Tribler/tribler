from Tribler.Core.dispersy.payload import Payload

class IntroductionRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        pass

class IntroductionResponsePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, address):
            assert isinstance(address, tuple)
            assert len(address) == 2
            assert isinstance(address[0], str)
            assert address[0]
            assert isinstance(address[1], int)
            assert address[1] > 0
            super(IntroductionResponsePayload.Implementation, self).__init__(meta)
            self._address = address

        @property
        def address(self):
            return self._address

class PunctureRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, address):
            assert isinstance(address, tuple)
            assert len(address) == 2
            assert isinstance(address[0], str)
            assert address[0]
            assert isinstance(address[1], int)
            assert address[1] > 0
            super(PunctureRequestPayload.Implementation, self).__init__(meta)
            self._address = address

        @property
        def address(self):
            return self._address

class PuncturePayload(Payload):
    class Implementation(Payload.Implementation):
        pass
