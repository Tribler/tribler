from meta import MetaObject

"""
Each Privilege can be distributed, usualy through the transfer of a
message, in different ways.  These ways are defined by
DistributionMeta object that is associated to the Privilege.

The DistributionMeta associated to the Privilege is used to create a
Distribution object that is assigned to the Message.

Example: A community has a permission called 'user-name'.  This
Permission has the LastSyncDistributionMeta object assigned to it.
The LastSyncDistributionMeta object dictates some values such as the
size and stepping used for the BloomFilter.

Whenever a the 'user-name' Permission is used, a LastSyncDistribution
object is created.  The LastSyncDistribution object holds additional
information for this specific message, such as the global_time.
"""

class Distribution(MetaObject):
    class Implementation(MetaObject.Implementation):
        def __init__(self, meta, global_time):
            assert isinstance(meta, Distribution)
            assert isinstance(global_time, (int, long))
            assert global_time > 0
            super(Distribution.Implementation, self).__init__(meta)
            # the last known global time + 1 (from the user who signed the
            # message)
            self._global_time = global_time

        @property
        def global_time(self):
            return self._global_time

        @property
        def footprint(self):
            return "Distribution"

    def setup(self, message):
        """
        Setup is called after the meta message is initially created.
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message)

    def generate_footprint(self):
        return "Distribution"

class SyncDistribution(Distribution):
    """
    Allows gossiping and synchronization of messages thoughout the
    community.

    Sequence numbers can be enabled or disabled per meta-message.
    When disabled the sequence number is always zero.  When enabled
    the claim_sequence_number method can be called to obtain the next
    requence number in sequence.

    Currently there is one situation where disabling sequence numbers
    is required.  This is when the message will be signed by multiple
    members.  In this case the sequence number is claimed but may not
    be used (if the other members refuse to add their signature).
    This causes a missing sequence message.  This in turn could be
    solved by creating a placeholder message, however, this is not
    currently, and my never be, implemented.
    """
    class Implementation(Distribution.Implementation):
        def __init__(self, meta, global_time, sequence_number=0):
            assert isinstance(meta, SyncDistribution)
            assert isinstance(sequence_number, (int, long))
            # assert (meta._enable_sequence_number and sequence_number > 0) or (not meta._enable_sequence_number and sequence_number == 0), "enable_sequence_number:{0} sequence_number:{1}".format(meta._enable_sequence_number, sequence_number)
            super(SyncDistribution.Implementation, self).__init__(meta, global_time)
            if sequence_number:
                assert sequence_number > 0
                self._sequence_number = sequence_number
            elif meta._enable_sequence_number:
                self._sequence_number = meta.claim_sequence_number()
            else:
                self._sequence_number = 0

        @property
        def enable_sequence_number(self):
            return self._meta._enable_sequence_number

        @property
        def synchronization_direction(self):
            return self._meta._synchronization_direction

        @property
        def synchronization_direction_id(self):
            return self._meta._synchronization_direction_id

        @property
        def database_id(self):
            return self._meta._database_id

        @property
        def sequence_number(self):
            return self._sequence_number

        @property
        def footprint(self):
            return "SyncDistribution:" + str(self._sequence_number)

    def __init__(self, enable_sequence_number, synchronization_direction):
        assert isinstance(enable_sequence_number, bool)
        assert isinstance(synchronization_direction, unicode)
        assert synchronization_direction in (u"in-order", u"out-order", u"random-order")
        self._enable_sequence_number = enable_sequence_number
        self._synchronization_direction = synchronization_direction
        self._current_sequence_number = 0
        self._database_id = 0
        self._synchronization_direction_id = 0

    @property
    def enable_sequence_number(self):
        return self._enable_sequence_number

    @property
    def synchronization_direction(self):
        return self._synchronization_direction

    @property
    def synchronization_direction_id(self):
        return self._synchronization_direction_id

    @property
    def database_id(self):
        return self._database_id

    def setup(self, message):
        """
        Setup is called after the meta message is initially created.

        It is used to determine the current sequence number, based on
        which messages are already in the database.
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message)
        if self._enable_sequence_number:
            # obtain the most recent sequence number that we have used
            self._current_sequence_number, = message.community.dispersy.database.execute(u"SELECT MAX(sync.distribution_sequence) FROM sync JOIN reference_user_sync ON (reference_user_sync.sync = sync.id) WHERE sync.community = ? AND reference_user_sync.user = ? AND name = ?", (message.community.database_id, message.community.my_member.database_id, message.database_id)).next()
            if self._current_sequence_number is None:
                # no entries in the database yet
                self._current_sequence_number = 0

        self._synchronization_direction_id, = message.community.dispersy.database.execute(u"SELECT key FROM tag WHERE value = ?", (self._synchronization_direction,)).next()

    def claim_sequence_number(self):
        assert self._enable_sequence_number
        self._current_sequence_number += 1
        return self._current_sequence_number

    def generate_footprint(self, sequence_number=0):
        assert isinstance(sequence_number, (int, long))
        assert (self._enable_sequence_number and sequence_number > 0) or (not self._enable_sequence_number and sequence_number == 0)
        return "SyncDistribution:" + str(sequence_number)

class FullSyncDistribution(SyncDistribution):
    class Implementation(SyncDistribution.Implementation):
        pass

class LastSyncDistribution(SyncDistribution):
    class Implementation(SyncDistribution.Implementation):
        @property
        def cluster(self):
            return self._meta._cluster

        @property
        def history_size(self):
            return self._meta._history_size

    def __init__(self, enable_sequence_number, synchronization_direction, history_size):
        assert isinstance(history_size, int)
        assert history_size > 0
        super(LastSyncDistribution, self).__init__(enable_sequence_number, synchronization_direction)
        self._history_size = history_size

    @property
    def history_size(self):
        return self._history_size

class DirectDistribution(Distribution):
    class Implementation(Distribution.Implementation):
        @property
        def footprint(self):
            return "DirectDistribution"

    def generate_footprint(self):
        return "DirectDistribution"

class RelayDistribution(Distribution):
    class Implementation(Distribution.Implementation):
        @property
        def footprint(self):
            return "RelayDistribution"

    def generate_footprint(self):
        return "RelayDistribution"



