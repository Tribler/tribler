from time import time
from hashlib import sha1

from meta import MetaObject

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

class AuthorizePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, permission_triplets):
            """
            Authorize the given permission_triplets.

            The permissions are given in the permission_triplets list.  Each element is a (Member,
            Message, permission) pair, where permission can either be u'permit', u'authorize', or
            u'revoke'.
            """
            if __debug__:
                from authentication import MemberAuthentication
                from resolution import LinearResolution
                from member import Member
                from message import Message
                for triplet in permission_triplets:
                    assert isinstance(triplet, tuple)
                    assert len(triplet) == 3
                    assert isinstance(triplet[0], Member)
                    assert isinstance(triplet[1], Message)
                    assert isinstance(triplet[1].resolution, LinearResolution)
                    assert isinstance(triplet[1].authentication, MemberAuthentication)
                    assert isinstance(triplet[2], unicode)
                    assert triplet[2] in (u'permit', u'authorize', u'revoke')
            super(AuthorizePayload.Implementation, self).__init__(meta)
            self._permission_triplets = permission_triplets

        @property
        def permission_triplets(self):
            return self._permission_triplets

        @property
        def payload(self):
            return self._payload

class RevokePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, permission_triplets):
            """
            Revoke the given permission_triplets.

            The permissions are given in the permission_triplets list.  Each element is a (Member,
            Message, permission) pair, where permission can either be u'permit', u'authorize', or
            u'revoke'.
            """
            if __debug__:
                from authentication import MemberAuthentication
                from resolution import LinearResolution
                from member import Member
                from message import Message
                for triplet in permission_triplets:
                    assert isinstance(triplet, tuple)
                    assert len(triplet) == 3
                    assert isinstance(triplet[0], Member)
                    assert isinstance(triplet[1], Message)
                    assert isinstance(triplet[1].resolution, LinearResolution)
                    assert isinstance(triplet[1].authentication, MemberAuthentication)
                    assert isinstance(triplet[2], unicode)
                    assert triplet[2] in (u'permit', u'authorize', u'revoke')
            super(RevokePayload.Implementation, self).__init__(meta)
            self._permission_triplets = permission_triplets

        @property
        def permission_triplets(self):
            return self._permission_triplets

        @property
        def payload(self):
            return self._payload

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

class CandidatePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, source_address, destination_address, source_default_conversion, routes):
            assert isinstance(source_address, tuple)
            assert len(source_address) == 2
            assert isinstance(source_address[0], str)
            assert isinstance(source_address[1], int)
            assert isinstance(destination_address, tuple)
            assert len(destination_address) == 2
            assert isinstance(destination_address[0], str)
            assert isinstance(destination_address[1], int)
            assert isinstance(source_default_conversion, tuple)
            assert len(source_default_conversion) == 2
            assert isinstance(source_default_conversion[0], str)
            assert len(source_default_conversion[0]) == 1
            assert isinstance(source_default_conversion[1], str)
            assert len(source_default_conversion[1]) == 1
            assert isinstance(routes, (tuple, list))
            assert not filter(lambda route: not isinstance(route, tuple), routes)
            assert not filter(lambda route: not len(route) == 2, routes)
            assert not filter(lambda route: not isinstance(route[0], tuple), routes)
            assert not filter(lambda route: not len(route[0]) == 2, routes)
            assert not filter(lambda route: not isinstance(route[0][0], str), routes)
            assert not filter(lambda route: not isinstance(route[0][1], (int, long)), routes)
            assert not filter(lambda route: not isinstance(route[1], float), routes)
            super(CandidatePayload.Implementation, self).__init__(meta)
            self._source_address = source_address
            self._destination_address = destination_address
            self._source_default_conversion = source_default_conversion
            self._routes = routes

        @property
        def source_address(self):
            return self._source_address

        @property
        def destination_address(self):
            return self._destination_address

        @property
        def source_default_conversion(self):
            return self._source_default_conversion

        @property
        def routes(self):
            return self._routes
        #     now = time()
        #     return [(address, age + now - stamp) for stamp, address, age in self._routes]

        # def add_route(self, address, age):
        #     assert isinstance(address, tuple)
        #     assert len(address) == 2
        #     assert isinstance(address[0], str)
        #     assert isinstance(address[1], int)
        #     assert isinstance(age, float)
        #     assert age >= 0.0
        #     assert len(self._routes) < 50
        #     self._routes.append(time(), address, age)

class CandidateRequestPayload(CandidatePayload):
    class Implementation(CandidatePayload.Implementation):
        pass

