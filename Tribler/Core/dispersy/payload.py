from hashlib import sha1

from meta import MetaObject

if __debug__:
    from bloomfilter import BloomFilter

    def is_address(address):
        assert isinstance(address, tuple), type(address)
        assert len(address) == 2, len(address)
        assert isinstance(address[0], str), type(address[0])
        assert address[0], address[0]
        assert isinstance(address[1], int), type(address[1])
        assert address[1] >= 0, address[1]
        return True

class Payload(MetaObject):
    class Implementation(MetaObject.Implementation):
        @property
        def footprint(self):
            return self._meta.__class__.__name__

    def setup(self, message):
        """
        Setup is called after the meta message is initially created.
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message)

    def generate_footprint(self):
        return self.__class__.__name__

    def __str__(self):
        return "<{0.__class__.__name__}>".format(self)

class IntroductionRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, destination_address, source_lan_address, source_wan_address, advice, connection_type, sync, identifier):
            """
            Create the payload for an introduction-request message.

            DESTINATION_ADDRESS is the address of the receiver.  Effectively this should be the
            wan address that others can use to contact the receiver.

            SOURCE_LAN_ADDRESS is the lan address of the sender.  Nodes in the same LAN
            should use this address to communicate.

            SOURCE_WAN_ADDRESS is the wan address of the sender.  Nodes not in the same
            LAN should use this address to communicate.

            ADVICE is a boolean value.  When True the receiver will introduce the sender to a new
            node.  This introduction will be facilitated by the receiver sending a puncture-request
            to the new node.

            CONNECTION_TYPE is a unicode string indicating the connection type that the message
            creator has.  Currently the following values are supported: u"unknown", u"public", and
            u"symmetric-NAT".

            SYNC is an optional (TIME_LOW, TIME_HIGH, MODULO, OFFSET, BLOOM_FILTER) tuple.  When
            given the introduction-request will also add this sync bloom filter in the message
            allowing the receiver to respond with missing packets.  No such sync bloom filter will
            be included when SYNC is None.

               TIME_LOW and TIME_HIGH give the global time range that the sync bloomfilter covers.

               Only packets with (global time + OFFSET % MODULO) == 0 will be taken into account,
               allowing for sync ranges to cover much larger ranges without including all the
               packets in that range.

               BLOOM_FILTER is a BloomFilter object containing all packets that the sender has in
               the given sync range.

            IDENTIFIER is a number that must be given in the associated introduction-response.  This
            number allows to distinguish between multiple introduction-response messages.
            """
            assert is_address(destination_address), destination_address
            assert is_address(source_lan_address), source_lan_address
            assert is_address(source_wan_address), source_wan_address
            assert isinstance(advice, bool), advice
            assert isinstance(connection_type, unicode) and connection_type in (u"unknown", u"public", u"symmetric-NAT"), connection_type
            assert sync is None or isinstance(sync, tuple), sync
            assert sync is None or len(sync) == 5, sync
            assert isinstance(identifier, int), identifier
            assert 0 <= identifier < 2**16, identifier
            super(IntroductionRequestPayload.Implementation, self).__init__(meta)
            self._destination_address = destination_address
            self._source_lan_address = source_lan_address
            self._source_wan_address = source_wan_address
            self._advice = advice
            self._connection_type = connection_type
            self._identifier = identifier
            if sync:
                self._time_low, self._time_high, self._modulo, self._offset, self._bloom_filter = sync
                assert isinstance(self._time_low, (int, long))
                assert 0 < self._time_low
                assert isinstance(self._time_high, (int, long))
                assert self._time_high == 0 or self._time_low <= self._time_high
                assert isinstance(self._modulo, int)
                assert 0 < self._modulo < 2**16
                assert isinstance(self._offset, int)
                assert 0 <= self._offset < self._modulo
                assert isinstance(self._bloom_filter, BloomFilter)
            else:
                self._time_low, self._time_high, self._modulo, self._offset, self._bloom_filter = 0, 0, 1, 0, None

        @property
        def destination_address(self):
            return self._destination_address

        @property
        def source_lan_address(self):
            return self._source_lan_address

        @property
        def source_wan_address(self):
            return self._source_wan_address

        @property
        def advice(self):
            return self._advice

        @property
        def connection_type(self):
            return self._connection_type

        @property
        def sync(self):
            return True if self._bloom_filter else False

        @property
        def time_low(self):
            return self._time_low

        @property
        def time_high(self):
            return self._time_high

        @property
        def has_time_high(self):
            return self._time_high > 0

        @property
        def modulo(self):
            return self._modulo

        @property
        def offset(self):
            return self._offset

        @property
        def bloom_filter(self):
            return self._bloom_filter

        @property
        def identifier(self):
            return self._identifier

class IntroductionResponsePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, destination_address, source_lan_address, source_wan_address, lan_introduction_address, wan_introduction_address, connection_type, tunnel, identifier):
            """
            Create the payload for an introduction-response message.

            DESTINATION_ADDRESS is the address of the receiver.  Effectively this should be the
            wan address that others can use to contact the receiver.

            SOURCE_LAN_ADDRESS is the lan address of the sender.  Nodes in the same LAN
            should use this address to communicate.

            SOURCE_WAN_ADDRESS is the wan address of the sender.  Nodes not in the same
            LAN should use this address to communicate.

            LAN_INTRODUCTION_ADDRESS is the lan address of the node that the sender
            advises the receiver to contact.  This address is zero when the associated request did
            not want advice.

            WAN_INTRODUCTION_ADDRESS is the wan address of the node that the sender
            advises the receiver to contact.  This address is zero when the associated request did
            not want advice.

            CONNECTION_TYPE is a unicode string indicating the connection type that the message
            creator has.  Currently the following values are supported: u"unknown", u"public", and
            u"symmetric-NAT".

            TUNNEL is a boolean indicating that the connection is tunneled and all messages send to
            the introduced candidate require a ffffffff prefix.

            IDENTIFIER is a number that was given in the associated introduction-request.  This
            number allows to distinguish between multiple introduction-response messages.

            When the associated request wanted advice the sender will also sent a puncture-request
            message to either the lan_introduction_address or the wan_introduction_address
            (depending on their positions).  The introduced node must sent a puncture message to the
            receiver to punch a hole in its NAT.
            """
            assert is_address(destination_address)
            assert is_address(source_lan_address)
            assert is_address(source_wan_address)
            assert is_address(lan_introduction_address)
            assert is_address(wan_introduction_address)
            assert isinstance(connection_type, unicode) and connection_type in (u"unknown", u"public", u"symmetric-NAT")
            assert isinstance(tunnel, bool)
            assert isinstance(identifier, int)
            assert 0 <= identifier < 2**16
            super(IntroductionResponsePayload.Implementation, self).__init__(meta)
            self._destination_address = destination_address
            self._source_lan_address = source_lan_address
            self._source_wan_address = source_wan_address
            self._lan_introduction_address = lan_introduction_address
            self._wan_introduction_address = wan_introduction_address
            self._connection_type = connection_type
            self._tunnel = tunnel
            self._identifier = identifier

        @property
        def footprint(self):
            return "IntroductionResponsePayload:%d" % self._identifier

        @property
        def destination_address(self):
            return self._destination_address

        @property
        def source_lan_address(self):
            return self._source_lan_address

        @property
        def source_wan_address(self):
            return self._source_wan_address

        @property
        def lan_introduction_address(self):
            return self._lan_introduction_address

        @property
        def wan_introduction_address(self):
            return self._wan_introduction_address

        @property
        def connection_type(self):
            return self._connection_type

        @property
        def tunnel(self):
            return self._tunnel

        @property
        def identifier(self):
            return self._identifier

    def generate_footprint(self, identifier):
        assert isinstance(identifier, int)
        assert 0 <= identifier < 2**16
        return "IntroductionResponsePayload:%d" % identifier

class PunctureRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, lan_walker_address, wan_walker_address, identifier):
            """
            Create the payload for a puncture-request payload.

            LAN_WALKER_ADDRESS is the lan address of the node that the sender wants us to
            contact.  This contact attempt should punch a hole in our NAT to allow the node to
            connect to us.

            WAN_WALKER_ADDRESS is the wan address of the node that the sender wants us to
            contact.  This contact attempt should punch a hole in our NAT to allow the node to
            connect to us.

            IDENTIFIER is a number that was given in the associated introduction-request.  This
            number allows to distinguish between multiple introduction-response messages.
            """
            assert is_address(lan_walker_address)
            assert is_address(wan_walker_address)
            assert isinstance(identifier, int)
            assert 0 <= identifier < 2**16
            super(PunctureRequestPayload.Implementation, self).__init__(meta)
            self._lan_walker_address = lan_walker_address
            self._wan_walker_address = wan_walker_address
            self._identifier = identifier

        @property
        def lan_walker_address(self):
            return self._lan_walker_address

        @property
        def wan_walker_address(self):
            return self._wan_walker_address

        @property
        def identifier(self):
            return self._identifier

class PuncturePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, source_lan_address, source_wan_address, identifier):
            """
            Create the payload for a puncture message

            SOURCE_LAN_ADDRESS is the lan address of the sender.  Nodes in the same LAN
            should use this address to communicate.

            SOURCE_WAN_ADDRESS is the wan address of the sender.  Nodes not in the same
            LAN should use this address to communicate.

            IDENTIFIER is a number that was given in the associated introduction-request.  This
            number allows to distinguish between multiple introduction-response messages.
            """
            assert is_address(source_lan_address)
            assert is_address(source_wan_address)
            assert isinstance(identifier, int)
            assert 0 <= identifier < 2**16
            super(PuncturePayload.Implementation, self).__init__(meta)
            self._source_lan_address = source_lan_address
            self._source_wan_address = source_wan_address
            self._identifier = identifier

        @property
        def source_lan_address(self):
            return self._source_lan_address

        @property
        def source_wan_address(self):
            return self._source_wan_address

        @property
        def identifier(self):
            return self._identifier

class AuthorizePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, permission_triplets):
            """
            Authorize the given permission_triplets.

            The permissions are given in the permission_triplets list.  Each element is a (Member,
            Message, permission) pair, where permission can either be u"permit", u"authorize", or
            u"revoke".
            """
            if __debug__:
                from authentication import MemberAuthentication, MultiMemberAuthentication
                from resolution import PublicResolution, LinearResolution, DynamicResolution
                from member import Member
                from message import Message
                for triplet in permission_triplets:
                    assert isinstance(triplet, tuple), triplet
                    assert len(triplet) == 3, triplet
                    assert isinstance(triplet[0], Member), triplet[0]
                    assert isinstance(triplet[1], Message), triplet[1]
                    assert isinstance(triplet[1].resolution, (PublicResolution, LinearResolution, DynamicResolution)), triplet[1]
                    assert isinstance(triplet[1].authentication, (MemberAuthentication, MultiMemberAuthentication)), triplet[1]
                    assert isinstance(triplet[2], unicode), triplet[2]
                    assert triplet[2] in (u"permit", u"authorize", u"revoke", u"undo"), triplet[2]
            super(AuthorizePayload.Implementation, self).__init__(meta)
            self._permission_triplets = permission_triplets

        @property
        def permission_triplets(self):
            return self._permission_triplets

class RevokePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, permission_triplets):
            """
            Revoke the given permission_triplets.

            The permissions are given in the permission_triplets list.  Each element is a (Member,
            Message, permission) pair, where permission can either be u"permit", u"authorize", or
            u"revoke".
            """
            if __debug__:
                from authentication import MemberAuthentication, MultiMemberAuthentication
                from resolution import PublicResolution, LinearResolution, DynamicResolution
                from member import Member
                from message import Message
                for triplet in permission_triplets:
                    assert isinstance(triplet, tuple)
                    assert len(triplet) == 3
                    assert isinstance(triplet[0], Member), triplet
                    assert isinstance(triplet[1], Message), triplet
                    assert isinstance(triplet[1].resolution, (PublicResolution, LinearResolution, DynamicResolution)), triplet
                    assert isinstance(triplet[1].authentication, (MemberAuthentication, MultiMemberAuthentication)), triplet
                    assert isinstance(triplet[2], unicode), triplet
                    assert triplet[2] in (u"permit", u"authorize", u"revoke", u"undo"), triplet
            super(RevokePayload.Implementation, self).__init__(meta)
            self._permission_triplets = permission_triplets

        @property
        def permission_triplets(self):
            return self._permission_triplets

class UndoPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, member, global_time, packet):
            if __debug__:
                from member import Member
            assert isinstance(member, Member)
            assert isinstance(global_time, (int, long))
            assert global_time > 0
            super(UndoPayload.Implementation, self).__init__(meta)
            self._member = member
            self._global_time = global_time
            self._packet = packet

        @property
        def member(self):
            return self._member

        @property
        def global_time(self):
            return self._global_time

        @property
        def packet(self):
            return self._packet

class MissingSequencePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, member, message, missing_low, missing_high):
            """
            We are missing messages of type MESSAGE signed by USER.  We
            are missing sequence numbers >= missing_low to <=
            missing_high.
            """
            if __debug__:
                from member import Member
                from message import Message
            assert isinstance(member, Member)
            assert isinstance(message, Message)
            assert isinstance(missing_low, (int, long))
            assert isinstance(missing_high, (int, long))
            assert 0 < missing_low <= missing_high
            super(MissingSequencePayload.Implementation, self).__init__(meta)
            self._member = member
            self._message = message
            self._missing_low = missing_low
            self._missing_high = missing_high

        @property
        def member(self):
            return self._member

        @property
        def message(self):
            return self._message

        @property
        def missing_low(self):
            return self._missing_low

        @property
        def missing_high(self):
            return self._missing_high

class SignaturePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, message):
            if __debug__:
                from message import Message
            assert isinstance(identifier, int), identifier
            assert 0 <= identifier < 2**16, identifier
            assert isinstance(message, Message.Implementation)
            super(SignaturePayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._message = message

        @property
        def identifier(self):
            return self._identifier

        @property
        def message(self):
            return self._message

        @property
        def footprint(self):
            return "SignaturePayload:%d" % self._identifier

    def generate_footprint(self, identifier):
        assert isinstance(identifier, int), identifier
        assert 0 <= identifier < 2**16, identifier
        return "SignaturePayload:%d" % identifier

class SignatureRequestPayload(SignaturePayload):
    class Implementation(SignaturePayload.Implementation):
        pass

class SignatureResponsePayload(SignaturePayload):
    class Implementation(SignaturePayload.Implementation):
        pass

class IdentityPayload(Payload):
    class Implementation(Payload.Implementation):
        pass

class MissingIdentityPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, mid):
            assert isinstance(mid, str)
            assert len(mid) == 20
            super(MissingIdentityPayload.Implementation, self).__init__(meta)
            self._mid = mid

        @property
        def mid(self):
            return self._mid

class DestroyCommunityPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, degree):
            assert isinstance(degree, unicode)
            assert degree in (u"soft-kill", u"hard-kill")
            super(DestroyCommunityPayload.Implementation, self).__init__(meta)
            self._degree = degree

        @property
        def degree(self):
            return self._degree

        @property
        def is_soft_kill(self):
            return self._degree == u"soft-kill"

        @property
        def is_hard_kill(self):
            return self._degree == u"hard-kill"

class SubjectiveSetPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, cluster, subjective_set):
            if __debug__:
                from bloomfilter import BloomFilter
            assert isinstance(cluster, int)
            assert 0 < cluster < 2^8, "CLUSTER must fit in one byte"
            assert isinstance(subjective_set, BloomFilter)
            super(SubjectiveSetPayload.Implementation, self).__init__(meta)
            self._cluster = cluster
            self._subjective_set = subjective_set

        @property
        def cluster(self):
            return self._cluster

        @property
        def subjective_set(self):
            return self._subjective_set

class MissingSubjectiveSetPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, cluster, members):
            """
            The payload for a dispersy-missing-subjective-set message.

            This message is sent whenever we are missing the dispersy-subjective-set message for a
            specific cluster and member.

            The sender side is likely to add only one member, however, on the receiver side this may
            result in multiple member instance, because the member is represented as a 20 byte sha1
            digest on the wire.  Hence the payload must be able to contain multiple members.

            @param cluster: the cluster that we want the subjective set for (note that one member
             can have multiple subjective sets, they are identified by their cluster).
            @type cluster: int

            @param members: the list of members for wich we want the subjective set.
            @type member: [Member]
            """
            if __debug__:
                from member import Member
            assert isinstance(cluster, int)
            assert 0 < cluster < 2^8, "CLUSTER must fit in one byte"
            assert isinstance(members, (tuple, list))
            assert all(isinstance(member, Member) for member in members)
            super(MissingSubjectiveSetPayload.Implementation, self).__init__(meta)
            self._cluster = cluster
            self._members = members

        @property
        def cluster(self):
            return self._cluster

        @property
        def members(self):
            return self._members

class MissingMessagePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, member, global_times):
            if __debug__:
                from member import Member
            assert isinstance(member, Member)
            assert isinstance(global_times, (tuple, list))
            assert all(isinstance(global_time, (int, long)) for global_time in global_times)
            assert all(global_time > 0 for global_time in global_times)
            assert len(global_times) > 0
            assert len(set(global_times)) == len(global_times)
            super(MissingMessagePayload.Implementation, self).__init__(meta)
            self._member = member
            self._global_times = global_times

        @property
        def member(self):
            return self._member

        @property
        def global_times(self):
            return self._global_times

# class MissingLastPayload(Payload):
#     class Implementation(Payload.Implementation):
#         def __init__(self, meta, member, message):
#             if __debug__:
#                 from member import Member
#             assert isinstance(member, Member)
#             assert isinstance(message, Message)
#             assert isinstance(message.distribution, LastSyncDistribution), "Currently we only support LastSyncDistribution"
#             super(MissingLastPayload.Implementation, self).__init__(meta)
#             self._member = member
#             self._message = message

#         @property
#         def member(self):
#             return self._member

#         @property
#         def message(self):
#             return self._message

class MissingProofPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, member, global_time):
            if __debug__:
                from member import Member
            assert isinstance(member, Member)
            assert isinstance(global_time, (int, long))
            assert global_time > 0
            super(MissingProofPayload.Implementation, self).__init__(meta)
            self._member = member
            self._global_time = global_time

        @property
        def member(self):
            return self._member

        @property
        def global_time(self):
            return self._global_time

class DynamicSettingsPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, policies):
            """
            Create a new payload container for a dispersy-dynamic-settings message.

            This message allows the community to start using different policies for one or more of
            its messages.  Currently only the resolution policy can be dynamically changed.

            The POLICIES is a list containing (meta_message, policy) tuples.  The policy that is
            choosen must be one of the policies defined for the associated meta_message.

            @param policies: A list with the new message policies.
            @type *policies: [(meta_message, policy), ...]
            """
            if __debug__:
                from message import Message
                from resolution import PublicResolution, LinearResolution, DynamicResolution
                assert isinstance(policies, (tuple, list))
                for tup in policies:
                    assert isinstance(tup, tuple)
                    assert len(tup) == 2
                    message, policy = tup
                    assert isinstance(message, Message)
                    # currently only supporting resolution policy changes
                    assert isinstance(message.resolution, DynamicResolution)
                    assert isinstance(policy, (PublicResolution, LinearResolution))
                    assert policy in message.resolution.policies, "the given policy must be one available at meta message creation"

            super(DynamicSettingsPayload.Implementation, self).__init__(meta)
            self._policies = policies

        @property
        def policies(self):
            """
            Returns a list or tuple containing the new message policies.
            @rtype: [(meta_message, policy), ...]
            """
            return self._policies
