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

# class NoDestination(Destination):
#     """
#     The message does not contain any destination.
#     """
#     class Implementation(Destination.Implementation):
#         pass

class AddressDestination(Destination):
    """
    The message is send to the destination address.
    """
    class Implementation(Destination.Implementation):
        def __init__(self, meta, *addresses):
            assert isinstance(addresses, tuple)
            assert len(addresses) >= 0
            assert not filter(lambda x: not isinstance(x, tuple), addresses)
            assert not filter(lambda x: not len(x) == 2, addresses)
            assert not filter(lambda x: not isinstance(x[0], str), addresses)
            assert not filter(lambda x: not isinstance(x[1], int), addresses)
            super(AddressDestination.Implementation, self).__init__(meta)
            # the target addresses
            self._addresses = addresses

        @property
        def addresses(self):
            return self._addresses

        @property
        def footprint(self):
            return "AddressDestination"

    def generate_footprint(self):
        return "AddressDestination"

class MemberDestination(Destination):
    """
    The message is send to the destination Member.
    """
    class Implementation(Destination.Implementation):
        def __init__(self, meta, *members):
            if __debug__:
                from member import Member
            assert len(members) >= 0
            assert not filter(lambda x: not isinstance(x, Member), members)
            super(MemberDestination.Implementation, self).__init__(meta)
            self._members = members

        @property
        def members(self):
            return self._members

        @property
        def footprint(self):
            return "MemberDestination"

    def generate_footprint(self):
        return "MemberDestination"

class CommunityDestination(Destination):
    """
    The message is send to one or more peers in the Community.
    """
    class Implementation(Destination.Implementation):
        @property
        def footprint(self):
            return "CommunityDestination"

        @property
        def node_count(self):
            return self._meta._node_count

    def __init__(self, node_count):
        assert isinstance(node_count, int)
        assert node_count > 0
        self._node_count = node_count

    @property
    def node_count(self):
        return self._node_count

    def generate_footprint(self):
        return "CommunityDestination"

class SubjectiveDestination(Destination):
    class Implementation(Destination.Implementation):
        def __init__(self, meta, is_valid=False):
            """
            TODO

            is_valid when message creator is in -my- subjective set (associated to the correct
            cluster)
            """
            # assert isinstance(members, list)
            # assert not filter(lambda member: not isinstance(member, Member), members)
            assert isinstance(is_valid, bool)
            super(SubjectiveDestination.Implementation, self).__init__(meta)
            # self._members = members
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

        # @property
        # def max_capacity(self):
        #     return self._meta._max_capacity

        # @property
        # def error_rate(self):
        #     return self._meta._error_rate

        @property
        def footprint(self):
            return "SubjectiveDestination:" + str(self._meta._cluster)

    def __init__(self, cluster, node_count):
        assert isinstance(cluster, int)
        assert 0 < cluster < 2^8, "CLUSTER must fit in one byte"
        assert isinstance(node_count, int)
        assert node_count > 0
        # assert isinstance(max_capacity, int)
        # assert isinstance(error_rate, float)
        self._cluster = cluster
        self._node_count = node_count
        # self._max_capacity = max_capacity
        # self._error_rate = error_rate

    @property
    def cluster(self):
        return self._cluster

    @property
    def node_count(self):
        return self._node_count
    # @property
    # def max_capacity(self):
    #     return self._max_capacity

    # @property
    # def error_rate(self):
    #     return self._error_rate

    def generate_footprint(self):
        return "SubjectiveDestination:" + str(self._cluster)

class SimilarityDestination(Destination):
    class Implementation(Destination.Implementation):
        def __init__(self, meta, bic_occurrence=0):
            assert isinstance(bic_occurrence, (int, long))
            super(SimilarityDestination.Implementation, self).__init__(meta)
            self._bic_occurrence = bic_occurrence

        @property
        def cluster(self):
            return self._meta._cluster

        @property
        def size(self):
            return self._meta._size

        @property
        def minimum_bits(self):
            return self._meta._minimum_bits

        @property
        def maximum_bits(self):
            return self._meta._maximum_bits

        @property
        def threshold(self):
            return self._meta._threshold

        @property
        def bic_occurrence(self):
            return self._bic_occurrence

        @property
        def is_similar(self):
            return self._bic_occurrence >= self._meta._threshold

        @property
        def footprint(self):
            return "SimilarityDestination:" + str(self._meta._cluster)

    def __init__(self, cluster, size, minimum_bits, maximum_bits, threshold):
        assert isinstance(cluster, int)
        assert 0 < cluster < 2^8, "CLUSTER must fit in one byte"
        assert isinstance(size, (int, long))
        assert 0 < size < 2^16, "SIZE must fit in two bytes"
        assert isinstance(minimum_bits, int)
        assert 0 <= minimum_bits <= size
        assert isinstance(maximum_bits, int)
        assert minimum_bits <= maximum_bits <= size
        assert isinstance(threshold, int)
        assert 0 < threshold <= size
        self._cluster = cluster
        self._size = size
        self._minimum_bits = minimum_bits
        self._maximum_bits = maximum_bits
        self._threshold = threshold

    @property
    def cluster(self):
        return self._cluster

    @property
    def size(self):
        return self._size

    @property
    def minimum_bits(self):
        return self._minimum_bits

    @property
    def maximum_bits(self):
        return self._maximum_bits

    @property
    def threshold(self):
        return self._threshold

    def generate_footprint(self):
        return "SimilarityDestination:" + str(self._cluster)

# class PrivilegedDestination(Destination):
#     class Implementation(Destination.Implementation):
#         pass