class CandidateResponsePayload(CandidatePayload):
    class Implementation(CandidatePayload.Implementation):
        def __init__(self, meta, request_identifier, source_address, destination_address, source_default_conversion, routes):
            assert isinstance(request_identifier, str)
            assert len(request_identifier) == 20
            super(CandidateResponsePayload.Implementation, self).__init__(meta, source_address, destination_address, source_default_conversion, routes)
            self._request_identifier = request_identifier

        @property
        def request_identifier(self):
            return self._request_identifier

        @property
        def footprint(self):
            return "CandidateResponsePayload:" + self._request_identifier.encode("HEX")

    def generate_footprint(self, request_identifier):
        assert isinstance(request_identifier, str)
        assert len(request_identifier) == 20
        return "CandidateResponsePayload:" + request_identifier.encode("HEX")

class SignatureRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, message):
            super(SignatureRequestPayload.Implementation, self).__init__(meta)
            self._message = message

        @property
        def message(self):
            return self._message

class SignatureResponsePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, signature):
            assert isinstance(identifier, str)
            assert len(identifier) == 20
            super(SignatureResponsePayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._signature = signature

        @property
        def identifier(self):
            return self._identifier

        @property
        def signature(self):
            return self._signature

        @property
        def footprint(self):
            return "SignatureResponsePayload:" + self._identifier.encode("HEX")

    def generate_footprint(self, identifier):
        assert isinstance(identifier, str)
        assert len(identifier) == 20
        return "SignatureResponsePayload:" + identifier.encode("HEX")

class IdentityPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, address):
            assert isinstance(address, tuple)
            assert len(address) == 2
            assert isinstance(address[0], str)
            assert isinstance(address[1], int)
            super(IdentityPayload.Implementation, self).__init__(meta)
            self._address = address

        @property
        def address(self):
            return self._address

class IdentityRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, mid):
            assert isinstance(mid, str)
            assert len(mid) == 20
            super(IdentityRequestPayload.Implementation, self).__init__(meta)
            self._mid = mid

        @property
        def mid(self):
            return self._mid

        @property
        def footprint(self):
            return "IdentityPayload:" + self._mid

    def generate_footprint(self, mid):
        return "IdentityPayload" + mid

class SyncPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, time_low, time_high, bloom_filter):
            if __debug__:
                from bloomfilter import BloomFilter
            assert isinstance(time_low, (int, long))
            assert 0 < time_low
            assert isinstance(time_high, (int, long))
            assert time_high == 0 or time_low <= time_high
            assert isinstance(bloom_filter, BloomFilter)
            super(SyncPayload.Implementation, self).__init__(meta)
            self._time_low = time_low
            self._time_high = time_high
            self._bloom_filter = bloom_filter

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
        def bloom_filter(self):
            return self._bloom_filter

class SimilarityPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, cluster, similarity):
            """
            The payload for a dispersy-similarity message.

            CLUSTER is the cluster that we want the similarity for (note
            that one member can have multiple similarity bitstrings, they
            are identified by message.destination.cluster).

            SIMILARITY is a BloomFilter containing the similarity bits.
            The bloom filter must have the same size as is defined in the
            meta Message.
            """
            if __debug__:
                from bloomfilter import BloomFilter
            assert isinstance(cluster, int)
            assert 0 < cluster < 2^8, "CLUSTER must fit in one byte"
            assert isinstance(similarity, BloomFilter)
            super(SimilarityPayload.Implementation, self).__init__(meta)
            self._cluster = cluster
            self._similarity = similarity

        @property
        def cluster(self):
            return self._cluster

        @property
        def similarity(self):
            return self._similarity

class SimilarityRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, cluster, members):
            """
            The payload for a dispersy-similarity-request message.

            CLUSTER is the cluster that we want the similarity for (note
            that one member can have multiple similarity bitstrings, they
            are identified by message.destination.cluster).

            MEMBERS is a list with Member instances for wich we want the
            similarity.  We specifically need a list of members here,
            because we are unable to uniquely identify a single Member
            using the 20 byte sha1 hash.
            """
            if __debug__:
                from member import Member
            assert isinstance(cluster, int)
            assert 0 < cluster < 2^8, "CLUSTER must fit in one byte"
            assert isinstance(members, (tuple, list))
            assert not filter(lambda x: not isinstance(x, Member), members)
            super(SimilarityRequestPayload.Implementation, self).__init__(meta)
            self._cluster = cluster
            self._members = members

        @property
        def cluster(self):
            return self._cluster

        @property
        def members(self):
            return self._members

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

class SubjectiveSetRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, cluster, members):
            """
            The payload for a dispersy-subjective-set-request message.

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
            assert not filter(lambda x: not isinstance(x, Member), members)
            super(SubjectiveSetRequestPayload.Implementation, self).__init__(meta)
            self._cluster = cluster
            self._members = members

        @property
        def cluster(self):
            return self._cluster

        @property
        def members(self):
            return self._members
