from struct import pack, unpack_from

from authentication import MultiMemberAuthentication, MemberAuthentication
from community import Community
from conversion import BinaryConversion
from debug import Node
from destination import MemberDestination, CommunityDestination, SubjectiveDestination, SimilarityDestination
from distribution import DirectDistribution, FullSyncDistribution, LastSyncDistribution
from message import Message, DropPacket
from member import MyMember
from payload import Payload
from resolution import PublicResolution

from dprint import dprint

#
# Node
#

class DebugNode(Node):
    def _create_text_message(self, message_name, text, global_time):
        assert isinstance(message_name, unicode)
        assert isinstance(text, str)
        assert isinstance(global_time, (int, long))
        meta = self._community.get_meta_message(message_name)
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time),
                              meta.destination.implement(),
                              meta.payload.implement(text))

    def _create_sequence_text_message(self, message_name, text, global_time, sequence_number):
        assert isinstance(message_name, unicode)
        assert isinstance(text, str)
        assert isinstance(global_time, (int, long))
        assert isinstance(sequence_number, (int, long))
        meta = self._community.get_meta_message(message_name)
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time, sequence_number),
                              meta.destination.implement(),
                              meta.payload.implement(text))

    def create_last_1_test_message(self, text, global_time):
        return self._create_text_message(u"last-1-test", text, global_time)

    def create_last_9_nosequence_test_message(self, text, global_time):
        return self._create_text_message(u"last-9-nosequence-test", text, global_time)

    # def create_last_9_sequence_test_message(self, text, global_time, sequence_number):
    #     return self._create_sequence_text_message(u"last-9-sequence-test", text, global_time, sequence_number)

    def create_full_sync_text_message(self, text, global_time):
        return self._create_text_message(u"full-sync-text", text, global_time)

    def create_in_order_text_message(self, text, global_time):
        return self._create_text_message(u"in-order-text", text, global_time)

    def create_out_order_text_message(self, text, global_time):
        return self._create_text_message(u"out-order-text", text, global_time)

    def create_random_order_text_message(self, text, global_time):
        return self._create_text_message(u"random-order-text", text, global_time)

    def create_taste_aware_message(self, number, global_time, sequence_number):
        assert isinstance(number, (int, long))
        meta = self._community.get_meta_message(u"taste-aware-record")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time, sequence_number),
                              meta.destination.implement(),
                              meta.payload.implement(number))

    def create_taste_aware_message_last(self, number, global_time, sequence_number):
        assert isinstance(number, (int, long))
        meta = self._community.get_meta_message(u"taste-aware-record-last")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(global_time, sequence_number),
                              meta.destination.implement(),
                              meta.payload.implement(number))

    def create_subjective_set_text_message(self, text, global_time):
        return self._create_text_message(u"subjective-set-text", text, global_time)

#
# Conversion
#

