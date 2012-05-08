from hashlib import sha1
from math import ceil
from socket import inet_ntoa, inet_aton
from struct import pack, unpack_from, Struct

from authentication import NoAuthentication, MemberAuthentication, MultiMemberAuthentication
from bloomfilter import BloomFilter
from crypto import ec_check_public_bin
from destination import MemberDestination, CommunityDestination, CandidateDestination, SubjectiveDestination
from dispersydatabase import DispersyDatabase
from distribution import FullSyncDistribution, LastSyncDistribution, DirectDistribution
from message import DelayPacketByMissingMember, DelayPacketByMissingMessage, DropPacket, Packet, Message
from resolution import PublicResolution, LinearResolution, DynamicResolution

if __debug__:
    from authentication import Authentication
    from candidate import Candidate
    from destination import Destination
    from distribution import Distribution
    from dprint import dprint
    from resolution import Resolution

class Conversion(object):
    """
    A Conversion object is used to convert incoming packets to a different, possibly more recent,
    community version.  If also allows outgoing messages to be converted to a different, possibly
    older, community version.
    """
    def __init__(self, community, dispersy_version, community_version):
        """
        COMMUNITY instance that this conversion belongs to.
        DISPERSY_VERSION is the dispersy conversion identifier (on the wire version; must be one byte).
        COMMUNIY_VERSION is the community conversion identifier (on the wire version; must be one byte).

        COMMUNIY_VERSION may not be '\x00' or '\xff'.  '\x00' is used by the DefaultConversion until
        a proper conversion instance can be made for the Community.  '\xff' is reserved for when
        more than one byte is needed as a version indicator.
        """
        if __debug__: from community import Community
        assert isinstance(community, Community), type(community)
        assert isinstance(dispersy_version, str), type(dispersy_version)
        assert len(dispersy_version) == 1, dispersy_version
        assert isinstance(community_version, str), type(community_version)
        assert len(community_version) == 1, community_version

        # the dispersy database
        self._dispersy_database = DispersyDatabase.get_instance()

        # the community that this conversion belongs to.
        self._community = community

        # the messages that this instance can handle, and that this instance produces, is identified
        # by _prefix.
        self._prefix = dispersy_version + community_version + community.cid
        assert len(self._prefix) == 22 # when this assumption changes, we need to ensure the
                                       # dispersy_version and community_version properties are
                                       # returned correctly

    @property
    def community(self):
        return self._community

    @property
    def dispersy_version(self):
        return self._prefix[0]

    @property
    def community_version(self):
        return self._prefix[1]

    @property
    def version(self):
        return (self._prefix[0], self._prefix[1])

    @property
    def prefix(self):
        return self._prefix

    def decode_meta_message(self, data):
        """
        Obtain the dispersy meta message from DATA.
        @return: Message
        """
        assert isinstance(data, str)
        assert len(data) >= 22
        assert data[:22] == self._prefix
        raise NotImplementedError("The subclass must implement decode_message")

    def decode_message(self, address, data):
        """
        DATA is a string, where the first byte is the on-the-wire Dispersy version, the second byte
        is the on-the-wire Community version and the following 20 bytes is the Community Identifier.
        The rest is the message payload.

        Returns a Message instance.
        """
        assert isinstance(data, str)
        assert len(data) >= 22
        assert data[:22] == self._prefix
        raise NotImplementedError("The subclass must implement decode_message")

    def encode_message(self, message):
        """
        Encode a Message instance into a binary string where the first byte is the on-the-wire
        Dispersy version, the second byte is the on-the-wire Community version and the following 20
        bytes is the Community Identifier.  The rest is the message payload.

        Returns a binary string.
        """
        assert isinstance(message, Message)
        raise NotImplementedError("The subclass must implement encode_message")

