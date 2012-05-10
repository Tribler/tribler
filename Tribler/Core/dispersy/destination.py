from meta import MetaObject

class Destination(MetaObject):
    class Implementation(MetaObject.Implementation):
        @property
        def footprint(self):
            return "Destination"

    def setup(self, message):
        """
        Setup is called after the meta message is initially created.
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message)

    def generate_footprint(self):
        return "Destination"

class CandidateDestination(Destination):
    """
    A destination policy where the message is sent to one or more specified candidates.
    """
    class Implementation(Destination.Implementation):
        def __init__(self, meta, *candidates):
            """
            Construct a CandidateDestination.Implementation object.

            META the associated CandidateDestination object.

            CANDIDATES is a tuple containing zero or more Candidate objects.  These will contain the
            destination addresses when the associated message is sent.
            """
            if __debug__:
                from candidate import Candidate
            assert isinstance(candidates, tuple)
            assert len(candidates) >= 0
            assert all(isinstance(candidate, Candidate) for candidate in candidates)
            super(CandidateDestination.Implementation, self).__init__(meta)
            self._candidates = candidates

        @property
        def candidates(self):
            return self._candidates

class MemberDestination(Destination):
    """
    A destination policy where the message is sent to one or more specified Members.

    Note that the Member objects need to be translated into an address.  This is done using the
    candidates that are currently online.  As this candidate list constantly changes (random walk,
    timeout, churn, etc.) it is possible that no address can be found.  In this case the message can
    not be sent and will be silently dropped.
    """
    class Implementation(Destination.Implementation):
        def __init__(self, meta, *members):
            """
            Construct an AddressDestination.Implementation object.

            META the associated MemberDestination object.

            MEMBERS is a tuple containing one or more Member instances.  These will be used to try
            to find the destination addresses when the associated message is sent.
            """
            if __debug__:
                from member import Member
            assert len(members) >= 0
            assert all(isinstance(member, Member) for member in members)
            super(MemberDestination.Implementation, self).__init__(meta)
            self._members = members

        @property
        def members(self):
            return self._members

class CommunityDestination(Destination):
    """
    A destination policy where the message is sent to one or more community members selected from
    the current candidate list.

    At the time of sending at most NODE_COUNT addresses are obtained using
    dispersy.yield_random_candidates(...) to receive the message.
    """
    class Implementation(Destination.Implementation):
        @property
        def node_count(self):
            return self._meta._node_count

    def __init__(self, node_count):
        """
        Construct a CommunityDestination object.

        NODE_COUNT is an integer giving the number of nodes where, when the message is created, the
        message must be sent to.  These nodes are selected using the
        dispersy.yield_random_candidates(...) method.  NODE_COUNT must be zero or higher.
        """
        assert isinstance(node_count, int)
        assert node_count >= 0
        self._node_count = node_count

    @property
    def node_count(self):
        return self._node_count

class SubjectiveDestination(Destination):
    """
    A destination policy where the message is sent to one or more community members, that have us in
    their subjective set, from the current candidate list.

    The bloom filter used by the SubjectiveDestination policy contains public keys of members that a
    member is interested in and can change over time.  The members' own public key will always be
    added to its own subjective set.

    For each different CLUSTER value a unique subjective set will be created and maintained.  The
    subjective set consists of a bloom filter using community.dispersy_subjective_set_bits bits and
    community.dispersy_subjective_set_error_rate error rate (note that all subjective sets use the
    same bloom filter settings).

    At the time of sending at most NODE_COUNT addresses are obtained using
    dispersy.yield_subjective_candidates(...) to receive the message.
    """
    class Implementation(Destination.Implementation):
        def __init__(self, meta, is_valid):
            """
            Construct a SubjectiveDestination.Implementation object.

            META the associated SubjectiveDestination object.

            IS_VALID is a boolean that tells us if the creator of this message is in -my- subjective
            set.
            """
            assert isinstance(is_valid, bool)
            super(SubjectiveDestination.Implementation, self).__init__(meta)
            self._is_valid = is_valid

        @property
        def cluster(self):
            return self._meta._cluster

        @property
        def node_count(self):
            return self._meta._node_count

        @property
        def is_valid(self):
            return self._is_valid

        @property
        def footprint(self):
            return "SubjectiveDestination:" + str(self._meta._cluster)

    def __init__(self, cluster, node_count):
        """
        Construct a SubjectiveDestination object.

        CLUSTER is an integer giving an value that identifies this subjective set.  For each
        different CLUSTER value a dispersy-subjective-set message is generated and spread around,
        hence SubjectiveDestination policies with the same CLUSTER value will use the same
        subjective set.

        NODE_COUNT is an integer giving the number of nodes where, when the message is created, the
        message must be sent to.  These nodes are selected using the
        dispersy.yield_subjective_candidates(...) method.  NODE_COUNT must be zero or higher.
        """
        assert isinstance(cluster, int)
        assert 0 < cluster < 2^8, "CLUSTER must fit in one byte"
        assert isinstance(node_count, int)
        assert node_count >= 0
        self._cluster = cluster
        self._node_count = node_count

    @property
    def cluster(self):
        return self._cluster

    @property
    def node_count(self):
        return self._node_count

    def setup(self, message):
        # use cache to avoid database queries
        assert message.name in message.community.meta_message_cache
        cache = message.community.meta_message_cache[message.name]
        if not cache["cluster"] == self._cluster:
            message.community.dispersy.database.execute(u"UPDATE meta_message SET cluster = ? WHERE id = ?",
                                                        (self._cluster, message.database_id))
            assert message.community.dispersy.database.changes == 1

    def generate_footprint(self):
        return "SubjectiveDestination:" + str(self._cluster)
