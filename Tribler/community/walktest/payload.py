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
        def __init__(self, meta, destination_address, source_internal_address, advice, identifier):
            """
            Create the payload for an introduction-request message.

            DESTINATION_ADDRESS is the address of the receiver.  Effectively this should be the
            external address that others can use to contact the receiver.

            SOURCE_INTERNAL_ADDRESS is the internal address of the sender.  Nodes that are behind
            the same NAT or firewall can use this address to connect with each other.

            ADVICE is a boolean value.  When True the receiver will introduce the sender to a new
            node.  This introduction will be facilitated by the receiver sending a puncture-request
            to the new node.
            
            IDENTIFIER is a number that must be given in the associated introduction-response.  This
            number allows to distinguish between multiple introduction-response messages.
            """
            assert is_address(destination_address)
            assert is_address(source_internal_address)
            assert isinstance(advice, bool)
            assert isinstance(identifier, int)
            assert 0 <= identifier < 2**16
            super(IntroductionRequestPayload.Implementation, self).__init__(meta)
            self._destination_address = destination_address
            self._source_internal_address = source_internal_address
            self._advice = advice
            self._identifier = identifier

        @property
        def destination_address(self):
            return self._destination_address

        @property
        def source_internal_address(self):
            return self._source_internal_address

        @property
        def advice(self):
            return self._advice

        @property
        def identifier(self):
            return self._identifier

class IntroductionResponsePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, destination_address, internal_introduction_address, external_introduction_address, identifier):
            """
            Create the payload for an introduction-response message.

            DESTINATION_ADDRESS is the address of the receiver.  Effectively this should be the
            external address that others can use to contact the receiver.

            INTERNAL_INTRODUCTION_ADDRESS is the internal address of the node that the sender
            advises the receiver to contact.  This address is zero when the associated request did
            not want advice.
            
            EXTERNAL_INTRODUCTION_ADDRESS is the external address of the node that the sender
            advises the receiver to contact.  This address is zero when the associated request did
            not want advice.
            
            IDENTIFIER is a number that was given in the associated introduction-request.  This
            number allows to distinguish between multiple introduction-response messages.

            When the associated request wanted advice the sender will also sent a puncture-request
            message to either the internal_introduction_address or the external_introduction_address
            (depending on their positions).  The introduced node must sent a puncture message to the
            receiver to punch a hole in its NAT.
            """
            assert is_address(destination_address)
            assert is_address(internal_introduction_address)
            assert is_address(external_introduction_address)
            assert isinstance(identifier, int)
            assert 0 <= identifier < 2**16
            super(IntroductionResponsePayload.Implementation, self).__init__(meta)
            self._destination_address = destination_address
            self._internal_introduction_address = internal_introduction_address
            self._external_introduction_address = external_introduction_address
            self._identifier = identifier

        @property
        def footprint(self):
            return "IntroductionResponsePayload:%d" % self._identifier

        @property
        def destination_address(self):
            return self._destination_address

        @property
        def internal_introduction_address(self):
            return self._internal_introduction_address

        @property
        def external_introduction_address(self):
            return self._external_introduction_address

        @property
        def identifier(self):
            return self._identifier

    def generate_footprint(self, identifier):
        assert isinstance(identifier, int)
        assert 0 <= identifier < 2**16
        return "IntroductionResponsePayload:%d" % identifier

class PunctureRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, internal_walker_address, external_walker_address):
            """
            Create the payload for a puncture-request payload.

            INTERNAL_WALKER_ADDRESS is the internal address of the node that the sender wants us to
            contact.  This contact attempt should punch a hole in our NAT to allow the node to
            connect to us.

            EXTERNAL_WALKER_ADDRESS is the external address of the node that the sender wants us to
            contact.  This contact attempt should punch a hole in our NAT to allow the node to
            connect to us.
            """
            assert is_address(internal_walker_address)
            assert is_address(external_walker_address)
            super(PunctureRequestPayload.Implementation, self).__init__(meta)
            self._internal_walker_address = internal_walker_address
            self._external_walker_address = external_walker_address

        @property
        def internal_walker_address(self):
            return self._internal_walker_address

        @property
        def external_walker_address(self):
            return self._external_walker_address

class PuncturePayload(Payload):
    class Implementation(Payload.Implementation):
        pass