class DebugCommunityConversion(BinaryConversion):
    def __init__(self, community):
        super(DebugCommunityConversion, self).__init__(community, "\x00\x02")
        self.define_meta_message(chr(1), community.get_meta_message(u"last-1-test"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(2), community.get_meta_message(u"last-9-nosequence-test"), self._encode_text, self._decode_text)
        # self.define_meta_message(chr(3), community.get_meta_message(u"last-9-sequence-test"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(4), community.get_meta_message(u"double-signed-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(5), community.get_meta_message(u"triple-signed-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(6), community.get_meta_message(u"taste-aware-record"), self._encode_taste_aware_record, self._decode_taste_aware_record)
        self.define_meta_message(chr(7), community.get_meta_message(u"taste-aware-record-last"), self._encode_taste_aware_record, self._decode_taste_aware_record)
        self.define_meta_message(chr(8), community.get_meta_message(u"full-sync-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(9), community.get_meta_message(u"in-order-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(10), community.get_meta_message(u"out-order-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(11), community.get_meta_message(u"random-order-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(12), community.get_meta_message(u"subjective-set-text"), self._encode_text, self._decode_text)

    def _encode_text(self, message):
        return pack("!B", len(message.payload.text)), message.payload.text

    def _decode_text(self, meta_message, offset, data):
        if len(data) < offset + 1:
            raise DropPacket("Insufficient packet size")

        text_length, = unpack_from("!B", data, offset)
        offset += 1

        if len(data) < offset + text_length:
            raise DropPacket("Insufficient packet size")

        text = data[offset:offset+text_length]
        offset += text_length

        return offset, meta_message.payload.implement(text)

    def _encode_taste_aware_record(self, message):
        return pack("!L", message.payload.number),

    def _decode_taste_aware_record(self, meta_message, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")

        number, = unpack_from("!L", data, offset)
        offset += 8

        return offset, meta_message.payload.implement(number)

#
# Payload
#

class TextPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, text):
            assert isinstance(text, str)
            super(TextPayload.Implementation, self).__init__(meta)
            self._text = text

        @property
        def text(self):
            return self._text

class TasteAwarePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, number):
            assert isinstance(number, (int, long))
            super(TasteAwarePayload.Implementation, self).__init__(meta)
            self._number = number

        @property
        def number(self):
            return self._number

#
# Community
#

class DebugCommunity(Community):
    """
    Community to debug Dispersy related messages and policies.
    """
    @property
    def dispersy_candidate_request_initial_delay(self):
        # disable candidate
        return 0.0

    @property
    def dispersy_sync_initial_delay(self):
        # disable sync
        return 0.0

    def initiate_conversions(self):
        return [DebugCommunityConversion(self)]

    def initiate_meta_messages(self):
        return [Message(self, u"last-1-test", MemberAuthentication(), PublicResolution(), LastSyncDistribution(enable_sequence_number=False, synchronization_direction=u"in-order", history_size=1), CommunityDestination(node_count=10), TextPayload(), self.check_text, self.on_text),
                Message(self, u"last-9-nosequence-test", MemberAuthentication(), PublicResolution(), LastSyncDistribution(enable_sequence_number=False, synchronization_direction=u"in-order", history_size=9), CommunityDestination(node_count=10), TextPayload(), self.check_text, self.on_text),
                # Message(self, u"last-9-sequence-test", MemberAuthentication(), PublicResolution(), LastSyncDistribution(enable_sequence_number=True, synchronization_direction=u"in-order", history_size=9), CommunityDestination(node_count=10), TextPayload()),
                Message(self, u"double-signed-text", MultiMemberAuthentication(count=2, allow_signature_func=self.allow_double_signed_text), PublicResolution(), DirectDistribution(), MemberDestination(), TextPayload(), self.check_text, self.on_text),
                Message(self, u"triple-signed-text", MultiMemberAuthentication(count=3, allow_signature_func=self.allow_triple_signed_text), PublicResolution(), DirectDistribution(), MemberDestination(), TextPayload(), self.check_text, self.on_text),
                Message(self, u"taste-aware-record", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"in-order"), SimilarityDestination(cluster=1, size=16, minimum_bits=6, maximum_bits=10, threshold=12), TasteAwarePayload(), self.check_text, self.on_taste_aware_record),
                Message(self, u"taste-aware-record-last", MemberAuthentication(), PublicResolution(), LastSyncDistribution(enable_sequence_number=False, synchronization_direction=u"in-order", history_size=1), SimilarityDestination(cluster=2, size=16, minimum_bits=6, maximum_bits=10, threshold=12), TasteAwarePayload(), self.check_text, self.on_taste_aware_record),
                Message(self, u"full-sync-text", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"in-order"), CommunityDestination(node_count=10), TextPayload(), self.check_text, self.on_text),
                Message(self, u"in-order-text", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"in-order"), CommunityDestination(node_count=10), TextPayload(), self.check_text, self.on_text),
                Message(self, u"out-order-text", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"out-order"), CommunityDestination(node_count=10), TextPayload(), self.check_text, self.on_text),
                Message(self, u"random-order-text", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"random-order"), CommunityDestination(node_count=10), TextPayload(), self.check_text, self.on_text),
                Message(self, u"subjective-set-text", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"in-order"), SubjectiveDestination(cluster=1, node_count=10), TextPayload(), self.check_text, self.on_text),
                ]

    def create_full_sync_text(self, text, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"full-sync-text")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(text))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    #
    # double-signed-text
    #

    def create_double_signed_text(self, text, member, response_func, response_args=(), timeout=10.0, store=True, forward=True):
        meta = self.get_meta_message(u"double-signed-text")
        message = meta.implement(meta.authentication.implement([self._my_member, member]),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(member),
                                 meta.payload.implement(text))
        return self.create_dispersy_signature_request(message, response_func, response_args, timeout, store, forward)

    def create_taste_aware_record(self, number, sequence_number):
        meta = self.get_meta_message(u"taste-aware-record")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(self._timeline.global_time, sequence_number),
                              meta.destination.implement(),
                              meta.payload.implement(number))

    def create_taste_aware_record_last(self, number, sequence_number):
        meta = self.get_meta_message(u"taste-aware-record-last")
        return meta.implement(meta.authentication.implement(self._my_member),
                              meta.distribution.implement(self._timeline.global_time, sequence_number),
                              meta.destination.implement(),
                              meta.payload.implement(number))

    def allow_double_signed_text(self, message):
        """
        Received a request to sign MESSAGE.
        """
        dprint(message, " \"", message.payload.text, "\"")
        assert message.payload.text in ("Allow=True", "Allow=False")
        return message.payload.text == "Allow=True"

    #
    # triple-signed-text
    #

    def create_triple_signed_text(self, text, member1, member2, response_func, response_args=(), timeout=10.0, store=True, forward=True):
        meta = self.get_meta_message(u"triple-signed-text")
        message = meta.implement(meta.authentication.implement([self._my_member, member1, member2]),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(member1, member2),
                                 meta.payload.implement(text))
        return self.create_dispersy_signature_request(message, response_func, response_args, timeout, store, forward)

    def allow_triple_signed_text(self, message):
        """
        Received a request to sign MESSAGE.
        """
        dprint(message)
        assert message.payload.text in ("Allow=True", "Allow=False")
        return message.payload.text == "Allow=True"

    #
    # taste-aware-record
    #

    def on_taste_aware_record(self, address, message):
        """
        Received a taste aware record.
        """
        dprint(message.payload.number)

    #
    # any text-payload
    #

    def check_text(self, messages):
        for message in messages:
            if not self._timeline.check(message):
                raise RuntimeError()
            yield message

    def on_text(self, messages):
        """
        Received a text message.
        """
        for message in messages:
            if not "Dprint=False" in message.payload.text:
                dprint(message, " \"", message.payload.text, "\"")
