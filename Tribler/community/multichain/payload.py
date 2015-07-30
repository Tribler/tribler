from Tribler.dispersy.payload import Payload

""" ID to indicate the block was not (yet) filled in by the responder.
This can occur during signature request or in the database if the request has failed."""
EMPTY_HASH = '0'*19+'1'


class SignaturePayload(Payload):
    """
    Payload for message that will respond to a Signature Request containing
    the Signature of {timestamp,signature_requester}.
    """

    class Implementation(Payload.Implementation):
        def __init__(self, meta, up, down, total_up_requester, total_down_requester,
                     sequence_number_requester, previous_hash_requester,
                     total_up_responder=0, total_down_responder=0,
                     sequence_number_responder=-1, previous_hash_responder=''):
            super(SignaturePayload.Implementation, self).__init__(meta)
            """ Set the interaction part of the message """
            self._up = up
            self._down = down
            """ Set the requester part of the message """
            self._total_up_requester = total_up_requester
            self._total_down_requester = total_down_requester
            self._sequence_number_requester = sequence_number_requester
            self._previous_hash_requester = previous_hash_requester
            """ Set the responder part of the message. """
            self._total_up_responder = total_up_responder
            self._total_down_responder = total_down_responder
            self._sequence_number_responder = sequence_number_responder
            self._previous_hash_responder = previous_hash_responder if previous_hash_responder \
                else EMPTY_HASH

        @property
        def up(self):
            return self._up

        @property
        def down(self):
            return self._down

        @property
        def total_up_requester(self):
            return self._total_up_requester

        @property
        def total_down_requester(self):
            return self._total_down_requester

        @property
        def sequence_number_requester(self):
            return self._sequence_number_requester

        @property
        def previous_hash_requester(self):
            return self._previous_hash_requester

        @property
        def total_up_responder(self):
            return self._total_up_responder

        @property
        def total_down_responder(self):
            return self._total_down_responder

        @property
        def sequence_number_responder(self):
            return self._sequence_number_responder

        @property
        def previous_hash_responder(self):
            return self._previous_hash_responder


class BlockRequestPayload(Payload):
    """
    Request a block with a specific sequence number or the latest if -1.
    """

    class Implementation(Payload.Implementation):

        def __init__(self, meta, requested_sequence_number=-1):
            super(BlockRequestPayload.Implementation, self).__init__(meta)
            self._requested_sequence_number = requested_sequence_number

        @property
        def requested_sequence_number(self):
            return self._requested_sequence_number


class BlockResponsePayload(Payload):
    """
    Payload for message that will respond to a Signature Request containing
    the Signature of {timestamp,signature_requester}.
    """

    class Implementation(Payload.Implementation):
        def __init__(self, meta, up, down, total_up_requester, total_down_requester,
                     sequence_number_requester, previous_hash_requester,
                     total_up_responder, total_down_responder,
                     sequence_number_responder, previous_hash_responder,
                     public_key_requester, signature_requester,
                     public_key_responder, signature_responder):
            super(BlockResponsePayload.Implementation, self).__init__(meta)
            """ Set the interaction part of the message """
            self._up = up
            self._down = down
            """ Set the requester part of the message """
            self._total_up_requester = total_up_requester
            self._total_down_requester = total_down_requester
            self._sequence_number_requester = sequence_number_requester
            self._previous_hash_requester = previous_hash_requester
            """ Set the responder part of the message. """
            self._total_up_responder = total_up_responder
            self._total_down_responder = total_down_responder
            self._sequence_number_responder = sequence_number_responder
            self._previous_hash_responder = previous_hash_responder
            """ Set the authentication part of the message. """
            self._signature_requester = signature_requester
            self._public_key_requester = public_key_requester
            self._signature_responder = signature_responder
            self._public_key_responder = public_key_responder

        @property
        def up(self):
            return self._up

        @property
        def down(self):
            return self._down

        @property
        def total_up_requester(self):
            return self._total_up_requester

        @property
        def total_down_requester(self):
            return self._total_down_requester

        @property
        def sequence_number_requester(self):
            return self._sequence_number_requester

        @property
        def previous_hash_requester(self):
            return self._previous_hash_requester

        @property
        def total_up_responder(self):
            return self._total_up_responder

        @property
        def total_down_responder(self):
            return self._total_down_responder

        @property
        def sequence_number_responder(self):
            return self._sequence_number_responder

        @property
        def previous_hash_responder(self):
            return self._previous_hash_responder

        @property
        def signature_requester(self):
            return self._signature_requester

        @property
        def public_key_requester(self):
            return self._public_key_requester

        @property
        def signature_responder(self):
            return self._signature_responder

        @property
        def public_key_responder(self):
            return self._public_key_responder