class BinaryConversion(Conversion):
    """
    On-The-Wire binary version

    This conversion is intended to be as space efficient as possible.
    All data is encoded in a binary form.
    """
    class Placeholder(object):
        __slots__ = ["candidate", "meta", "offset", "data", "authentication", "resolution", "first_signature_offset", "destination", "distribution", "payload"]

        def __init__(self, candidate, meta, offset, data):
            self.candidate = candidate
            self.meta = meta
            self.offset = offset
            self.data = data
            self.authentication = None
            self.resolution = None
            self.first_signature_offset = 0
            self.destination = None
            self.distribution = None
            self.payload = None

    class EncodeFunctions(object):
        __slots__ = ["byte", "authentication", "signature", "resolution", "distribution", "payload"]

        def __init__(self, byte, (authentication, signature), resolution, distribution, payload):
            self.byte = byte
            self.authentication = authentication
            self.signature = signature
            self.resolution = resolution
            self.distribution = distribution
            self.payload = payload

    class DecodeFunctions(object):
        __slots__ = ["meta", "authentication", "resolution", "distribution", "destination", "payload"]

        def __init__(self, meta, authentication, resolution, distribution, destination, payload):
            self.meta = meta
            self.authentication = authentication
            self.resolution = resolution
            self.distribution = distribution
            self.destination = destination
            self.payload = payload

    def __init__(self, community, community_version):
        Conversion.__init__(self, community, "\x00", community_version)

        self._struct_B = Struct(">B")
        self._struct_BBH = Struct(">BBH")
        self._struct_BH = Struct(">BH")
        self._struct_H = Struct(">H")
        self._struct_LL = Struct(">LL")
        self._struct_Q = Struct(">Q")
        self._struct_QH = Struct(">QH")
        self._struct_QL = Struct(">QL")
        self._struct_QQHHBH = Struct(">QQHHBH")
        self._struct_ccB = Struct(">ccB")

        self._encode_message_map = dict() # message.name : EncodeFunctions
        self._decode_message_map = dict() # byte : DecodeFunctions

        # the dispersy-introduction-request and dispersy-introduction-response have several bitfield
        # flags that must be set correctly
        # reserve 1st bit for enable/disable advice
        self._encode_advice_map = {True:int("1", 2), False:int("0", 2)}
        self._decode_advice_map = dict((value, key) for key, value in self._encode_advice_map.iteritems())
        # reserve 2nd bit for enable/disable sync
        self._encode_sync_map = {True:int("10", 2), False:int("00", 2)}
        self._decode_sync_map = dict((value, key) for key, value in self._encode_sync_map.iteritems())
        # reserve 3rd bit for enable/disable tunnel (02/05/12)
        self._encode_tunnel_map = {True:int("100", 2), False:int("000", 2)}
        self._decode_tunnel_map = dict((value, key) for key, value in self._encode_tunnel_map.iteritems())
        # 4th, 5th and 6th bits are currently unused
        # reserve 7th and 8th bits for connection type
        self._encode_connection_type_map = {u"unknown":int("00000000", 2), u"public":int("10000000", 2), u"symmetric-NAT":int("11000000", 2)}
        self._decode_connection_type_map = dict((value, key) for key, value in self._encode_connection_type_map.iteritems())

        def define(value, name, encode, decode):
            try:
                meta = community.get_meta_message(name)
            except KeyError:
                if __debug__:
                    debug_non_available.append(name)
            else:
                self.define_meta_message(chr(value), meta, encode, decode)

        if __debug__:
            debug_non_available = []

        # 255 is reserved
        define(254, u"dispersy-missing-sequence", self._encode_missing_sequence, self._decode_missing_sequence)
        define(253, u"dispersy-missing-proof", self._encode_missing_proof, self._decode_missing_proof)
        define(252, u"dispersy-signature-request", self._encode_signature_request, self._decode_signature_request)
        define(251, u"dispersy-signature-response", self._encode_signature_response, self._decode_signature_response)
        define(250, u"dispersy-puncture-request", self._encode_puncture_request, self._decode_puncture_request)
        define(249, u"dispersy-puncture", self._encode_puncture, self._decode_puncture)
        define(248, u"dispersy-identity", self._encode_identity, self._decode_identity)
        define(247, u"dispersy-missing-identity", self._encode_missing_identity, self._decode_missing_identity)
        define(246, u"dispersy-introduction-request", self._encode_introduction_request, self._decode_introduction_request)
        define(245, u"dispersy-introduction-response", self._encode_introduction_response, self._decode_introduction_response)
        define(244, u"dispersy-destroy-community", self._encode_destroy_community, self._decode_destroy_community)
        define(243, u"dispersy-authorize", self._encode_authorize, self._decode_authorize)
        define(242, u"dispersy-revoke", self._encode_revoke, self._decode_revoke)
        define(241, u"dispersy-subjective-set", self._encode_subjective_set, self._decode_subjective_set)
        define(240, u"dispersy-missing-subjective-set", self._encode_missing_subjective_set, self._decode_missing_subjective_set)
        define(239, u"dispersy-missing-message", self._encode_missing_message, self._decode_missing_message)
        define(238, u"dispersy-undo-own", self._encode_undo_own, self._decode_undo_own)
        define(237, u"dispersy-undo-other", self._encode_undo_other, self._decode_undo_other)
        define(236, u"dispersy-dynamic-settings", self._encode_dynamic_settings, self._decode_dynamic_settings)
        define(235, u"dispersy-missing-last-message", self._encode_missing_last_message, self._decode_missing_last_message)

        if __debug__:
            if debug_non_available:
                dprint("unable to define non-available messages ", ", ".join(debug_non_available), level="warning")

    def define_meta_message(self, byte, meta, encode_payload_func, decode_payload_func):
        assert isinstance(byte, str)
        assert len(byte) == 1
        assert isinstance(meta, Message)
        assert 0 < ord(byte) < 255
        assert not meta.name in self._encode_message_map
        assert not byte in self._decode_message_map, "This byte has already been defined (%d)" % ord(byte)
        assert callable(encode_payload_func)
        assert callable(decode_payload_func)

        mapping = {MemberAuthentication:(self._encode_member_authentication, self._encode_member_authentication_signature),
                   MultiMemberAuthentication:(self._encode_multi_member_authentication, self._encode_multi_member_authentication_signature),
                   NoAuthentication:(self._encode_no_authentication, self._encode_no_authentication_signature),

                   PublicResolution:self._encode_public_resolution,
                   LinearResolution:self._encode_linear_resolution,
                   DynamicResolution:self._encode_dynamic_resolution,

                   FullSyncDistribution:self._encode_full_sync_distribution,
                   LastSyncDistribution:self._encode_last_sync_distribution,
                   DirectDistribution:self._encode_direct_distribution}

        self._encode_message_map[meta.name] = self.EncodeFunctions(byte, mapping[type(meta.authentication)], mapping[type(meta.resolution)], mapping[type(meta.distribution)], encode_payload_func)

        mapping = {MemberAuthentication:self._decode_member_authentication,
                   MultiMemberAuthentication:self._decode_multi_member_authentication,
                   NoAuthentication:self._decode_no_authentication,

                   DynamicResolution:self._decode_dynamic_resolution,
                   LinearResolution:self._decode_linear_resolution,
                   PublicResolution:self._decode_public_resolution,

                   DirectDistribution:self._decode_direct_distribution,
                   FullSyncDistribution:self._decode_full_sync_distribution,
                   LastSyncDistribution:self._decode_last_sync_distribution,

                   CandidateDestination:self._decode_empty_destination,
                   CommunityDestination:self._decode_empty_destination,
                   MemberDestination:self._decode_empty_destination,
                   SubjectiveDestination:self._decode_subjective_destination}

        self._decode_message_map[byte] = self.DecodeFunctions(meta, mapping[type(meta.authentication)], mapping[type(meta.resolution)], mapping[type(meta.distribution)], mapping[type(meta.destination)], decode_payload_func)

    #
    # Dispersy payload
    #

    def _encode_missing_sequence(self, message):
        payload = message.payload
        assert payload.message.name in self._encode_message_map, payload.message.name
        message_id = self._encode_message_map[payload.message.name].byte
        return (payload.member.mid, message_id, self._struct_LL.pack(payload.missing_low, payload.missing_high))

    def _decode_missing_sequence(self, placeholder, offset, data):
        if len(data) < offset + 29:
            raise DropPacket("Insufficient packet size")

        member_id = data[offset:offset+20]
        offset += 20
        members = [member for member in self._community.dispersy.get_members_from_id(member_id) if member.has_identity(self._community)]
        if not members:
            raise DelayPacketByMissingMember(self._community, member_id)
        elif len(members) > 1:
            # this is unrecoverable.  a member id without a signature is simply not globally unique.
            # This can occur when two or more nodes have the same sha1 hash.  Very unlikely.
            raise DropPacket("Unrecoverable: ambiguous member")
        member = members[0]

        decode_functions = self._decode_message_map.get(data[offset])
        if decode_functions is None:
            raise DropPacket("Invalid message")
        offset += 1

        missing_low, missing_high = self._struct_LL.unpack_from(data, offset)
        if not (0 < missing_low <= missing_high):
            raise DropPacket("Invalid missing_low and missing_high combination")
        offset += 8

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, member, decode_functions.meta, missing_low, missing_high)

    def _encode_missing_message(self, message):
        """
        Encode the payload for dispersy-missing-message.

        The payload will contain one public key, this is a binary string of variable length.  It
        also contains one or more global times, each global time is a 64 bit unsigned integer.

        The payload contains:
         - 2 bytes: the length of the public key
         - n bytes: the public key
         - 8 bytes: the global time
         - 8 bytes: the global time
         - ...
         - 8 bytes: the global time
        """
        payload = message.payload
        return (self._struct_H.pack(len(payload.member.public_key)), payload.member.public_key, pack("!%dQ" % len(payload.global_times), *payload.global_times))

    def _decode_missing_message(self, placeholder, offset, data):
        if len(data) < offset + 2:
            raise DropPacket("Insufficient packet size (_decode_missing_message.1)")

        key_length, = self._struct_H.unpack_from(data, offset)
        offset += 2

        if len(data) < offset + key_length:
            raise DropPacket("Insufficient packet size (_decode_missing_message.2)")

        key = data[offset:offset+key_length]
        if not ec_check_public_bin(key):
            raise DropPacket("Invalid cryptographic key (_decode_missing_message)")
        member = self._community.dispersy.get_member(key)
        if not member.has_identity(self._community):
            raise DelayPacketByMissingMember(self._community, member.mid)
        offset += key_length

        # there must be at least one global time in the packet
        global_time_length, mod = divmod(len(data) - offset, 8)
        if global_time_length == 0:
            raise DropPacket("Insufficient packet size (_decode_missing_message.3)")
        if mod != 0:
            raise DropPacket("Invalid packet size (_decode_missing_message)")

        global_times = unpack_from("!%dQ" % global_time_length, data, offset)
        offset += 8 * len(global_times)

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, member, global_times)

    def _encode_missing_last_message(self, message):
        """
        Encode the payload for dispersy-missing-last-message.

        The payload will contain one public key, this is a binary string of variable length.  It
        also contains the meta message where the last message is requested from.  It also contains a
        counter, i.e. how many last we want.

        The payload contains:
         - 2 bytes: the request identifier
         - 2 bytes: the length of the public key
         - n bytes: the public key
         - 1 byte:  the meta message
         - 1 byte:  the max count we want
        """
        payload = message.payload
        return (self._struct_H.pack(len(payload.member.public_key)),
                payload.member.public_key,
                self._encode_message_map[payload.message.name].byte,
                chr(payload.count))

    def _decode_missing_last_message(self, placeholder, offset, data):
        if len(data) < offset + 2:
            raise DropPacket("Insufficient packet size (_decode_missing_message.1)")

        key_length, = self._struct_H.unpack_from(data, offset)
        offset += 2

        if len(data) < offset + key_length:
            raise DropPacket("Insufficient packet size (_decode_missing_message.2)")

        key = data[offset:offset+key_length]
        if not ec_check_public_bin(key):
            raise DropPacket("Invalid cryptographic key (_decode_missing_message)")
        member = self._community.dispersy.get_member(key)
        if not member.has_identity(self._community):
            raise DelayPacketByMissingMember(self._community, member.mid)
        offset += key_length

        if len(data) < offset + 1:
            raise DropPacket("Insufficient packet size (_decode_missing_message.3)")
        message_id = data[offset]
        offset += 1
        decode_functions = self._decode_message_map.get(message_id)
        if decode_functions is None:
            raise DropPacket("Unknown sub-message id [%d]" % ord(message_id))
        message = decode_functions.meta

        if len(data) < offset + 1:
            raise DropPacket("Insufficient packet size (_decode_missing_message.4)")
        count = ord(data[offset])
        offset += 1

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, member, message, count)

    def _encode_signature_request(self, message):
        return (self._struct_H.pack(message.payload.identifier), self.encode_message(message.payload.message))

    def _decode_signature_request(self, placeholder, offset, data):
        if len(data) < offset + 2:
            raise DropPacket("Insufficient packet size (_decode_signature_request)")

        identifier, = self._struct_H.unpack_from(data, offset)
        offset += 2

        message = self._decode_message(placeholder.candidate, data[offset:], False)
        offset = len(data)

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, identifier, message)

    def _encode_signature_response(self, message):
        return (self._struct_H.pack(message.payload.identifier), self.encode_message(message.payload.message))
        # return message.payload.identifier, message.payload.signature

    def _decode_signature_response(self, placeholder, offset, data):
        if len(data) < offset + 2:
            raise DropPacket("Insufficient packet size (_decode_signature_request)")

        identifier, = self._struct_H.unpack_from(data, offset)
        offset += 2

        message = self._decode_message(placeholder.candidate, data[offset:], False)
        offset = len(data)

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, identifier, message)
        # return len(data), placeholder.meta.payload.Implementation(placeholder.meta.payload, data[offset:offset+20], data[offset+20:])

    def _encode_identity(self, message):
        return ()

    def _decode_identity(self, placeholder, offset, data):
        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload)

    def _encode_missing_identity(self, message):
        return (message.payload.mid,)

    def _decode_missing_identity(self, placeholder, offset, data):
        if len(data) < offset + 20:
            raise DropPacket("Insufficient packet size")

        return offset + 20, placeholder.meta.payload.Implementation(placeholder.meta.payload, data[offset:offset+20])

    def _encode_destroy_community(self, message):
        if message.payload.is_soft_kill:
            return ("s",)
        else:
            return ("h",)

    def _decode_destroy_community(self, placeholder, offset, data):
        if len(data) < offset + 1:
            raise DropPacket("Insufficient packet size")

        if data[offset] == "s":
            degree = u"soft-kill"
        else:
            degree = u"hard-kill"
        offset += 1

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, degree)

    def _encode_authorize(self, message):
        """
        Encode the permissiong_triplets (Member, Message, permission) into an on-the-wire string.

        On-the-wire format:
        [ repeat for each Member
           2 byte member public key length
           n byte member public key
           1 byte length
           [ once for each number in previous byte
              1 byte message id
              1 byte permission bits
           ]
        ]
        """
        permission_map = {u"permit":int("0001", 2), u"authorize":int("0010", 2), u"revoke":int("0100", 2), u"undo":int("1000", 2)}
        members = {}
        for member, message, permission in message.payload.permission_triplets:
            public_key = member.public_key
            assert isinstance(public_key, str)
            assert message.name in self._encode_message_map
            message_id = self._encode_message_map[message.name].byte
            assert isinstance(message_id, str)
            assert len(message_id) == 1
            assert permission in permission_map
            permission_bit = permission_map[permission]

            if not public_key in members:
                members[public_key] = {}

            if not message_id in members[public_key]:
                members[public_key][message_id] = 0

            members[public_key][message_id] |= permission_bit

        data = []
        for public_key, messages in members.iteritems():
            data.extend((self._struct_H.pack(len(public_key)), public_key, self._struct_B.pack(len(messages))))
            for message_id, permission_bits in messages.iteritems():
                data.extend((message_id, self._struct_B.pack(permission_bits)))

        return tuple(data)

    def _decode_authorize(self, placeholder, offset, data):
        permission_map = {u"permit":int("0001", 2), u"authorize":int("0010", 2), u"revoke":int("0100", 2), u"undo":int("1000", 2)}
        permission_triplets = []

        while offset < len(data):
            if len(data) < offset + 2:
                raise DropPacket("Insufficient packet size")

            key_length, = self._struct_H.unpack_from(data, offset)
            offset += 2

            if len(data) < offset + key_length + 1:
                raise DropPacket("Insufficient packet size")

            key = data[offset:offset+key_length]
            if not ec_check_public_bin(key):
                raise DropPacket("Invalid cryptographic key (_decode_authorize)")
            member = self._community.dispersy.get_member(key)
            if not member.has_identity(self._community):
                raise DelayPacketByMissingMember(self._community, member.mid)
            offset += key_length

            messages_length, = self._struct_B.unpack_from(data, offset)
            offset += 1

            if len(data) < offset + messages_length * 2:
                raise DropPacket("Insufficient packet size")

            for _ in xrange(messages_length):
                message_id = data[offset]
                offset += 1
                decode_functions = self._decode_message_map.get(message_id)
                if decode_functions is None:
                    raise DropPacket("Unknown sub-message id [%d]" % ord(message_id))
                message = decode_functions.meta

                if not isinstance(message.resolution, (PublicResolution, LinearResolution, DynamicResolution)):
                    raise DropPacket("Invalid resolution policy")

                if not isinstance(message.authentication, (MemberAuthentication, MultiMemberAuthentication)):
                    # it makes no sence to authorize a message that does not use the
                    # MemberAuthentication or MultiMemberAuthentication policy because without this
                    # policy it is impossible to verify WHO created the message.
                    raise DropPacket("Invalid authentication policy")

                permission_bits, = self._struct_B.unpack_from(data, offset)
                offset += 1

                for permission, permission_bit in permission_map.iteritems():
                    if permission_bit & permission_bits:
                        permission_triplets.append((member, message, permission))

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, permission_triplets)

    def _encode_revoke(self, message):
        """
        Encode the permissiong_triplets (Member, Message, permission) into an on-the-wire string.

        On-the-wire format:
        [ repeat for each Member
           2 byte member public key length
           n byte member public key
           1 byte length
           [ once for each number in previous byte
              1 byte message id
              1 byte permission bits
           ]
        ]
        """
        permission_map = {u"permit":int("0001", 2), u"authorize":int("0010", 2), u"revoke":int("0100", 2), u"undo":int("1000", 2)}
        members = {}
        for member, message, permission in message.payload.permission_triplets:
            public_key = member.public_key
            assert isinstance(public_key, str)
            assert message.name in self._encode_message_map
            message_id = self._encode_message_map[message.name].byte
            assert isinstance(message_id, str)
            assert len(message_id) == 1
            assert permission in permission_map
            permission_bit = permission_map[permission]

            if not public_key in members:
                members[public_key] = {}

            if not message_id in members[public_key]:
                members[public_key][message_id] = 0

            members[public_key][message_id] |= permission_bit

        data = []
        for public_key, messages in members.iteritems():
            data.extend((self._struct_H.pack(len(public_key)), public_key, self._struct_B.pack(len(messages))))
            for message_id, permission_bits in messages.iteritems():
                data.extend((message_id, self._struct_B.pack(permission_bits)))

        return tuple(data)

    def _decode_revoke(self, placeholder, offset, data):
        permission_map = {u"permit":int("0001", 2), u"authorize":int("0010", 2), u"revoke":int("0100", 2), u"undo":int("1000", 2)}
        permission_triplets = []

        while offset < len(data):
            if len(data) < offset + 2:
                raise DropPacket("Insufficient packet size")

            key_length, = self._struct_H.unpack_from(data, offset)
            offset += 2

            if len(data) < offset + key_length + 1:
                raise DropPacket("Insufficient packet size")

            key = data[offset:offset+key_length]
            if not ec_check_public_bin(key):
                raise DropPacket("Invalid cryptographic key (_decode_revoke)")
            member = self._community.dispersy.get_member(key)
            if not member.has_identity(self._community):
                raise DelayPacketByMissingMember(self._community, member.mid)
            offset += key_length

            messages_length, = self._struct_B.unpack_from(data, offset)
            offset += 1

            if len(data) < offset + messages_length * 2:
                raise DropPacket("Insufficient packet size")

            for _ in xrange(messages_length):
                message_id = data[offset]
                offset += 1
                decode_functions = self._decode_message_map.get(message_id)
                if decode_functions is None:
                    raise DropPacket("Unknown message id [%d]" % ord(message_id))
                message = decode_functions.meta

                if not isinstance(message.resolution, LinearResolution):
                    # it makes no sence to authorize a message that does not use the
                    # LinearResolution policy.  currently we have two policies, PublicResolution
                    # (where all messages are allowed regardless of authorization) and
                    # LinearResolution.
                    raise DropPacket("Invalid resolution policy")

                if not isinstance(message.authentication, MemberAuthentication):
                    # it makes no sence to authorize a message that does not use the
                    # MemberAuthentication policy because without this policy it is impossible to
                    # verify WHO created the message.
                    raise DropPacket("Invalid authentication policy")

                permission_bits, = self._struct_B.unpack_from(data, offset)
                offset += 1

                for permission, permission_bit in permission_map.iteritems():
                    if permission_bit & permission_bits:
                        permission_triplets.append((member, message, permission))

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, permission_triplets)

    def _encode_subjective_set(self, message):
        payload = message.payload
        assert payload.subjective_set.size % 8 == 0
        assert 0 < payload.subjective_set.functions < 256, "assuming that we choose BITS to ensure the bloom filter will fit in one MTU, it is unlikely that there will be more than 255 functions.  hence we can encode this in one byte"
        assert len(payload.subjective_set.prefix) == 0, "Should not have a prefix"
        assert len(payload.subjective_set.bytes) == int(ceil(payload.subjective_set.size / 8))
        return (self._struct_BBH.pack(payload.cluster, payload.subjective_set.functions, payload.subjective_set.size), payload.subjective_set.bytes)

    def _decode_subjective_set(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")

        cluster, functions, size = self._struct_BBH.unpack_from(data, offset)
        offset += 4
        if not 0 < functions:
            raise DropPacket("Invalid functions value")
        if not 0 < size:
            raise DropPacket("Invalid size value")
        if not size % 8 == 0:
            raise DropPacket("Invalid size value, must be a multiple of eight")
        length = int(ceil(size / 8))
        if not length == len(data) - offset:
            raise DropPacket("Invalid number of bytes available")

        subjective_set = BloomFilter(data[offset:offset + length], functions)
        offset += length

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, cluster, subjective_set)

    def _encode_missing_subjective_set(self, message):
        return (self._struct_B.pack(message.payload.cluster),) + tuple([member.mid for member in message.payload.members])

    def _decode_missing_subjective_set(self, placeholder, offset, data):
        if len(data) < offset + 21:
            raise DropPacket("Insufficient packet size")

        cluster, = self._struct_B.unpack_from(data, offset)
        offset += 1

        # check that the cluster is valid, i.e. that there is a message with a SubjectiveDestination
        # policy and this cluster value
        if not cluster in placeholder.meta.community.subjective_set_clusters:
            raise DropPacket("Invalid subjective-set cluster value")

        members = []
        while len(data) >= offset + 20:
            members.extend(member for member in self._community.dispersy.get_members_from_id(data[offset:offset+20]) if member.has_identity(self._community))
            offset += 20

        if not members:
            raise DropPacket("Invalid subjective-set-request: no members given")

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, cluster, members)

    def _encode_undo_own(self, message):
        return (self._struct_Q.pack(message.payload.global_time),)

    def _decode_undo_own(self, placeholder, offset, data):
        # use the member in the Authentication policy
        member = placeholder.authentication.member

        if len(data) < offset + 8:
            raise DropPacket("Insufficient packet size")

        global_time, = self._struct_Q.unpack_from(data, offset)
        offset += 8

        if not global_time < placeholder.distribution.global_time:
            raise DropPacket("Invalid global time (trying to apply undo to the future)")

        try:
            packet_id, message_name, packet_data = self._dispersy_database.execute(u"SELECT sync.id, meta_message.name, sync.packet FROM sync JOIN meta_message ON meta_message.id = sync.meta_message WHERE sync.community = ? AND sync.member = ? AND sync.global_time = ?",
                                                                                   (self._community.database_id, member.database_id, global_time)).next()
        except StopIteration:
            raise DelayPacketByMissingMessage(self._community, member, [global_time])

        packet = Packet(self._community.get_meta_message(message_name), str(packet_data), packet_id)

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, member, global_time, packet)

    def _encode_undo_other(self, message):
        public_key = message.payload.member.public_key
        assert message.payload.member.public_key
        return (self._struct_H.pack(len(public_key)), public_key, self._struct_Q.pack(message.payload.global_time))

    def _decode_undo_other(self, placeholder, offset, data):
        if len(data) < offset + 2:
            raise DropPacket("Insufficient packet size")

        key_length, = self._struct_H.unpack_from(data, offset)
        offset += 2

        if len(data) < offset + key_length:
            raise DropPacket("Insufficient packet size")

        public_key = data[offset:offset+key_length]
        if not ec_check_public_bin(public_key):
            raise DropPacket("Invalid cryptographic key (_decode_revoke)")
        member = self._community.dispersy.get_member(public_key)
        if not member.has_identity(self._community):
            raise DelayPacketByMissingMember(self._community, member.mid)
        offset += key_length

        if len(data) < offset + 8:
            raise DropPacket("Insufficient packet size")

        global_time, = self._struct_Q.unpack_from(data, offset)
        offset += 8

        if not global_time < placeholder.distribution.global_time:
            raise DropPacket("Invalid global time (trying to apply undo to the future)")

        try:
            packet_id, message_name, packet_data = self._dispersy_database.execute(u"SELECT sync.id, meta_message.name, sync.packet FROM sync JOIN meta_message ON meta_message.id = sync.meta_message WHERE sync.community = ? AND sync.member = ? AND sync.global_time = ?",
                                                                                   (self._community.database_id, member.database_id, global_time)).next()
        except StopIteration:
            raise DelayPacketByMissingMessage(self._community, member, [global_time])

        packet = Packet(self._community.get_meta_message(message_name), str(packet_data), packet_id)

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, member, global_time, packet)

    def _encode_missing_proof(self, message):
        payload = message.payload
        return (self._struct_QH.pack(payload.global_time, len(payload.member.public_key)), payload.member.public_key)

    def _decode_missing_proof(self, placeholder, offset, data):
        if len(data) < offset + 10:
            raise DropPacket("Insufficient packet size (_decode_missing_proof)")

        global_time, key_length = self._struct_QH.unpack_from(data, offset)
        offset += 10

        key = data[offset:offset+key_length]
        if not ec_check_public_bin(key):
            raise DropPacket("Invalid cryptographic key (_decode_missing_proof)")
        member = self._community.dispersy.get_member(key)
        if not member.has_identity(self._community):
            raise DelayPacketByMissingMember(self._community, member.mid)
        offset += key_length

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, member, global_time)

    def _encode_dynamic_settings(self, message):
        data = []
        for meta, policy in message.payload.policies:
            assert meta.name in self._encode_message_map, ("unknown message", meta.name)
            assert isinstance(policy, (PublicResolution, LinearResolution))
            assert isinstance(meta.resolution, DynamicResolution)
            assert policy in meta.resolution.policies, "the given policy must be one available at meta message creation"
            meta_id = self._encode_message_map[meta.name].byte
            # currently only supporting resolution policy changes
            policy_type = "r"
            policy_index = meta.resolution.policies.index(policy)
            data.append(self._struct_ccB.pack(meta_id, policy_type, policy_index))
        return data

    def _decode_dynamic_settings(self, placeholder, offset, data):
        if len(data) < offset + 3:
            raise DropPacket("Insufficient packet size (_decode_dynamic_settings)")

        policies = []
        while len(data) >= offset + 3:
            meta_id, policy_type, policy_index = self._struct_ccB.unpack_from(data, offset)
            decode_functions = self._decode_message_map.get(meta_id)
            if decode_functions is None:
                raise DropPacket("Unknown meta id [%d]" % ord(meta_id))
            meta = decode_functions.meta
            if not isinstance(meta.resolution, DynamicResolution):
                raise DropPacket("Invalid meta id [%d]" % ord(meta_id))

            # currently only supporting resolution policy changes
            if not policy_type == "r":
                raise DropPacket("Invalid policy type")
            if not policy_index < len(meta.resolution.policies):
                raise DropPacket("Invalid policy id")
            policy = meta.resolution.policies[policy_index]

            offset += 3

            policies.append((meta, policy))

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, policies)

    def _encode_introduction_request(self, message):
        payload = message.payload

        data = [inet_aton(payload.destination_address[0]), self._struct_H.pack(payload.destination_address[1]),
                inet_aton(payload.source_lan_address[0]), self._struct_H.pack(payload.source_lan_address[1]),
                inet_aton(payload.source_wan_address[0]), self._struct_H.pack(payload.source_wan_address[1]),
                self._struct_B.pack(self._encode_advice_map[payload.advice] | self._encode_connection_type_map[payload.connection_type] | self._encode_sync_map[payload.sync]),
                self._struct_H.pack(payload.identifier)]

        # add optional sync
        if payload.sync:
            assert payload.bloom_filter.size % 8 == 0
            assert 0 < payload.bloom_filter.functions < 256, "assuming that we choose BITS to ensure the bloom filter will fit in one MTU, it is unlikely that there will be more than 255 functions.  hence we can encode this in one byte"
            assert len(payload.bloom_filter.prefix) == 1, "must have a one character prefix"
            assert len(payload.bloom_filter.bytes) == int(ceil(payload.bloom_filter.size / 8))
            data.extend((self._struct_QQHHBH.pack(payload.time_low, payload.time_high, payload.modulo, payload.offset, payload.bloom_filter.functions, payload.bloom_filter.size),
                         payload.bloom_filter.prefix, payload.bloom_filter.bytes))

        return data

    def _decode_introduction_request(self, placeholder, offset, data):
        if len(data) < offset + 21:
            raise DropPacket("Insufficient packet size")

        destination_address = (inet_ntoa(data[offset:offset+4]), self._struct_H.unpack_from(data, offset+4)[0])
        offset += 6

        source_lan_address = (inet_ntoa(data[offset:offset+4]), self._struct_H.unpack_from(data, offset+4)[0])
        offset += 6

        source_wan_address = (inet_ntoa(data[offset:offset+4]), self._struct_H.unpack_from(data, offset+4)[0])
        offset += 6

        flags, identifier = self._struct_BH.unpack_from(data, offset)
        offset += 3

        advice = self._decode_advice_map.get(flags & int("1", 2))
        if advice is None:
            raise DropPacket("Invalid advice flag")

        connection_type = self._decode_connection_type_map.get(flags & int("11000000", 2))
        if connection_type is None:
            raise DropPacket("Invalid connection type flag")

        sync = self._decode_sync_map.get(flags & int("10", 2))
        if sync is None:
            raise DropPacket("Invalid sync flag")
        if sync:
            if len(data) < offset + 24:
                raise DropPacket("Insufficient packet size")

            time_low, time_high, modulo, modulo_offset, functions, size = self._struct_QQHHBH.unpack_from(data, offset)
            offset += 23

            prefix = data[offset]
            offset += 1

            if not time_low > 0:
                raise DropPacket("Invalid time_low value")
            if not (time_high == 0 or time_low <= time_high):
                raise DropPacket("Invalid time_high value")
            if not 0 < modulo:
                raise DropPacket("Invalid modulo value")
            if not 0 <= modulo_offset < modulo:
                raise DropPacket("Invalid offset value")
            if not 0 < functions:
                raise DropPacket("Invalid functions value")
            if not 0 < size:
                raise DropPacket("Invalid size value")
            if not size % 8 == 0:
                raise DropPacket("Invalid size value, must be a multiple of eight")

            length = int(ceil(size / 8))
            if not length == len(data) - offset:
                raise DropPacket("Invalid number of bytes available")

            bloom_filter = BloomFilter(data[offset:offset + length], functions, prefix=prefix)
            offset += length

            sync = (time_low, time_high, modulo, modulo_offset, bloom_filter)

        else:
            sync = None

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, destination_address, source_lan_address, source_wan_address, advice, connection_type, sync, identifier)

    def _encode_introduction_response(self, message):
        payload = message.payload
        return (inet_aton(payload.destination_address[0]), self._struct_H.pack(payload.destination_address[1]),
                inet_aton(payload.source_lan_address[0]), self._struct_H.pack(payload.source_lan_address[1]),
                inet_aton(payload.source_wan_address[0]), self._struct_H.pack(payload.source_wan_address[1]),
                inet_aton(payload.lan_introduction_address[0]), self._struct_H.pack(payload.lan_introduction_address[1]),
                inet_aton(payload.wan_introduction_address[0]), self._struct_H.pack(payload.wan_introduction_address[1]),
                self._struct_B.pack(self._encode_connection_type_map[payload.connection_type] | self._encode_tunnel_map[payload.tunnel]),
                self._struct_H.pack(payload.identifier))

    def _decode_introduction_response(self, placeholder, offset, data):
        if len(data) < offset + 33:
            raise DropPacket("Insufficient packet size")

        destination_address = (inet_ntoa(data[offset:offset+4]), self._struct_H.unpack_from(data, offset+4)[0])
        offset += 6

        source_lan_address = (inet_ntoa(data[offset:offset+4]), self._struct_H.unpack_from(data, offset+4)[0])
        offset += 6

        source_wan_address = (inet_ntoa(data[offset:offset+4]), self._struct_H.unpack_from(data, offset+4)[0])
        offset += 6

        lan_introduction_address = (inet_ntoa(data[offset:offset+4]), self._struct_H.unpack_from(data, offset+4)[0])
        offset += 6

        wan_introduction_address = (inet_ntoa(data[offset:offset+4]), self._struct_H.unpack_from(data, offset+4)[0])
        offset += 6

        flags, identifier, = self._struct_BH.unpack_from(data, offset)
        offset += 3

        connection_type = self._decode_connection_type_map.get(flags & int("1110", 2))
        if connection_type is None:
            raise DropPacket("Invalid connection type flag")

        tunnel = self._decode_tunnel_map.get(flags & int("100", 2))
        if tunnel is None:
            raise DropPacket("Invalid tunnel flag")

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, destination_address, source_lan_address, source_wan_address, lan_introduction_address, wan_introduction_address, connection_type, tunnel, identifier)

    def _encode_puncture_request(self, message):
        payload = message.payload
        return (inet_aton(payload.lan_walker_address[0]), self._struct_H.pack(payload.lan_walker_address[1]),
                inet_aton(payload.wan_walker_address[0]), self._struct_H.pack(payload.wan_walker_address[1]),
                self._struct_H.pack(payload.identifier))

    def _decode_puncture_request(self, placeholder, offset, data):
        if len(data) < offset + 14:
            raise DropPacket("Insufficient packet size")

        lan_walker_address = (inet_ntoa(data[offset:offset+4]), self._struct_H.unpack_from(data, offset+4)[0])
        offset += 6

        wan_walker_address = (inet_ntoa(data[offset:offset+4]), self._struct_H.unpack_from(data, offset+4)[0])
        offset += 6

        identifier, = self._struct_H.unpack_from(data, offset)
        offset += 2

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, lan_walker_address, wan_walker_address, identifier)

    def _encode_puncture(self, message):
        payload = message.payload
        return (inet_aton(payload.source_lan_address[0]), self._struct_H.pack(payload.source_lan_address[1]),
                inet_aton(payload.source_wan_address[0]), self._struct_H.pack(payload.source_wan_address[1]),
                self._struct_H.pack(payload.identifier))

    def _decode_puncture(self, placeholder, offset, data):
        if len(data) < offset + 14:
            raise DropPacket("Insufficient packet size")

        source_lan_address = (inet_ntoa(data[offset:offset+4]), self._struct_H.unpack_from(data, offset+4)[0])
        offset += 6

        source_wan_address = (inet_ntoa(data[offset:offset+4]), self._struct_H.unpack_from(data, offset+4)[0])
        offset += 6

        identifier, = self._struct_H.unpack_from(data, offset)
        offset += 2

        return offset, placeholder.meta.payload.Implementation(placeholder.meta.payload, source_lan_address, source_wan_address, identifier)

    #
    # Encoding
    #

    def _encode_no_authentication(self, container, message):
        pass

    def _encode_member_authentication(self, container, message):
        if message.authentication.encoding == "sha1":
            container.append(message.authentication.member.mid)
        elif message.authentication.encoding == "bin":
            assert message.authentication.member.public_key
            assert ec_check_public_bin(message.authentication.member.public_key), message.authentication.member.public_key.encode("HEX")
            container.extend((self._struct_H.pack(len(message.authentication.member.public_key)), message.authentication.member.public_key))
        else:
            raise NotImplementedError(message.authentication.encoding)

    def _encode_multi_member_authentication(self, container, message):
        container.extend([member.mid for member in message.authentication.members])

    def _encode_full_sync_distribution(self, container, message):
        assert message.distribution.global_time
        # 23/04/12 Boudewijn: testcases generate global time values that have not been claimed
        # if message.distribution.global_time > message.community.global_time:
        #     # did not use community.claim_global_time() FAIL
        #     raise ValueError("incorrect global_time value chosen")
        if message.distribution.enable_sequence_number:
            assert message.distribution.sequence_number
            container.append(self._struct_QL.pack(message.distribution.global_time, message.distribution.sequence_number))
        else:
            container.append(self._struct_Q.pack(message.distribution.global_time))

    def _encode_last_sync_distribution(self, container, message):
        assert message.distribution.global_time
        # 23/04/12 Boudewijn: testcases generate global time values that have not been claimed
        # if message.distribution.global_time > message.community.global_time:
        #     # did not use community.claim_global_time() FAIL
        #     raise ValueError("incorrect global_time value chosen")
        container.append(self._struct_Q.pack(message.distribution.global_time))

    def _encode_direct_distribution(self, container, message):
        assert message.distribution.global_time
        # 23/04/12 Boudewijn: testcases generate global time values that have not been claimed
        # if message.distribution.global_time > message.community.global_time:
        #     # did not use community.claim_global_time() FAIL
        #     raise ValueError("incorrect global_time value chosen")
        container.append(self._struct_Q.pack(message.distribution.global_time))

    def _encode_public_resolution(self, container, message):
        pass

    def _encode_linear_resolution(self, container, message):
        pass

    def _encode_dynamic_resolution(self, container, message):
        assert isinstance(message.resolution.policy, (PublicResolution.Implementation, LinearResolution.Implementation)), message.resolution.policy
        assert not isinstance(message.resolution.policy, DynamicResolution), message.resolution.policy
        index = message.resolution.policies.index(message.resolution.policy.meta)
        container.append(chr(index))
        # both the public and the linear resolution do not require any storage

    def _encode_no_authentication_signature(self, container, message):
        return "".join(container)

    def _encode_member_authentication_signature(self, container, message):
        assert message.authentication.member.private_key, (message.authentication.member.database_id, message.authentication.member.mid.encode("HEX"), id(message.authentication.member))
        data = "".join(container)
        signature = message.authentication.member.sign(data)
        message.authentication.set_signature(signature)
        return data + signature

    def _encode_multi_member_authentication_signature(self, container, message):
        data = "".join(container)
        signatures = []
        for signature, member in message.authentication.signed_members:
            if signature:
                signatures.append(signature)
            elif member.private_key:
                signature = member.sign(data)
                message.authentication.set_signature(member, signature)
                signatures.append(signature)
            else:
                signatures.append("\x00" * member.signature_length)
        return data + "".join(signatures)

    def encode_message(self, message):
        assert isinstance(message, Message.Implementation), message
        assert message.name in self._encode_message_map, message.name
        encode_functions = self._encode_message_map[message.name]

        # community prefix, message-id
        container = [self._prefix, encode_functions.byte]

        # authentication
        encode_functions.authentication(container, message)

        # resolution
        encode_functions.resolution(container, message)

        # distribution
        encode_functions.distribution(container, message)

        # payload
        payload = encode_functions.payload(message)
        assert isinstance(payload, (tuple, list)), (type(payload), encode_functions.payload)
        assert all(isinstance(x, str) for x in payload)
        container.extend(payload)

        # sign
        packet = encode_functions.signature(container, message)

        if __debug__:
            if len(packet) > 1500 - 60 - 8:
                dprint("Packet size for ", message.name, " exceeds MTU - IP header - UDP header (", len(packet), " bytes)", level="warning")

        # dprint(message.packet.encode("HEX"))
        return packet

    #
    # Decoding
    #

    def _decode_full_sync_distribution(self, placeholder):
        distribution = placeholder.meta.distribution
        if distribution.enable_sequence_number:
            global_time, sequence_number = self._struct_QL.unpack_from(placeholder.data, placeholder.offset)
            if not global_time:
                raise DropPacket("Invalid global time value (_decode_full_sync_distribution)")
            if not sequence_number:
                raise DropPacket("Invalid sequence number value (_decode_full_sync_distribution)")
            placeholder.offset += 12
            placeholder.distribution = distribution.Implementation(distribution, global_time, sequence_number)

        else:
            global_time, = self._struct_Q.unpack_from(placeholder.data, placeholder.offset)
            if not global_time:
                raise DropPacket("Invalid global time value (_decode_full_sync_distribution)")
            placeholder.offset += 8
            placeholder.distribution = distribution.Implementation(distribution, global_time)

    def _decode_last_sync_distribution(self, placeholder):
        global_time, = self._struct_Q.unpack_from(placeholder.data, placeholder.offset)
        if not global_time:
            raise DropPacket("Invalid global time value (_decode_last_sync_distribution)")
        placeholder.offset += 8
        placeholder.distribution = LastSyncDistribution.Implementation(placeholder.meta.distribution, global_time)

    def _decode_direct_distribution(self, placeholder):
        global_time, = self._struct_Q.unpack_from(placeholder.data, placeholder.offset)
        placeholder.offset += 8
        placeholder.distribution = DirectDistribution.Implementation(placeholder.meta.distribution, global_time)

    def _decode_public_resolution(self, placeholder):
        placeholder.resolution = PublicResolution.Implementation(placeholder.meta.resolution)

    def _decode_linear_resolution(self, placeholder):
        placeholder.resolution = LinearResolution.Implementation(placeholder.meta.resolution)

    def _decode_dynamic_resolution(self, placeholder):
        if len(placeholder.data) < placeholder.offset + 1:
            raise DropPacket("Insufficient packet size (_decode_dynamic_resolution)")

        index = ord(placeholder.data[placeholder.offset])
        if index > len(placeholder.meta.resolution.policies):
            raise DropPacket("Invalid policy index")
        meta_policy = placeholder.meta.resolution.policies[index]
        placeholder.offset += 1

        assert isinstance(meta_policy, (PublicResolution, LinearResolution)), meta_policy
        assert not isinstance(meta_policy, DynamicResolution), meta_policy
        # both the public and the linear resolution do not require any storage
        policy = meta_policy.Implementation(meta_policy)

        placeholder.resolution = DynamicResolution.Implementation(placeholder.meta.resolution, policy)

    def _decode_no_authentication(self, placeholder):
        placeholder.first_signature_offset = len(placeholder.data)
        placeholder.authentication = NoAuthentication.Implementation(placeholder.meta.authentication)

    def _decode_member_authentication(self, placeholder):
        authentication = placeholder.meta.authentication
        offset = placeholder.offset
        data = placeholder.data

        if authentication.encoding == "sha1":
            if len(data) < offset + 20:
                raise DropPacket("Insufficient packet size (_decode_member_authentication sha1)")
            member_id = data[offset:offset+20]
            offset += 20

            members = [member for member in self._community.dispersy.get_members_from_id(member_id) if member.has_identity(self._community)]
            if not members:
                raise DelayPacketByMissingMember(self._community, member_id)

            # signatures are enabled, verify that the signature matches the member sha1
            # identifier
            for member in members:
                first_signature_offset = len(data) - member.signature_length
                if member.verify(data, data[first_signature_offset:], length=first_signature_offset):
                    placeholder.offset = offset
                    placeholder.first_signature_offset = first_signature_offset
                    placeholder.authentication = MemberAuthentication.Implementation(authentication, member, is_signed=True)
                    return

            raise DelayPacketByMissingMember(self._community, member_id)

        elif authentication.encoding == "bin":
            key_length, = self._struct_H.unpack_from(data, offset)
            offset += 2
            if len(data) < offset + key_length:
                raise DropPacket("Insufficient packet size (_decode_authentication bin)")
            key = data[offset:offset+key_length]
            offset += key_length

            if not ec_check_public_bin(key):
                raise DropPacket("Invalid cryptographic key (_decode_authentication)")

            member = self._community.dispersy.get_member(key)

            # TODO we should ensure that member.has_identity(self._community), however, the
            # exception is the dispersy-identity message.  hence we need the placeholder
            # parameter to check this
            first_signature_offset = len(data) - member.signature_length

            # signatures are enabled, verify that the signature matches the member sha1
            # identifier
            if member.verify(data, data[first_signature_offset:], length=first_signature_offset):
                placeholder.offset = offset
                placeholder.first_signature_offset = first_signature_offset
                placeholder.authentication = MemberAuthentication.Implementation(authentication, member, is_signed=True)
                return

            raise DropPacket("Invalid signature")

        else:
            raise NotImplementedError(authentication.encoding)

    def _decode_multi_member_authentication(self, placeholder):
        def iter_options(members_ids):
            """
            members_ids = [[m1_a, m1_b], [m2_a], [m3_a, m3_b]]
            --> m1_a, m2_a, m3_a
            --> m1_a, m2_a, m3_b
            --> m1_b, m2_a, m3_a
            --> m1_b, m2_a, m3_b
            """
            if members_ids:
                for member_id in members_ids[0]:
                    for others in iter_options(members_ids[1:]):
                        yield [member_id] + others
            else:
                yield []

        authentication = placeholder.meta.authentication
        offset = placeholder.offset
        data = placeholder.data
        members_ids = []

        for _ in range(authentication.count):
            member_id = data[offset:offset+20]
            members = [member for member in self._community.dispersy.get_members_from_id(member_id) if member.has_identity(self._community)]
            if not members:
                raise DelayPacketByMissingMember(self._community, member_id)
            offset += 20
            members_ids.append(members)

        for members in iter_options(members_ids):
            # try this member combination
            first_signature_offset = len(data) - sum([member.signature_length for member in members])
            signature_offset = first_signature_offset
            signatures = [""] * authentication.count
            valid_or_null = True
            for index, member in zip(range(authentication.count), members):
                signature = data[signature_offset:signature_offset+member.signature_length]
                # dprint("INDEX: ", index, force=1)
                # dprint(signature.encode('HEX'), force=1)
                if not signature == "\x00" * member.signature_length:
                    if member.verify(data, data[signature_offset:signature_offset+member.signature_length], length=first_signature_offset):
                        signatures[index] = signature
                    else:
                        valid_or_null = False
                        break
                signature_offset += member.signature_length

            # found a valid combination
            if valid_or_null:
                placeholder.offset = offset
                placeholder.first_signature_offset = first_signature_offset
                placeholder.authentication = MultiMemberAuthentication.Implementation(placeholder.meta.authentication, members, signatures=signatures)
                return

        raise DelayPacketByMissingMember(self._community, member_id)

    def _decode_empty_destination(self, placeholder):
        placeholder.destination = placeholder.meta.destination.Implementation(placeholder.meta.destination)

    def _decode_subjective_destination(self, placeholder):
        meta = placeholder.meta
        # we want to know if the sender occurs in our subjective bloom filter
        subjective_set = self._community.get_subjective_set(self._community.my_member, meta.destination.cluster)
        assert subjective_set, "We must always have subjective sets for ourself"
        placeholder.destination = meta.destination.Implementation(meta.destination, placeholder.authentication.member.public_key in subjective_set)

    def _decode_message(self, candidate, data, verify_all_signatures):
        """
        Decode a binary string into a Message structure, with some
        Dispersy specific parameters.

        When VERIFY_ALL_SIGNATURES is True, all signatures must be valid.  When
        VERIFY_ALL_SIGNATURES is False, signatures must be either valid or \x00 bytes.
        Message.authentication.signed_members returns information on which members had a signature
        present.
        """
        assert isinstance(data, str)
        assert isinstance(verify_all_signatures, bool)
        assert len(data) >= 22
        assert data[:22] == self._prefix, (data[:22].encode("HEX"), self._prefix.encode("HEX"))

        if len(data) < 100:
            DropPacket("Packet is to small to decode")

        # meta_message
        decode_functions = self._decode_message_map.get(data[22])
        if decode_functions is None:
            raise DropPacket("Unknown message code %d" % ord(data[22]))

        # placeholder
        placeholder = self.Placeholder(candidate, decode_functions.meta, 23, data)

        # authentication
        decode_functions.authentication(placeholder)
        assert isinstance(placeholder.authentication, Authentication.Implementation)
        if verify_all_signatures and not placeholder.authentication.is_signed:
            raise DropPacket("Invalid signature")
        # drop packet if the creator is blacklisted.  we would prefer to do this in dispersy.py,
        # however, decoding the payload can cause DelayPacketByMissingMessage to be raised for
        # dispersy-undo messages, and the last thing that we want is to request messages from a
        # blacklisted member
        if isinstance(placeholder.meta.authentication, (MemberAuthentication, MultiMemberAuthentication)) and placeholder.authentication.member.must_blacklist:
            self._community.dispersy.send_malicious_proof(self._community, placeholder.authentication.member, candidate)
            raise DropPacket("Creator is blacklisted")

        # resolution
        decode_functions.resolution(placeholder)
        assert isinstance(placeholder.resolution, Resolution.Implementation)

        # destination
        decode_functions.destination(placeholder)
        assert isinstance(placeholder.destination, Destination.Implementation)

        # distribution
        decode_functions.distribution(placeholder)
        assert isinstance(placeholder.distribution, Distribution.Implementation)

        # payload
        placeholder.offset, placeholder.payload = decode_functions.payload(placeholder, placeholder.offset, placeholder.data[:placeholder.first_signature_offset])
        if placeholder.offset != placeholder.first_signature_offset:
            if __debug__: dprint("invalid packet size for ", placeholder.meta.name, " data:", placeholder.first_signature_offset, "; offset:", placeholder.offset, level="warning")
            raise DropPacket("Invalid packet size (there are unconverted bytes)")

        if __debug__:
            from payload import Payload
            assert isinstance(placeholder.payload, Payload.Implementation), type(placeholder.payload)
            assert isinstance(placeholder.offset, (int, long))

        return placeholder.meta.Implementation(placeholder.meta, placeholder.authentication, placeholder.resolution, placeholder.distribution, placeholder.destination, placeholder.payload, conversion=self, candidate=candidate, packet=placeholder.data)

    def decode_meta_message(self, data):
        """
        Decode a binary string into a Message instance.
        """
        assert isinstance(data, str)
        assert data[:22] == self._prefix, (data[:22].encode("HEX"), self._prefix.encode("HEX"))

        if len(data) < 23:
            raise DropPacket("Packet is to small to decode")

        # meta_message
        decode_functions = self._decode_message_map.get(data[22])
        if decode_functions is None:
            raise DropPacket("Unknown message code %d" % ord(data[22]))

        return decode_functions.meta

    def decode_message(self, candidate, data):
        """
        Decode a binary string into a Message.Implementation structure.
        """
        assert isinstance(candidate, Candidate), candidate
        assert isinstance(data, str), data
        return self._decode_message(candidate, data, True)

class DefaultConversion(BinaryConversion):
    """
    This conversion class is initially used to encode some Dispersy
    specific messages during the creation of a new Community
    (authorizing the initial member).  Afterwards it is usually
    replaced by a Community specific conversion that also supplies
    payload conversion for the Community specific messages.
    """
    def __init__(self, community):
        super(DefaultConversion, self).__init__(community, "\x00")
