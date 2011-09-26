from meta import MetaObject

"""
Each Privilege can be distributed, usualy through the transfer of a message, in different ways.
These ways are defined by DistributionMeta object that is associated to the Privilege.

The DistributionMeta associated to the Privilege is used to create a Distribution object that is
assigned to the Message.

Example: A community has a permission called 'user-name'.  This Permission has the
LastSyncDistributionMeta object assigned to it.  The LastSyncDistributionMeta object dictates some
values such as the size and stepping used for the BloomFilter.

Whenever a the 'user-name' Permission is used, a LastSyncDistribution object is created.  The
LastSyncDistribution object holds additional information for this specific message, such as the
global_time.
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
            return "Distribution:" + str(self._global_time)

    def setup(self, message):
        """
        Setup is called after the meta message is initially created.
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message)

    def generate_footprint(self, global_time=0):
        assert isinstance(global_time, (int, long))
        assert global_time >= 0
        return "Distribution:" + (str(global_time) if global_time else "[0-9]+")

class SyncDistribution(Distribution):
    """
    Allows gossiping and synchronization of messages thoughout the community.

    Sequence numbers can be enabled or disabled per meta-message.  When disabled the sequence number
    is always zero.  When enabled the claim_sequence_number method can be called to obtain the next
    requence number in sequence.

    Currently there is one situation where disabling sequence numbers is required.  This is when the
    message will be signed by multiple members.  In this case the sequence number is claimed but may
    not be used (if the other members refuse to add their signature).  This causes a missing
    sequence message.  This in turn could be solved by creating a placeholder message, however, this
    is not currently, and my never be, implemented.

    The PRIORITY value ranges [0:255] where the 0 is the lowest priority and 255 the highest.  Any
    messages that have a priority below 32 will not be synced.  These messages require a mechanism
    to request missing messages whenever they are needed.

    The PRIORITY was introduced when we found that the dispersy-identity messages are the majority
    of gossiped messages while very few are actually required.  The dispersy-missing-identity
    message is used to retrieve an identity whenever it is needed.
    """
    class Implementation(Distribution.Implementation):
        def __init__(self, meta, global_time, sequence_number=0):
            assert isinstance(meta, SyncDistribution)
            assert isinstance(sequence_number, (int, long))
            assert (meta._enable_sequence_number and sequence_number > 0) or (not meta._enable_sequence_number and sequence_number == 0), (meta._enable_sequence_number, sequence_number)
            super(SyncDistribution.Implementation, self).__init__(meta, global_time)
            self._sequence_number = sequence_number

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
        def priority(self):
            return self._meta._priority

        @property
        def database_id(self):
            return self._meta._database_id

        @property
        def sequence_number(self):
            return self._sequence_number

        @property
        def footprint(self):
            return "".join(("SyncDistribution:", str(self._global_time), ",", str(self._sequence_number)))

    def __init__(self, enable_sequence_number, synchronization_direction, priority):
        # note: messages with a high priority value are synced before those with a low priority
        # value.
        # note: the priority has precedence over the global_time based ordering.
        # note: the default priority should be 127, use higher or lowe values when needed.
        assert isinstance(enable_sequence_number, bool)
        assert isinstance(synchronization_direction, unicode)
        assert synchronization_direction in (u"ASC", u"DESC")
        assert isinstance(priority, int)
        assert 0 <= priority <= 255
        self._enable_sequence_number = enable_sequence_number
        self._synchronization_direction = synchronization_direction
        self._priority = priority
        self._current_sequence_number = 0
        self._database_id = 0

    @property
    def enable_sequence_number(self):
        return self._enable_sequence_number

    @property
    def synchronization_direction(self):
        return self._synchronization_direction

    @property
    def priority(self):
        return self._priority

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

        message.community.dispersy.database.execute(u"UPDATE meta_message SET priority = ?, direction = ? WHERE id = ?",
                                                    (self._priority, -1 if self._synchronization_direction == u"DESC" else 1, message.database_id))
        assert message.community.dispersy.database.changes == 1
        
    def claim_sequence_number(self):
        assert self._enable_sequence_number
        self._current_sequence_number += 1
        return self._current_sequence_number

    def generate_footprint(self, global_time=0, sequence_number=0):
        assert isinstance(global_time, (int, long))
        assert global_time >= 0
        assert isinstance(sequence_number, (int, long))
        assert (self._enable_sequence_number and sequence_number > 0) or (not self._enable_sequence_number and sequence_number == 0)
        return "".join(("SyncDistribution:",
                        str(global_time) if global_time else "[0-9]+",
                        ",",
                        str(sequence_number) if sequence_number else "[0-9]+"))

class FullSyncDistribution(SyncDistribution):
    class Implementation(SyncDistribution.Implementation):
        pass

    def setup(self, message):
        super(FullSyncDistribution, self).setup(message)
        if self._enable_sequence_number:
            # obtain the most recent sequence number that we have used
            self._current_sequence_number, = message.community.dispersy.database.execute(u"SELECT COUNT(1) FROM sync WHERE member = ? AND meta_message = ?",
                                                                                         (message.community.my_member.database_id, message.database_id)).next()

class LastSyncDistribution(SyncDistribution):
    class Implementation(SyncDistribution.Implementation):
        @property
        def cluster(self):
            return self._meta._cluster

        @property
        def history_size(self):
            return self._meta._history_size

    def __init__(self, enable_sequence_number, synchronization_direction, priority, history_size):
        assert isinstance(history_size, int)
        assert history_size > 0
        super(LastSyncDistribution, self).__init__(enable_sequence_number, synchronization_direction, priority)
        self._community = None
        self._history_size = history_size

    def setup(self, message):
        super(LastSyncDistribution, self).setup(message)
        # keep the community for later
        self._community = message.community

    def claim_sequence_number(self):
        assert self._enable_sequence_number

        # unfortunately we can not set the _current_sequence_number in the setup(...) method because
        # we can not decode a packet there
        if self._current_sequence_number == 0:
            try:
                packet, = self._community.dispersy.database.execute(u"SELECT packet FROM sync WHERE member = ? AND meta_message = ? ORDER BY global_time DESC LIMIT 1",
                                                                    (self._community.my_member.database_id, self.database_id)).next()
            except StopIteration:
                pass
            else:
                message = self._community.dispersy.convert_packet_to_message(str(packet))
                if message:
                    self._current_sequence_number = message.distribution.sequence_number

        self._current_sequence_number += 1
        return self._current_sequence_number

    @property
    def history_size(self):
        return self._history_size

class DirectDistribution(Distribution):
    class Implementation(Distribution.Implementation):
        @property
        def footprint(self):
            return "DirectDistribution:" + str(self._global_time)

    def generate_footprint(self, global_time=0):
        assert isinstance(global_time, (int, long))
        assert global_time >= 0
        return "DirectDistribution:" + (str(global_time) if global_time else "[0-9]+")

class RelayDistribution(Distribution):
    class Implementation(Distribution.Implementation):
        @property
        def footprint(self):
            return "RelayDistribution:" + str(self._global_time)

    def generate_footprint(self, global_time=0):
        assert isinstance(global_time, (int, long))
        assert global_time >= 0
        return "RelayDistribution:" + (str(global_time) if global_time else "[0-9]+")
