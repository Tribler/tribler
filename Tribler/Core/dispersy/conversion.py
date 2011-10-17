from hashlib import sha1
from math import ceil
from socket import inet_ntoa, inet_aton
from struct import pack, unpack_from

from authentication import NoAuthentication, MemberAuthentication, MultiMemberAuthentication
from bloomfilter import BloomFilter
from crypto import ec_check_public_bin
from destination import MemberDestination, CommunityDestination, AddressDestination, SubjectiveDestination
from dispersydatabase import DispersyDatabase
from distribution import FullSyncDistribution, LastSyncDistribution, DirectDistribution
from message import DelayPacketByMissingMember, DelayPacketByMissingMessage, DropPacket, Packet, Message
from resolution import PublicResolution, LinearResolution, DynamicResolution

if __debug__:
    from dprint import dprint
    from time import clock

class Placeholder(object):
    def __init__(self, offset, data):
        self.offset = offset
        self.data = data
        self.meta = None
        self.authentication = None
        self.resolution = None
        self.first_signature_offset = 0
        self.destination = None
        self.distribution = None
        self.payload = None

class Conversion(object):
    """
    A Conversion object is used to convert incoming packets to a different, possibly more recent,
    community version.  If also allows outgoing messages to be converted to a different, possibly
    older, community version.
    """
    if __debug__:
        debug_stats = {"encode-meta":0.0, "encode-authentication":0.0, "encode-destination":0.0, "encode-distribution":0.0, "encode-payload":0.0,
                       "decode-meta":0.0, "decode-authentication":0.0, "decode-destination":0.0, "decode-distribution":0.0, "decode-payload":0.0,
                       "verify-true":0.0, "verify-false":0.0, "sign":0.0}

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
    def __init__(self, community, community_version):
        Conversion.__init__(self, community, "\x00", community_version)
        self._encode_distribution_map = {FullSyncDistribution.Implementation:self._encode_full_sync_distribution,
                                         LastSyncDistribution.Implementation:self._encode_last_sync_distribution,
                                         DirectDistribution.Implementation:self._encode_direct_distribution}
        self._decode_distribution_map = {FullSyncDistribution:self._decode_full_sync_distribution,
                                         LastSyncDistribution:self._decode_last_sync_distribution,
                                         DirectDistribution:self._decode_direct_distribution}
        self._encode_resolution_map = {PublicResolution.Implementation:self._encode_public_resolution,
                                       LinearResolution.Implementation:self._encode_linear_resolution,
                                       DynamicResolution.Implementation:self._encode_dynamic_resolution}
        self._decode_resolution_map = {PublicResolution:self._decode_public_resolution,
                                       LinearResolution:self._decode_linear_resolution,
                                       DynamicResolution:self._decode_dynamic_resolution}
        self._encode_message_map = dict() # message.name : (byte, encode_payload_func)
        self._decode_message_map = dict() # byte : (message, decode_payload_func)

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

        define(254, u"dispersy-missing-sequence", self._encode_missing_sequence, self._decode_missing_sequence)
        define(252, u"dispersy-signature-request", self._encode_signature_request, self._decode_signature_request)
        define(251, u"dispersy-signature-response", self._encode_signature_response, self._decode_signature_response)
        define(248, u"dispersy-identity", self._encode_identity, self._decode_identity)
        define(247, u"dispersy-missing-identity", self._encode_missing_identity, self._decode_missing_identity)
        define(244, u"dispersy-destroy-community", self._encode_destroy_community, self._decode_destroy_community)
        define(243, u"dispersy-authorize", self._encode_authorize, self._decode_authorize)
        define(242, u"dispersy-revoke", self._encode_revoke, self._decode_revoke)
        define(241, u"dispersy-subjective-set", self._encode_subjective_set, self._decode_subjective_set)
        define(240, u"dispersy-missing-subjective-set", self._encode_missing_subjective_set, self._decode_missing_subjective_set)
        define(239, u"dispersy-missing-message", self._encode_missing_message, self._decode_missing_message)
        define(238, u"dispersy-undo", self._encode_undo, self._decode_undo)
        define(237, u"dispersy-missing-proof", self._encode_missing_proof, self._decode_missing_proof)
        define(236, u"dispersy-dynamic-settings", self._encode_dynamic_settings, self._decode_dynamic_settings)
        define(235, u"dispersy-introduction-request", self._encode_introduction_request, self._decode_introduction_request)
        define(234, u"dispersy-introduction-response", self._encode_introduction_response, self._decode_introduction_response)
        define(233, u"dispersy-puncture-request", self._encode_puncture_request, self._decode_puncture_request)
        define(232, u"dispersy-puncture", self._encode_puncture, self._decode_puncture)

        if __debug__:
            if debug_non_available:
                dprint("unable to define non-available messages ", ", ".join(debug_non_available), level="warning")

    def define_meta_message(self, byte, message, encode_payload_func, decode_payload_func):
        assert isinstance(byte, str)
        assert len(byte) == 1
        assert isinstance(message, Message)
        assert 0 < ord(byte) < 255
        assert not message.name in self._encode_message_map
        assert not byte in self._decode_message_map, "This byte has already been defined (%d)" % ord(byte)
        assert callable(encode_payload_func)
        assert callable(decode_payload_func)
        self._encode_message_map[message.name] = (byte, encode_payload_func)
        self._decode_message_map[byte] = (message, decode_payload_func)

    #
    # Dispersy payload
    #

    def _encode_missing_sequence(self, message):
        payload = message.payload
        assert payload.message.name in self._encode_message_map, payload.message.name
        message_id, _ = self._encode_message_map[payload.message.name]
        return payload.member.mid, message_id, pack("!LL", payload.missing_low, payload.missing_high)

    def _decode_missing_sequence(self, placeholder, offset, data):
        if len(data) < offset + 29:
            raise DropPacket("Insufficient packet size")

        member_id = data[offset:offset+20]
        offset += 20
        members = [member for member in self._community.get_members_from_id(member_id) if member.has_identity(self._community)]
        if not members:
            raise DelayPacketByMissingMember(self._community, member_id)
        elif len(members) > 1:
            # this is unrecoverable.  a member id without a signature is simply not globally unique.
            # This can occur when two or more nodes have the same sha1 hash.  Very unlikely.
            raise DropPacket("Unrecoverable: ambiguous member")
        member = members[0]

        missing_meta_message, _ = self._decode_message_map.get(data[offset], (None, None))
        if missing_meta_message is None:
            raise DropPacket("Invalid message")
        offset += 1

        missing_low, missing_high = unpack_from("!LL", data, offset)
        offset += 8

        return offset, placeholder.meta.payload.implement(member, missing_meta_message, missing_low, missing_high)

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
        return pack("!H", len(payload.member.public_key)), payload.member.public_key, pack("!%dQ" % len(payload.global_times), *payload.global_times)

    def _decode_missing_message(self, placeholder, offset, data):
        if len(data) < offset + 2:
            raise DropPacket("Insufficient packet size (_decode_missing_message.1)")

        key_length, = unpack_from("!H", data, offset)
        offset += 2

        if len(data) < offset + key_length + 1:
            raise DropPacket("Insufficient packet size (_decode_missing_message.2)")

        key = data[offset:offset+key_length]
        if not ec_check_public_bin(key):
            raise DropPacket("Invalid cryptographic key (_decode_missing_message)")
        member = self._community.get_member(key)
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

        return offset, placeholder.meta.payload.implement(member, global_times)

    def _encode_signature_request(self, message):
        return self.encode_message(message.payload.message),

    def _decode_signature_request(self, placeholder, offset, data):
        return len(data), placeholder.meta.payload.implement(self._decode_message(("", -1), data[offset:], False))

    def _encode_signature_response(self, message):
        return message.payload.identifier, message.payload.signature

    def _decode_signature_response(self, placeholder, offset, data):
        return len(data), placeholder.meta.payload.implement(data[offset:offset+20], data[offset+20:])

    def _encode_identity(self, message):
        return ()

    def _decode_identity(self, placeholder, offset, data):
        return offset, placeholder.meta.payload.implement()

    def _encode_missing_identity(self, message):
        return message.payload.mid,

    def _decode_missing_identity(self, placeholder, offset, data):
        if len(data) < offset + 20:
            raise DropPacket("Insufficient packet size")

        return offset + 20, placeholder.meta.payload.implement(data[offset:offset+20])

    def _encode_destroy_community(self, message):
        if message.payload.is_soft_kill:
            return "s",
        else:
            return "h",

    def _decode_destroy_community(self, placeholder, offset, data):
        if len(data) < offset + 1:
            raise DropPacket("Insufficient packet size")

        if data[offset] == "s":
            degree = u"soft-kill"
        else:
            degree = u"hard-kill"
        offset += 1

        return offset, placeholder.meta.payload.implement(degree)

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
        permission_map = {u"permit":1, u"authorize":2, u"revoke":4}
        members = {}
        for member, message, permission in message.payload.permission_triplets:
            public_key = member.public_key
            assert isinstance(public_key, str)
            assert message.name in self._encode_message_map
            message_id = self._encode_message_map[message.name][0]
            assert isinstance(message_id, str)
            assert len(message_id) == 1
            assert permission in permission_map
            permission_bit = permission_map[permission]

            if not public_key in members:
                members[public_key] = {}

            if not message_id in members[public_key]:
                members[public_key][message_id] = 0

            members[public_key][message_id] |= permission_bit

        bytes = []
        for public_key, messages in members.iteritems():
            bytes.extend((pack("!H", len(public_key)), public_key, pack("!B", len(messages))))
            for message_id, permission_bits in messages.iteritems():
                bytes.extend((message_id, pack("!B", permission_bits)))

        return tuple(bytes)

    def _decode_authorize(self, placeholder, offset, data):
        permission_map = {u"permit":1, u"authorize":2, u"revoke":4}
        permission_triplets = []

        while offset < len(data):
            if len(data) < offset + 2:
                raise DropPacket("Insufficient packet size")

            key_length, = unpack_from("!H", data, offset)
            offset += 2

            if len(data) < offset + key_length + 1:
                raise DropPacket("Insufficient packet size")

            key = data[offset:offset+key_length]
            if not ec_check_public_bin(key):
                raise DropPacket("Invalid cryptographic key (_decode_authorize)")
            member = self._community.get_member(key)
            if not member.has_identity(self._community):
                raise DelayPacketByMissingMember(self._community, member.mid)
            offset += key_length

            messages_length, = unpack_from("!B", data, offset)
            offset += 1

            if len(data) < offset + messages_length * 2:
                raise DropPacket("Insufficient packet size")

            for _ in xrange(messages_length):
                message_id = data[offset]
                offset += 1
                if not message_id in self._decode_message_map:
                    raise DropPacket("Unknown message id [%d]" % ord(message_id))
                message = self._decode_message_map[message_id][0]

                if not isinstance(message.resolution, (LinearResolution, DynamicResolution)):
                    # it makes no sence to authorize a message that does not use the
                    # LinearResolution or DynamicResolution policy.  currently we have three
                    # policies, PublicResolution (where all messages are allowed regardless of
                    # authorization), LinearResolution (where members require permissions), and
                    # DynamicResolution (where the policy changes between the other available
                    # policies).
                    raise DropPacket("Invalid resolution policy")

                if not isinstance(message.authentication, MemberAuthentication):
                    # it makes no sence to authorize a message that does not use the
                    # MemberAuthentication policy because without this policy it is impossible to
                    # verify WHO created the message.
                    raise DropPacket("Invalid authentication policy")

                permission_bits, = unpack_from("!B", data, offset)
                offset += 1

                for permission, permission_bit in permission_map.iteritems():
                    if permission_bit & permission_bits:
                        permission_triplets.append((member, message, permission))

        return offset, placeholder.meta.payload.implement(permission_triplets)

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
        permission_map = {u"permit":1, u"authorize":2, u"revoke":4}
        members = {}
        for member, message, permission in message.payload.permission_triplets:
            public_key = member.public_key
            assert isinstance(public_key, str)
            assert message.name in self._encode_message_map
            message_id = self._encode_message_map[message.name][0]
            assert isinstance(message_id, str)
            assert len(message_id) == 1
            assert permission in permission_map
            permission_bit = permission_map[permission]

            if not public_key in members:
                members[public_key] = {}

            if not message_id in members[public_key]:
                members[public_key][message_id] = 0

            members[public_key][message_id] |= permission_bit

        bytes = []
        for public_key, messages in members.iteritems():
            bytes.extend((pack("!H", len(public_key)), public_key, pack("!B", len(messages))))
            for message_id, permission_bits in messages.iteritems():
                bytes.extend((message_id, pack("!B", permission_bits)))

        return tuple(bytes)

    def _decode_revoke(self, placeholder, offset, data):
        permission_map = {u"permit":1, u"authorize":2, u"revoke":4}
        permission_triplets = []

        while offset < len(data):
            if len(data) < offset + 2:
                raise DropPacket("Insufficient packet size")

            key_length, = unpack_from("!H", data, offset)
            offset += 2

            if len(data) < offset + key_length + 1:
                raise DropPacket("Insufficient packet size")

            key = data[offset:offset+key_length]
            if not ec_check_public_bin(key):
                raise DropPacket("Invalid cryptographic key (_decode_revoke)")
            member = self._community.get_member(key)
            if not member.has_identity(self._community):
                raise DelayPacketByMissingMember(self._community, member.mid)
            offset += key_length

            messages_length, = unpack_from("!B", data, offset)
            offset += 1

            if len(data) < offset + messages_length * 2:
                raise DropPacket("Insufficient packet size")

            for _ in xrange(messages_length):
                message_id = data[offset]
                offset += 1
                if not message_id in self._decode_message_map:
                    raise DropPacket("Unknown message id [%d]" % ord(message_id))
                message = self._decode_message_map[message_id][0]

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

                permission_bits, = unpack_from("!B", data, offset)
                offset += 1

                for permission, permission_bit in permission_map.iteritems():
                    if permission_bit & permission_bits:
                        permission_triplets.append((member, message, permission))

        return offset, placeholder.meta.payload.implement(permission_triplets)

    def _encode_subjective_set(self, message):
        payload = message.payload
        assert 0 < payload.subjective_set.num_slices < 2**8, "Assuming the sync message fits within a single MTU, it is -extremely- unlikely to have more than 20 slices"
        assert 0 < payload.subjective_set.bits_per_slice < 2**16, "Assuming the sync message fits within a single MTU, it is -extremely- unlikely to have more than 30000 bits per slice"
        assert len(payload.subjective_set.prefix) == 0, "Should not have a prefix"
        return pack("!BBH", payload.cluster, payload.subjective_set.num_slices, payload.subjective_set.bits_per_slice), payload.subjective_set.prefix, payload.subjective_set.bytes

    def _decode_subjective_set(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")

        cluster, num_slices, bits_per_slice = unpack_from("!BBH", data, offset)
        offset += 4
        if not num_slices > 0:
            raise DropPacket("Invalid num_slices value")
        if not bits_per_slice > 0:
            raise DropPacket("Invalid bits_per_slice value")
        if not ceil(num_slices * bits_per_slice / 8.0) == len(data) - offset:
            raise DropPacket("Invalid number of bytes available")

        subjective_set = BloomFilter(data, num_slices, bits_per_slice, offset=offset)
        offset += num_slices * bits_per_slice

        return offset, placeholder.meta.payload.implement(cluster, subjective_set)

    def _encode_missing_subjective_set(self, message):
        return (pack("!B", message.payload.cluster),) + tuple([member.mid for member in message.payload.members])

    def _decode_missing_subjective_set(self, placeholder, offset, data):
        if len(data) < offset + 21:
            raise DropPacket("Insufficient packet size")

        cluster, = unpack_from("!B", data, offset)
        offset += 1

        # check that the cluster is valid, i.e. that there is a message with a SubjectiveDestination
        # policy and this cluster value
        if not cluster in placeholder.meta.community.subjective_set_clusters:
            raise DropPacket("Invalid subjective-set cluster value")

        members = []
        while len(data) >= offset + 20:
            members.extend(member for member in self._community.get_members_from_id(data[offset:offset+20]) if member.has_identity(self._community))
            offset += 20

        if not members:
            raise DropPacket("Invalid subjective-set-request: no members given")

        return offset, placeholder.meta.payload.implement(cluster, members)

    def _encode_undo(self, message):
        return pack("!Q", message.payload.global_time),

    def _decode_undo(self, placeholder, offset, data):
        if len(data) < offset + 8:
            raise DropPacket("Insufficient packet size")

        global_time, = unpack_from("!Q", data, offset)
        offset += 8

        if not global_time < placeholder.distribution.global_time:
            raise DropPacket("Invalid global time (trying to apply undo to the future)")

        try:
            packet_id, message_name, packet_data = self._dispersy_database.execute(u"SELECT sync.id, meta_message.name, sync.packet FROM sync JOIN meta_message ON meta_message.id = sync.meta_message WHERE sync.community = ? AND sync.member = ? AND sync.global_time = ?",
                                                                                   (self._community.database_id, placeholder.authentication.member.database_id, global_time)).next()
        except StopIteration:
            raise DelayPacketByMissingMessage(self._community, placeholder.authentication.member, [global_time])

        packet = Packet(self._community.get_meta_message(message_name), str(packet_data), packet_id)

        return offset, placeholder.meta.payload.implement(placeholder.authentication.member, global_time, packet)

    def _encode_missing_proof(self, message):
        payload = message.payload
        return pack("!QH", payload.global_time, len(payload.member.public_key)), payload.member.public_key

    def _decode_missing_proof(self, placeholder, offset, data):
        if len(data) < offset + 10:
            raise DropPacket("Insufficient packet size (_decode_missing_proof)")

        global_time, key_length = unpack_from("!QH", data, offset)
        offset += 10

        key = data[offset:offset+key_length]
        if not ec_check_public_bin(key):
            raise DropPacket("Invalid cryptographic key (_decode_missing_proof)")
        member = self._community.get_member(key)
        if not member.has_identity(self._community):
            raise DelayPacketByMissingMember(self._community, member.mid)
        offset += key_length

        return offset, placeholder.meta.payload.implement(member, global_time)

    def _encode_dynamic_settings(self, message):
        data = []
        for meta, policy in message.payload.policies:
            assert meta.name in self._encode_message_map, ("unknown message", meta.name)
            assert isinstance(policy, (PublicResolution, LinearResolution))
            assert isinstance(meta.resolution, DynamicResolution)
            assert policy in meta.resolution.policies, "the given policy must be one available at meta message creation"
            meta_id = self._encode_message_map[meta.name][0]
            # currently only supporting resolution policy changes
            policy_type = "r"
            policy_index = meta.resolution.policies.index(policy)
            data.append(pack("!ccB", meta_id, policy_type, policy_index))
        return data

    def _decode_dynamic_settings(self, placeholder, offset, data):
        if len(data) < offset + 3:
            raise DropPacket("Insufficient packet size (_decode_dynamic_settings)")

        policies = []
        while len(data) >= offset + 3:
            meta_id, policy_type, policy_index = unpack_from("!ccB", data, offset)
            if not meta_id in self._decode_message_map:
                raise DropPacket("Unknown meta id [%d]" % ord(meta_id))
            meta = self._decode_message_map[meta_id][0]
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

        return offset, placeholder.meta.payload.implement(policies)

    def _encode_introduction_request(self, message):
        payload = message.payload
        assert 0 < payload.bloom_filter.num_slices < 2**8, "Assuming the sync message fits within a single MTU, it is -extremely- unlikely to have more than 20 slices"
        assert 0 < payload.bloom_filter.bits_per_slice < 2**16, "Assuming the sync message fits within a single MTU, it is -extremely- unlikely to have more than 30000 bits per slice"
        assert len(payload.bloom_filter.prefix) == 1, "The bloom filter prefix is always one byte"
        return inet_aton(payload.destination_address[0]), pack("!H", payload.destination_address[1]), \
            inet_aton(payload.source_lan_address[0]), pack("!H", payload.source_lan_address[1]), \
            inet_aton(payload.source_wan_address[0]), pack("!H", payload.source_wan_address[1]), \
            pack("!BH", int(payload.advice), payload.identifier), \
            pack("!QQBH", payload.time_low, payload.time_high, payload.bloom_filter.num_slices, payload.bloom_filter.bits_per_slice), \
            payload.bloom_filter.prefix, payload.bloom_filter.bytes

    def _decode_introduction_request(self, placeholder, offset, data):
        if len(data) < offset + 41:
            raise DropPacket("Insufficient packet size")

        destination_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        source_lan_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        source_wan_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6
        
        advice, identifier = unpack_from("!BH", data, offset)
        advice = bool(advice)
        offset += 3

        time_low, time_high, num_slices, bits_per_slice = unpack_from("!QQBH", data, offset)
        offset += 19
        if not time_low > 0:
            raise DropPacket("Invalid time_low value")
        if not (time_high == 0 or time_low <= time_high):
            raise DropPacket("Invalid time_high value")
        if not num_slices > 0:
            raise DropPacket("Invalid num_slices value")
        if not bits_per_slice > 0:
            raise DropPacket("Invalid bits_per_slice value")

        prefix = data[offset]
        offset += 1

        if not ceil(num_slices * bits_per_slice / 8.0) == len(data) - offset:
            raise DropPacket("Invalid number of bytes available")
        bloom_filter = BloomFilter(data, num_slices, bits_per_slice, offset=offset, prefix=prefix)
        offset += num_slices * bits_per_slice
        
        return offset, placeholder.meta.payload.implement(destination_address, source_lan_address, source_wan_address, advice, identifier, time_low, time_high, bloom_filter)

    def _encode_introduction_response(self, message):
        payload = message.payload
        return inet_aton(payload.destination_address[0]), pack("!H", payload.destination_address[1]), \
            inet_aton(payload.source_lan_address[0]), pack("!H", payload.source_lan_address[1]), \
            inet_aton(payload.source_wan_address[0]), pack("!H", payload.source_wan_address[1]), \
            inet_aton(payload.lan_introduction_address[0]), pack("!H", payload.lan_introduction_address[1]), \
            inet_aton(payload.wan_introduction_address[0]), pack("!H", payload.wan_introduction_address[1]), \
            pack("!H", payload.identifier)

    def _decode_introduction_response(self, placeholder, offset, data):
        if len(data) < offset + 32:
            raise DropPacket("Insufficient packet size")

        destination_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        source_lan_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        source_wan_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        lan_introduction_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        wan_introduction_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6
        
        identifier, = unpack_from("!H", data, offset)
        offset += 2

        return offset, placeholder.meta.payload.implement(destination_address, source_lan_address, source_wan_address, lan_introduction_address, wan_introduction_address, identifier)

    def _encode_puncture_request(self, message):
        payload = message.payload
        return inet_aton(payload.lan_walker_address[0]), pack("!H", payload.lan_walker_address[1]), \
            inet_aton(payload.wan_walker_address[0]), pack("!H", payload.wan_walker_address[1]), \
            pack("!H", payload.identifier)

    def _decode_puncture_request(self, placeholder, offset, data):
        if len(data) < offset + 14:
            raise DropPacket("Insufficient packet size")

        lan_walker_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        wan_walker_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        identifier, = unpack_from("!H", data, offset)
        offset += 2
        
        return offset, placeholder.meta.payload.implement(lan_walker_address, wan_walker_address, identifier)

    def _encode_puncture(self, message):
        payload = message.payload
        return inet_aton(payload.source_lan_address[0]), pack("!H", payload.source_lan_address[1]), \
            inet_aton(payload.source_wan_address[0]), pack("!H", payload.source_wan_address[1]), \
            pack("!H", payload.identifier)

    def _decode_puncture(self, placeholder, offset, data):
        if len(data) < offset + 14:
            raise DropPacket("Insufficient packet size")

        source_lan_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        source_wan_address = (inet_ntoa(data[offset:offset+4]), unpack_from("!H", data, offset+4)[0])
        offset += 6

        identifier, = unpack_from("!H", data, offset)
        offset += 2

        return offset, placeholder.meta.payload.implement(source_lan_address, source_wan_address, identifier)

    #
    # Encoding
    #

    def _encode_full_sync_distribution(self, container, message):
        if message.distribution.enable_sequence_number:
            assert message.distribution.global_time
            assert message.distribution.sequence_number
            container.append(pack("!QL", message.distribution.global_time, message.distribution.sequence_number))
        else:
            assert message.distribution.global_time
            container.append(pack("!Q", message.distribution.global_time))

    def _encode_last_sync_distribution(self, container, message):
        assert message.distribution.global_time
        container.append(pack("!Q", message.distribution.global_time))

    def _encode_direct_distribution(self, container, message):
        assert message.distribution.global_time
        container.append(pack("!Q", message.distribution.global_time))

    def _encode_public_resolution(self, container, message):
        pass

    def _encode_linear_resolution(self, container, message):
        pass

    def _encode_dynamic_resolution(self, container, message):
        index = message.resolution.policies.index(message.resolution.policy.meta)
        container.append(chr(index))

        assert type(message.resolution.policy) in self._encode_resolution_map, type(message.resolution.policy)
        assert not isinstance(message.resolution.policy, DynamicResolution)
        self._encode_resolution_map[type(message.resolution.policy)](container, message)

    def encode_message(self, message):
        assert isinstance(message, Message.Implementation), message
        assert message.name in self._encode_message_map, message.name
        message_id, encode_payload_func = self._encode_message_map[message.name]

        # Community prefix, message-id
        container = [self._prefix, message_id]

        if __debug__:
            debug_begin = clock()

        # authentication
        if isinstance(message.authentication, NoAuthentication.Implementation):
            pass
        elif isinstance(message.authentication, MemberAuthentication.Implementation):
            if message.authentication.encoding == "sha1":
                container.append(message.authentication.member.mid)
            elif message.authentication.encoding == "bin":
                assert message.authentication.member.public_key
                assert ec_check_public_bin(message.authentication.member.public_key), message.authentication.member.public_key.encode("HEX")
                container.extend((pack("!H", len(message.authentication.member.public_key)), message.authentication.member.public_key))
            else:
                raise NotImplementedError(message.authentication.encoding)
        elif isinstance(message.authentication, MultiMemberAuthentication.Implementation):
            container.extend([member.mid for member in message.authentication.members])
        else:
            raise NotImplementedError(type(message.authentication))

        if __debug__:
            self.debug_stats["encode-meta"] += clock() - debug_begin
            debug_begin = clock()

        # resolution
        assert type(message.resolution) in self._encode_resolution_map
        self._encode_resolution_map[type(message.resolution)](container, message)

        # destination does not hold any space in the message

        # distribution
        assert type(message.distribution) in self._encode_distribution_map
        self._encode_distribution_map[type(message.distribution)](container, message)

        if __debug__:
            self.debug_stats["encode-distribution"] += clock() - debug_begin
            dprint(message.name, "          head ", sum(map(len, container)) + 1, " bytes")
            debug_begin = clock()

        # payload
        itererator = encode_payload_func(message)
        assert isinstance(itererator, (tuple, list)), (type(itererator), encode_payload_func)
        assert not filter(lambda x: not isinstance(x, str), itererator)
        container.extend(itererator)

        if __debug__:
            self.debug_stats["encode-payload"] += clock() - debug_begin
            dprint(message.name, "     head+body ", sum(map(len, container)), " bytes")
            debug_begin = clock()

        # sign
        if isinstance(message.authentication, NoAuthentication.Implementation):
            packet = "".join(container)

        elif isinstance(message.authentication, MemberAuthentication.Implementation):
            assert message.authentication.member.private_key, (message.authentication.member.database_id, message.authentication.member.mid.encode("HEX"), id(message.authentication.member))
            data = "".join(container)
            signature = message.authentication.member.sign(data)
            message.authentication.set_signature(signature)
            packet = data + signature

        elif isinstance(message.authentication, MultiMemberAuthentication.Implementation):
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
            packet = data + "".join(signatures)

        else:
            raise NotImplementedError(type(message.authentication))

        if __debug__:
            self.debug_stats["sign"] += clock() - debug_begin
            dprint(message.name, " head+body+sig ", len(packet), " bytes")

            if len(packet) > 1500 - 60 - 8:
                dprint("Packet size for ", message.name, " exceeds MTU - TCP header - UDP header (", len(packet), " bytes)", level="warning")

        # dprint(message.packet.encode("HEX"))
        return packet

    #
    # Decoding
    #

    def _decode_full_sync_distribution(self, placeholder, offset, data):
        if placeholder.meta.distribution.enable_sequence_number:
            global_time, sequence_number = unpack_from("!QL", data, offset)
            if not global_time:
                raise DropPacket("Invalid global time value (_decode_full_sync_distribution)")
            if not sequence_number:
                raise DropPacket("Invalid sequence number value (_decode_full_sync_distribution)")
            return offset + 12, placeholder.meta.distribution.implement(global_time, sequence_number)
        else:
            global_time, = unpack_from("!Q", data, offset)
            if not global_time:
                raise DropPacket("Invalid global time value (_decode_full_sync_distribution)")
            return offset + 8, placeholder.meta.distribution.implement(global_time)

    def _decode_last_sync_distribution(self, placeholder, offset, data):
        global_time, = unpack_from("!Q", data, offset)
        if not global_time:
            raise DropPacket("Invalid global time value (_decode_last_sync_distribution)")
        return offset + 8, placeholder.meta.distribution.implement(global_time)

    def _decode_direct_distribution(self, placeholder, offset, data):
        global_time, = unpack_from("!Q", data, offset)
        return offset + 8, placeholder.meta.distribution.implement(global_time)

    def _decode_public_resolution(self, placeholder, offset, data, dynamic_policy=None):
        if dynamic_policy:
            return offset, dynamic_policy.implement()
        else:
            return offset, placeholder.meta.resolution.implement()

    def _decode_linear_resolution(self, placeholder, offset, data, dynamic_policy=None):
        if dynamic_policy:
            return offset, dynamic_policy.implement()
        else:
            return offset, placeholder.meta.resolution.implement()

    def _decode_dynamic_resolution(self, placeholder, offset, data):
        if len(data) < offset + 1:
            raise DropPacket("Insufficient packet size (_decode_dynamic_resolution)")

        index = ord(data[offset])
        if index > len(placeholder.meta.resolution.policies):
            raise DropPacket("Invalid policy index")
        policy = placeholder.meta.resolution.policies[index]
        offset += 1

        assert type(policy) in self._decode_resolution_map
        assert not isinstance(policy, DynamicResolution)
        offset, policy = self._decode_resolution_map[type(policy)](placeholder, offset, data, policy)

        return offset, placeholder.meta.resolution.implement(policy)

    def _decode_authentication(self, authentication, offset, data):
        if isinstance(authentication, NoAuthentication):
            return offset, authentication.implement(), len(data)

        elif isinstance(authentication, MemberAuthentication):
            if authentication.encoding == "sha1":
                if len(data) < offset + 20:
                    raise DropPacket("Insufficient packet size (_decode_authentication sha1)")
                member_id = data[offset:offset+20]
                members = [member for member in self._community.get_members_from_id(member_id) if member.has_identity(self._community)]
                if not members:
                    raise DelayPacketByMissingMember(self._community, member_id)
                offset += 20

                for member in members:
                    if __debug__:
                        debug_begin = clock()
                    first_signature_offset = len(data) - member.signature_length
                    if member.verify(data, data[first_signature_offset:], length=first_signature_offset):
                        if __debug__:
                            self.debug_stats["verify-true"] += clock() - debug_begin
                        return offset, authentication.implement(member, is_signed=True), first_signature_offset
                    if __debug__:
                        self.debug_stats["verify-false"] += clock() - debug_begin

                raise DelayPacketByMissingMember(self._community, member_id)

            elif authentication.encoding == "bin":
                key_length, = unpack_from("!H", data, offset)
                offset += 2
                if len(data) < offset + key_length:
                    raise DropPacket("Insufficient packet size (_decode_authentication bin)")
                key = data[offset:offset+key_length]
                if not ec_check_public_bin(key):
                    if __debug__: dprint(key_length, " ", key.encode("HEX"), level="warning")
                    raise DropPacket("Invalid cryptographic key (_decode_authentication)")
                member = self._community.get_member(key)
                # TODO we should ensure that member.had_identity(self._community), however, the
                # exception is the dispersy-identity message.  hence we need the placeholder
                # parameter to check this
                offset += key_length
                first_signature_offset = len(data) - member.signature_length
                if member.verify(data, data[first_signature_offset:], length=first_signature_offset):
                    return offset, authentication.implement(member, is_signed=True), first_signature_offset
                else:
                    raise DropPacket("Invalid signature")

            else:
                raise NotImplementedError(authentication.encoding)

        elif isinstance(authentication, MultiMemberAuthentication):
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

            members_ids = []
            for _ in range(authentication.count):
                member_id = data[offset:offset+20]
                members = [member for member in self._community.get_members_from_id(member_id) if member.has_identity(self._community)]
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
                    # dprint("INDEX: ", index)
                    # dprint(signature.encode('HEX'))
                    if not signature == "\x00" * member.signature_length:
                        if member.verify(data, data[signature_offset:signature_offset+member.signature_length], length=first_signature_offset):
                            signatures[index] = signature
                        else:
                            valid_or_null = False
                            break
                    signature_offset += member.signature_length

                # found a valid combination
                if valid_or_null:
                    return offset, authentication.implement(members, signatures=signatures), first_signature_offset
            raise DelayPacketByMissingMember(self._community, member_id)

        raise NotImplementedError()

    def _decode_subjective_destination(self, placeholder):
        meta = placeholder.meta
        # we want to know if the sender occurs in our subjective bloom filter
        subjective_set = self._community.get_subjective_set(self._community.my_member, meta.destination.cluster)
        assert subjective_set, "We must always have subjective sets for ourself"
        return meta.destination.implement(placeholder.authentication.member.public_key in subjective_set)

    def _decode_message(self, address, data, verify_all_signatures):
        """
        Decode a binary string into a Message structure, with some
        Dispersy specific parameters.

        When VERIFY_ALL_SIGNATURES is True, all signatures must be
        valid.  When VERIFY_ALL_SIGNATURES is False, signatures may be
        \x00 bytes.  Message.authentication.signed_members returns
        information on which members had a signature present.
        Signatures that are set and fail will NOT be accepted.
        """
        assert isinstance(data, str)
        assert isinstance(verify_all_signatures, bool)
        assert len(data) >= 22
        assert data[:22] == self._prefix, (data[:22].encode("HEX"), self._prefix.encode("HEX"))

        if len(data) < 100:
            DropPacket("Packet is to small to decode")

        placeholder = Placeholder(22, data)

        if __debug__:
            debug_begin = clock()

        # meta_message
        placeholder.meta, decode_payload_func = self._decode_message_map.get(placeholder.data[placeholder.offset], (None, None))
        if placeholder.meta is None:
            raise DropPacket("Unknown message code %d" % ord(placeholder.data[placeholder.offset]))
        placeholder.offset += 1

        if __debug__:
            self.debug_stats["decode-meta"] += clock() - debug_begin
            debug_begin = clock()

        # authentication
        placeholder.offset, placeholder.authentication, placeholder.first_signature_offset = self._decode_authentication(placeholder.meta.authentication, placeholder.offset, placeholder.data)
        if verify_all_signatures and not placeholder.authentication.is_signed:
            raise DropPacket("Invalid signature")
        # drop packet if the creator is blacklisted.  we would prefer to do this in dispersy.py,
        # however, decoding the payload can cause DelayPacketByMissingMessage to be raised for
        # dispersy-undo messages, and the last thing that we want is to request messages from a
        # blacklisted member
        if isinstance(placeholder.authentication, (MemberAuthentication.Implementation, MultiMemberAuthentication.Implementation)) and placeholder.authentication.member.must_blacklist:
            self._community.dispersy.send_malicious_proof(self._community, placeholder.authentication.member, address)
            raise DropPacket("Creator is blacklisted")

        if __debug__:
            self.debug_stats["decode-authentication"] += clock() - debug_begin
            debug_begin = clock()

        # resolution
        assert type(placeholder.meta.resolution) in self._decode_resolution_map, type(placeholder.meta.resolution)
        placeholder.offset, placeholder.resolution = self._decode_resolution_map[type(placeholder.meta.resolution)](placeholder, placeholder.offset, placeholder.data)

        # destination
        assert isinstance(placeholder.meta.destination, (MemberDestination, CommunityDestination, AddressDestination, SubjectiveDestination))
        if isinstance(placeholder.meta.destination, AddressDestination):
            placeholder.destination = placeholder.meta.destination.implement(("", 0))
        elif isinstance(placeholder.meta.destination, MemberDestination):
            placeholder.destination = placeholder.meta.destination.implement(self._community.my_member)
        elif isinstance(placeholder.meta.destination, SubjectiveDestination):
            placeholder.destination = self._decode_subjective_destination(placeholder)
        else:
            placeholder.destination = placeholder.meta.destination.implement()

        if __debug__:
            self.debug_stats["decode-destination"] += clock() - debug_begin
            debug_begin = clock()

        # distribution
        assert type(placeholder.meta.distribution) in self._decode_distribution_map, type(placeholder.meta.distribution)
        placeholder.offset, placeholder.distribution = self._decode_distribution_map[type(placeholder.meta.distribution)](placeholder, placeholder.offset, placeholder.data)

        if __debug__:
            self.debug_stats["decode-distribution"] += clock() - debug_begin
            debug_begin = clock()

        # payload
        placeholder.offset, placeholder.payload = decode_payload_func(placeholder, placeholder.offset, placeholder.data[:placeholder.first_signature_offset])
        if placeholder.offset != placeholder.first_signature_offset:
            if __debug__: dprint("invalid packet size for ", placeholder.meta.name, " data:", placeholder.first_signature_offset, "; offset:", placeholder.offset, level="warning")
            raise DropPacket("Invalid packet size (there are unconverted bytes)")
        
        if __debug__:
            self.debug_stats["decode-payload"] += clock() - debug_begin

        if __debug__:
            from payload import Payload
        assert isinstance(placeholder.payload, Payload.Implementation), type(placeholder.payload)
        assert isinstance(placeholder.offset, (int, long))

        return placeholder.meta.implement(placeholder.authentication, placeholder.resolution, placeholder.distribution, placeholder.destination, placeholder.payload, conversion=self, address=address, packet=placeholder.data)

    def decode_meta_message(self, data):
        """
        Decode a binary string into a Message instance.
        """
        assert isinstance(data, str)
        assert data[:22] == self._prefix, (data[:22].encode("HEX"), self._prefix.encode("HEX"))

        if len(data) < 23:
            DropPacket("Packet is to small to decode")

        # meta_message
        meta_message, _ = self._decode_message_map.get(data[22], (None, None))
        if meta_message is None:
            raise DropPacket("Unknown message code %d" % ord(data[22]))

        return meta_message

    def decode_message(self, address, data):
        """
        Decode a binary string into a Message.Implementation structure.
        """
        assert isinstance(address, tuple)
        assert isinstance(data, str)
        return self._decode_message(address, data, True)

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
