from Tribler.Core.dispersy.payload import Payload

if __debug__:
    def is_address(address):
        assert isinstance(address, tuple), type(address)
        assert len(address) == 2, len(address)
        assert isinstance(address[0], str), type(address[0])
        assert address[0], address[0]
        assert isinstance(address[1], int), type(address[1])
        assert address[1] >= 0, address[1]
        return True

class IntroductionRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, public_address, identifier):
            """
            Create the payload for an introduction-request message.

            PUBLIC_ADDRESS is the address where this introduction-response was sent to.  Effectively
            this should be the public, or external, address that other can use to contact the
            receiver of this message.

            IDENTIFIER is a number that should be given in the response aswell.  This number allows
            us to distinguish between multiple incoming introduction-response messages.
            """
            assert is_address(public_address)
            assert isinstance(identifier, int)
            assert 0 <= identifier < 2**16
            super(IntroductionRequestPayload.Implementation, self).__init__(meta)
            self._public_address = public_address
            self._identifier = identifier

        @property
        def public_address(self):
            return self._public_address

        @property
        def identifier(self):
            return self._identifier

class IntroductionResponsePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, public_address, introduction_address, identifier):
            """
            Create the payload for an introduction-response message.

            PUBLIC_ADDRESS is the address where this introduction-response was sent to.  Effectively
            this should be the public, or external, address that other can use to contact the
            receiver of this message.

            INTRODUCTION_ADDRESS is the address of a node that we advise you to contact.  The sender
            of the introduction-response has also sent a puncture-request message to
            INTRODUCTION_ADDRESS asking it to puncture a hole in its own NAT using a puncture
            message.

            IDENTIFIER is a number that was given in the request.  This number allows us to match
            the request to this specific response.
            """
            assert is_address(public_address)
            assert is_address(introduction_address)
            assert isinstance(identifier, int)
            assert 0 <= identifier < 2**16
            super(IntroductionResponsePayload.Implementation, self).__init__(meta)
            self._public_address = public_address
            self._introduction_address = introduction_address
            self._identifier = identifier

        @property
        def footprint(self):
            return "IntroductionResponsePayload:%d" % self._identifier

        @property
        def public_address(self):
            return self._public_address

        @property
        def introduction_address(self):
            return self._introduction_address

        @property
        def identifier(self):
            return self._identifier

    def generate_footprint(self, identifier):
        assert isinstance(identifier, int)
        assert 0 <= identifier < 2**16
        return "IntroductionResponsePayload:%d" % identifier

class PunctureRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, walker_address):
            """
            Create the payload for a puncture-request payload.

            WALKER_ADDRESS is the address that the sender wants us to contact.  This contact attempt
            should puncture a hole in our NAT to allow the node at WALKER_ADDRESS to connect to us.
            """
            assert is_address(walker_address)
            super(PunctureRequestPayload.Implementation, self).__init__(meta)
            self._walker_address = walker_address

        @property
        def walker_address(self):
            return self._walker_address

class PuncturePayload(Payload):
    class Implementation(Payload.Implementation):
        pass
