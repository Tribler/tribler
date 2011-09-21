"""
the community module provides the Community baseclass that should be used when a new Community is
implemented.  It provides a simplified interface between the Dispersy instance and a running
Community instance.

@author: Boudewijn Schoon
@organization: Technical University Delft
@contact: dispersy@frayja.com
"""

from hashlib import sha1
from itertools import count
from math import sqrt
from random import gauss, choice

from bloomfilter import BloomFilter
from cache import CacheDict
from conversion import BinaryConversion, DefaultConversion
from crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from decorator import documentation
from destination import SubjectiveDestination
from dispersy import Dispersy
from dispersydatabase import DispersyDatabase
from member import Member
from resolution import LinearResolution, DynamicResolution
from timeline import Timeline

if __debug__:
    from dprint import dprint
    from math import ceil

class SyncRange(object):
    def __init__(self, time_low, bits, error_rate, redundancy):
        assert isinstance(time_low, (int, long))
        assert time_low > 0
        assert isinstance(bits, (int, long))
        assert bits > 0
        assert isinstance(error_rate, float)
        assert 0.0 < error_rate < 1.0
        assert isinstance(redundancy, int)
        assert redundancy > 0
        self.time_low = time_low
        self.space_freed = 0
        self.bloom_filters = [BloomFilter(error_rate, bits, prefix=chr(i)) for i in xrange(redundancy)]
        self.space_remaining = self.capacity = self.bloom_filters[0].capacity
        if __debug__:
            for bloom_filter in self.bloom_filters:
                assert self.capacity == bloom_filter.capacity
                assert 0 < bloom_filter.num_slices < 2**8, "Assuming the sync message fits within a single MTU, it is -extremely- unlikely to have more than 20 slices"
                assert 0 < bloom_filter.bits_per_slice < 2**16, "Assuming the sync message fits within a single MTU, it is -extremely- unlikely to have more than 30000 bits per slice"
                assert len(bloom_filter.prefix) == 1, "The bloom filter prefix is always one byte"

    def add(self, packet):
        assert isinstance(packet, str)
        assert len(packet) > 0
        self.space_remaining -= 1
        for bloom_filter in self.bloom_filters:
            bloom_filter.add(packet)
        if __debug__: dprint("add ", len(packet), " byte packet to sync range. ", self.space_remaining, " space remaining")

    def free(self):
        self.space_freed += 1
        assert self.space_freed <= self.capacity - self.space_remaining, "May never free more than added"

    def clear(self):
        self.space_freed = 0
        self.space_remaining = self.capacity
        for bloom_filter in self.bloom_filters:
            bloom_filter.clear()

class SubjectiveSetCache(object):
    def __init__(self, packet, subjective_set):
        assert isinstance(packet, str)
        assert isinstance(subjective_set, BloomFilter)
        self.packet = packet
        self.subjective_set = subjective_set

class Community(object):
    @classmethod
    def get_classification(cls):
        """
        Describes the community type.  Should be the same across compatible versions.
        @rtype: unicode
        """
        return cls.__name__.decode("UTF-8")

    @classmethod
    def create_community(cls, my_member, *args, **kargs):
        """
        Create a new community owned by my_member.

        Each unique community, that exists out in the world, is identified by a public/private key
        pair.  When the create_community method is called such a key pair is generated.

        Furthermore, my_member will be granted permission to use all the messages that the community
        provides.

        @param my_member: The Member that will be granted Permit, Authorize, and Revoke for all
         messages.
        @type my_member: Member

        @param args: optional arguments that are passed to the community constructor.
        @type args: tuple

        @param kargs: optional keyword arguments that are passed to the community constructor.
        @type args: dictionary

        @return: The created community instance.
        @rtype: Community
        """
        assert isinstance(my_member, Member), my_member
        ec = ec_generate_key(u"high")
        master = Member.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec))

        database = DispersyDatabase.get_instance()
        database.execute(u"INSERT INTO community (master, member, classification) VALUES(?, ?, ?)", (master.database_id, my_member.database_id, cls.get_classification()))

        # new community instance
        community = cls.load_community(master, *args, **kargs)

        # create the dispersy-identity for the master member
        meta = community.get_meta_message(u"dispersy-identity")
        message = meta.impl(authentication=(master,),
                            distribution=(community.claim_global_time(),),
                            payload=(("0.0.0.0", 0),))
        community.dispersy.store_update_forward([message], True, True, False)

        # create the dispersy-identity for my member
        community.create_dispersy_identity()

        # authorize MY_MEMBER for each message
        permission_triplets = []
        for message in community.get_meta_messages():
            if isinstance(message.resolution, (LinearResolution, DynamicResolution)):
                for allowed in (u"authorize", u"revoke", u"permit"):
                    permission_triplets.append((my_member, message, allowed))
        if permission_triplets:
            community.create_dispersy_authorize(permission_triplets, sign_with_master=True, forward=False)

        return community

    @classmethod
    def join_community(cls, master, my_member, *args, **kargs):
        """
        Join an existing community.

        Once you have discovered an existing community, i.e. you have obtained the public master key
        from a community, you can join this community.

        Joining a community does not mean that you obtain permissions in that community, those will
        need to be granted by another member who is allowed to do so.  However, it will let you
        receive, send, and disseminate messages that do not require any permission to use.

        @param master: The master member that identified the community that we want to join.
        @type master: Member

        @param my_member: The member that will be granted Permit, Authorize, and Revoke for all
         messages.
        @type my_member: Member

        @param args: optional argumets that are passed to the community constructor.
        @type args: tuple

        @param kargs: optional keyword arguments that are passed to the community constructor.
        @type args: dictionary

        @return: The created community instance.
        @rtype: Community
        """
        assert isinstance(master, Member)
        assert isinstance(my_member, Member)
        if __debug__: dprint("joining ", cls.get_classification(), " ", master.mid.encode("HEX"))

        execute = DispersyDatabase.get_instance().execute
        execute(u"INSERT INTO community(master, member, classification) VALUES(?, ?, ?)",
                (master.database_id, my_member.database_id, cls.get_classification()))

        # new community instance
        community = cls.load_community(master, *args, **kargs)

        # send out my initial dispersy-identity
        community.create_dispersy_identity()

        return community

    @classmethod
    def get_master_members(cls):
        def loader(mid, master_public_key):
            assert isinstance(mid, buffer)
            assert master_public_key is None ot isinstance(master_public_key, buffer)
            if master_public_key:
                return Member.get_instance(str(master_public_key))
            else:
                return Member.get_instance(str(mid), public_key_available=False)

        if __debug__: dprint("retrieving all master members owning ", cls.get_classification(), " communities")
        execute = DispersyDatabase.get_instance().execute
        return [loader(mid, master_public_key)
                for mid, master_public_key
                in list(execute(u"SELECT m.mid, m.public_key FROM community AS c JOIN member AS m ON m.id = c.master WHERE c.classification = ?", (cls.get_classification(),)))]

    @classmethod
    def load_community(cls, master, *args, **kargs):
        """
        Load a single community.

        Will raise a ValueError exception when cid is unavailable.

        @param master: The master member that identifies the community.
        @type master: Member

        @return: The community identified by master.
        @rtype: Community
        """
        assert isinstance(master, Member)
        if __debug__: dprint("loading ", cls.get_classification(), " ", master.mid.encode("HEX"))
        community = cls(master, *args, **kargs)

        # tell dispersy that there is a new community
        community._dispersy.attach_community(community)

        # start the peer selection strategy (must be called after attach)
        community.dispersy_start_walk()
        
        return community

    def __init__(self, master):
        """
        Initialize a community.

        Generally a new community is created using create_community.  Or an existing community is
        loaded using load_community.  These two methods prepare and call this __init__ method.

        @param master: The master member that identifies the community.
        @type master: Member
        """
        assert isinstance(master, Member)
        if __debug__: dprint("initializing ", self.get_classification(), " ", master.mid.encode("HEX"))

        self._dispersy = Dispersy.get_instance()
        self._dispersy_database = DispersyDatabase.get_instance()

        try:
            self._database_id, member_public_key = self._dispersy_database.execute(u"SELECT community.id, member.public_key FROM community JOIN member ON member.id = community.member WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            raise ValueError(u"Community not found in database [" + master.mid.encode("HEX") + "]")

        self._cid = master.mid
        self._master_member = master
        self._my_member = Member.get_instance(str(member_public_key))

        # define all available messages
        self._meta_messages = {}
        self._initialize_meta_messages()

        # define all available conversions
        conversions = self.initiate_conversions()
        assert len(conversions) > 0
        self._conversions = dict((conversion.prefix, conversion) for conversion in conversions)
        # the last conversion in the list will be used as the default conversion
        self._conversions[None] = conversions[-1]

        # the list with bloom filters.  the list will grow as the global time increases.  older time
        # ranges are at higher indexes in the list, new time ranges are inserted at the start of the
        # list.
        self._global_time = 0
        self._time_high = 1
        self._sync_ranges = []
        self._initialize_sync_ranges()
        if __debug__:
            b = BloomFilter(self.dispersy_sync_bloom_filter_error_rate, self.dispersy_sync_bloom_filter_bits)
            dprint("sync range bloom filter. size: ", int(ceil(b.size // 8)), "; capacity: ", b.capacity, "; error-rate: ", b.error_rate)

        # the subjective sets.  the dictionary containing subjective sets that were recently used.
        self._subjective_sets = CacheDict()  # (member, cluster) / SubjectiveSetCache pairs
        self._subjective_set_clusters = []   # all cluster numbers used by subjective sets
        self._initialize_subjective_sets()
        if __debug__:
            if any(isinstance(meta.destination, SubjectiveDestination) for meta in self._meta_messages.itervalues()):
                b = BloomFilter(self.dispersy_subjective_set_error_rate, self.dispersy_subjective_set_bits)
                dprint("subjective set. size: ", int(ceil(b.size // 8)), "; capacity: ", b.capacity, "; error-rate: ", b.error_rate)

        # initial timeline.  the timeline will keep track of member permissions
        self._timeline = Timeline(self)
        self._initialize_timeline()

    def _initialize_meta_messages(self):
        assert isinstance(self._meta_messages, dict)
        assert len(self._meta_messages) == 0

        # obtain dispersy meta messages
        for meta_message in self._dispersy.initiate_meta_messages(self):
            assert meta_message.name not in self._meta_messages
            self._meta_messages[meta_message.name] = meta_message

        # obtain community meta messages
        for meta_message in self.initiate_meta_messages():
            assert meta_message.name not in self._meta_messages
            self._meta_messages[meta_message.name] = meta_message

        if __debug__:
            from distribution import SyncDistribution
            sync_delay = self._meta_messages[u"dispersy-introduction-request"].delay
            for meta_message in self._meta_messages.itervalues():
                if isinstance(meta_message.distribution, SyncDistribution):
                    assert meta_message.delay < sync_delay, (meta_message.name, "when sync is enabled the interval should be greater than the message delay.  otherwise you are likely to receive duplicate packets")
        
    def _initialize_sync_ranges(self):
        assert isinstance(self._sync_ranges, list)
        assert len(self._sync_ranges) == 0
        assert self._global_time == 0
        assert self._time_high == 1

        # ensure that at least one bloom filter exists
        sync_range = SyncRange(1, self.dispersy_sync_bloom_filter_bits, self.dispersy_sync_bloom_filter_error_rate, self.dispersy_sync_bloom_filter_redundancy)
        self._sync_ranges.insert(0, sync_range)

        current_global_time, global_time = self._dispersy.database.execute(u"SELECT MIN(global_time), MAX(global_time) FROM sync WHERE community = ?", (self.database_id,)).next()
        if __debug__: dprint("MIN:", current_global_time, "; MAX:", global_time)
        if not global_time:
            return
        self._global_time = self._time_high = global_time

        # load all messages into the bloom filters
        packets = []
        for global_time, packet in self._dispersy.database.execute(u"SELECT global_time, packet FROM sync WHERE community = ? ORDER BY global_time, packet", (self.database_id,)):
            if global_time == current_global_time:
                packets.append(str(packet))
            else:
                if len(packets) > sync_range.space_remaining:
                    sync_range = SyncRange(current_global_time, self.dispersy_sync_bloom_filter_bits, self.dispersy_sync_bloom_filter_error_rate, self.dispersy_sync_bloom_filter_redundancy)
                    self._sync_ranges.insert(0, sync_range)

                map(sync_range.add, packets)
                if __debug__: dprint("add in [", sync_range.time_low, ":inf] ", len(packets), " packets @", current_global_time, "; remaining: ", sync_range.space_remaining)

                packets = [str(packet)]
                current_global_time = global_time

        if packets:
            if len(packets) > sync_range.space_remaining:
                sync_range = SyncRange(global_time, self.dispersy_sync_bloom_filter_bits, self.dispersy_sync_bloom_filter_error_rate, self.dispersy_sync_bloom_filter_redundancy)
                self._sync_ranges.insert(0, sync_range)

            map(sync_range.add, packets)
            if __debug__: dprint("add in [", sync_range.time_low, ":inf] ", len(packets), " packets @", current_global_time, "; remaining: ", sync_range.space_remaining)

        # todo: maybe we can add a callback or event notifier to give a progress indication while
        # loading millions of packets...

    def _initialize_subjective_sets(self):
        assert isinstance(self._subjective_sets, CacheDict)
        assert len(self._subjective_sets) == 0
        assert isinstance(self._subjective_set_clusters, list)
        assert len(self._subjective_set_clusters) == 0

        try:
            meta = self.get_meta_message(u"dispersy-subjective-set")

        except KeyError:
            # subjective sets are disabled for this community
            pass

        else:
            # ensure we have all unique cluster numbers
            self._subjective_set_clusters = list(set(meta.destination.cluster for meta in self.get_meta_messages() if isinstance(meta.destination, SubjectiveDestination)))

            # load all subjective sets by self.my_member
            for packet, in self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND meta_message = ?",
                                                           (self._database_id, self._my_member.database_id, meta.database_id)):
                packet = str(packet)

                # check that this is the packet we are looking for, i.e. has the right cluster
                conversion = self.get_conversion(packet[:22])
                message = conversion.decode_message(("", -1), packet)
                key = (self._my_member, message.payload.cluster)
                assert not key in self._subjective_sets
                self._subjective_sets[key] = SubjectiveSetCache(message.packet, message.payload.subjective_set)

            # ensure that there are no missing subjective sets
            for cluster in self._subjective_set_clusters:
                    key = (self._my_member, cluster)
                    if not key in self._subjective_sets:
                        # create this missing subjective set
                        message = self.create_dispersy_subjective_set(cluster, [self._my_member])
                        self._subjective_sets[key] = SubjectiveSetCache(message.packet, message.payload.subjective_set)

            if self._subjective_sets:
                # apparently we have one or more subjective sets
                self._dispersy.callback.register(self._periodically_cleanup_subjective_sets)

    def _periodically_cleanup_subjective_sets(self):
        while True:
            # peek once every minute.  given that the initial_poke_count is 10, this will ensure
            # that a cache instance will exist for at least 10 peeks (unless we run out of cache
            # space)
            yield 60.0

            if __debug__: dprint(self._subjective_sets)
            for key, cache in self._subjective_sets.cleanup():
                if __debug__: dprint("member: ", key[0].database_id, "; cluster: ", key[1])

    def _initialize_timeline(self):
        # load existing permissions from the database
        try:
            authorize = self.get_meta_message(u"dispersy-authorize")
            revoke = self.get_meta_message(u"dispersy-revoke")
            dynamic_settings = self.get_meta_message(u"dispersy-dynamic-settings")

        except KeyError:
            if __debug__: dprint("unable to load permissions from database [could not obtain 'dispersy-authorize' or 'dispersy-revoke' or 'dispersy-dynamic-settings']", level="warning")

        else:
            mapping = {authorize.database_id:authorize.handle_callback, revoke.database_id:revoke.handle_callback, dynamic_settings.database_id:dynamic_settings.handle_callback}
            # for meta_message_id, packet in self._dispersy.database.execute(u"SELECT meta_message, packet FROM sync WHERE meta_message IN (?, ?, ?) ORDER BY global_time, packet", (authorize.database_id, revoke.database_id, dynamic_settings.database_id)):
            for meta_message_id, packet in list(self._dispersy.database.execute(u"SELECT meta_message, packet FROM sync WHERE meta_message IN (?, ?, ?) ORDER BY global_time, packet", (authorize.database_id, revoke.database_id, dynamic_settings.database_id))):
                packet = str(packet)
                # TODO: when a packet conversion fails we must drop something, and preferably check
                # all messages in the database again...
                message = self.get_conversion(packet[:22]).decode_message(("", -1), packet)
                mapping[meta_message_id]([message], initializing=True)

    # @property
    def __get_dispersy_auto_load(self):
        """
        When True, this community will automatically be loaded when a packet is received.
        """
        # currently we grab it directly from the database, should become a property for efficiency
        return bool(self._dispersy_database.execute(u"SELECT auto_load FROM community WHERE master = ?",
                                                    (self._master_member.database_id,)).next()[0])

    # @dispersu_auto_load.setter
    def __set_dispersy_auto_load(self, auto_load):
        """
        Sets the auto_load flag for this community.
        """
        assert isinstance(auto_load, bool)
        self._dispersy_database.execute(u"UPDATE community SET auto_load = ? WHERE master = ?",
                                        (1 if auto_load else 0, self._master_member.database_id))
    # .setter was introduced in Python 2.6
    dispersy_auto_load = property(__get_dispersy_auto_load, __set_dispersy_auto_load)

    @property
    def dispersy_sync_bloom_filter_error_rate(self):
        """
        The error rate that is allowed within the sync bloom filter.

        Having a higher error rate will allow for more items to be stored in the bloom filter,
        allowing more items to be syced with each sync interval.  Although this has the disadvantage
        that more false positives will occur.

        A false positive will mean that if A sends a dispersy-sync message to B, B will incorrectly
        believe that A already has certain messages.  Each message has -error rate- chance of being
        a false positive, and hence B will not be able to receive -error rate- percent of the
        messages in the system.

        This problem can be aleviated by having multiple bloom filters for each sync range with
        different prefixes.  Because bloom filters with different prefixes are extremely likely (the
        hash functions md5, sha1, shaxxx ensure this) to have false positives for different packets.
        Hence, having two of three different bloom filters will ensure you will get all messages,
        though it will take more rounds.

        @rtype: float
        """
        return 0.01

    @property
    def dispersy_sync_bloom_filter_redundancy(self):
        """
        The number of bloom filters, each with a unique prefix, that are used to represent one sync
        range.

        The effective error rate for a sync range then becomes redundancy * error_rate.

        @rtype: int
        """
        return 3

    @property
    def dispersy_sync_bloom_filter_bits(self):
        """
        The size in bits of this bloom filter.

        The sync bloom filter is part of the dispersy-introduction-request message and hence must
        fit within a single MTU.  There are several numbers that need to be taken into account.

        - A typical MTU is 1500 bytes

        - A typical IP header is 20 bytes.  However, the maximum IP header is 60 bytes (this
          includes information for VPN, tunnels, etc.)

        - The UDP header is 8 bytes

        - The dispersy header is 2 + 20 + 1 + 20 + 8 = 51 bytes (version, cid, type, member,
          global-time)

        - The signature is usually 60 bytes.  This depends on what public/private key was chosen.
          The current value is: self._my_member.signature_length
          
        - The other payload is 6 + 6 + 6 + 1 + 2 = 21 (destination-address, source-lan-address,
          source-wan-address, advice, identifier)
        
        - The sync payload uses 16 bytes to indicate the sync range and 4 bytes for the num_slices,
          bits_per_slice, and the prefix
        """
        return (1500 - 60 - 8 - 51 - self._my_member.signature_length - 21 - 16 - 4) * 8

    def dispersy_claim_sync_bloom_filter(self, identifier):
        """
        The bloom filter that should be sent this interval.

        Returns a (time_low, time_high, bloom_filter) tuple.  For the most recent bloom filter it is
        good practice to send 0 (zero) instead of time_high, this will ensure that messages newer
        than time_high are also retrieved.

        Bloom filters at index 0 indicates the most recent bloom filter range, while a higher number
        indicates an older range.
        """
        size = len(self._sync_ranges)
        index = int(abs(gauss(0, sqrt(size))))
        while index >= size:
            index = int(abs(gauss(0, sqrt(size))))

        if index == 0:
            sync_range = self._sync_ranges[index]
            return sync_range.time_low, 0, choice(sync_range.bloom_filters)

        else:
            newer_range, sync_range = self._sync_ranges[index - 1:index + 1]
            return sync_range.time_low, newer_range.time_low, choice(sync_range.bloom_filters)

    @property
    def dispersy_sync_response_limit(self):
        """
        The maximum number of bytes to send back per received dispersy-sync message.
        @rtype: int
        """
        return 5 * 1025

    @property
    def dispersy_missing_sequence_response_limit(self):
        """
        The maximum number of bytes to send back per received dispersy-missing-sequence message.
        @rtype: (int, int)
        """
        return 10 * 1025

    @property
    def dispersy_subjective_set_error_rate(self):
        """
        The error rate that is allowed within the subjective set bloom filter.

        Having a higher error rate will allow for more items to be stored in the bloom filter,
        allowing more public keys to be placed stored.  Although this has the disadvantage that more
        false positives will occur.

        A false positive will mean that it might be perceived that we included peer A in our
        subjective set while in fact we did not.  Hence more false positives will result in more
        incoming traffic that we ourselves will also store since it matches our subjective set.

        @rtype: float
        """
        return 0.0001

    @property
    def dispersy_subjective_set_bits(self):
        """
        The size in bits of this bloom filter.

        We want one dispersy-subjective-set message to fit within a single MTU.  There are several
        numbers that need to be taken into account.

        - A typical MTU is 1500 bytes

        - A typical IP header is 20 bytes.  However, the maximum IP header is 60 bytes (this
          includes information for VPN, tunnels, etc.)

        - The UDP header is 8 bytes

        - The dispersy header is 2 + 20 + 1 + 20 + 8 = 51 bytes (version, cid, type, member,
          global-time)

        - The signature is usually 60 bytes.  This depends on what public/private key was choosen.
          The current value is: self._my_member.signature_length

        - The dispersy-subjective-set message uses 1 byte to indicate the cluster and 3 bytes for
          the num_slices and bits_per_slice
        """
        return (1500 - 60 - 8 - 51 - self._my_member.signature_length - 1 - 3) * 8

    @property
    def cid(self):
        """
        The 20 byte sha1 digest of the public master key, in other words: the community identifier.
        @rtype: string
        """
        return self._cid

    @property
    def database_id(self):
        """
        The number used to identify this community in the local Dispersy database.
        @rtype: int or long
        """
        return self._database_id

    @property
    def master_member(self):
        """
        The community Member instance.
        @rtype: Member
        """
        return self._master_member

    @property
    def my_member(self):
        """
        Our own Member instance that is used to sign the messages that we create.
        @rtype: Member
        """
        return self._my_member

    @property
    def dispersy(self):
        """
        The Dispersy instance.
        @rtype: Dispersy
        """
        return self._dispersy

    @property
    def subjective_set_clusters(self):
        """
        The cluster values that this community supports.
        @rtype: [int]
        """
        return self._subjective_set_clusters

    @property
    def global_time(self):
        """
        The most recent global time.
        @rtype: int or long
        """
        return max(1, self._global_time)

    def unload_community(self):
        """
        Unload a single community.
        """
        self._dispersy.detach_community(self)

    def dispersy_start_walk(self):
        return self._dispersy.start_walk(self)

    def claim_global_time(self):
        """
        Increments the current global time by one and returns this value.
        @rtype: int or long
        """
        self._global_time += 1
        return self._global_time

    def update_global_time(self, global_time):
        """
        Increase the local global time if the given GLOBAL_TIME is larger.
        """
        self._global_time = max(self._global_time, global_time)

    def free_sync_range(self, global_times):
        """
        Update the sync ranges to reflect that previously stored messages, at the indicated
        global_times, are no longer stored.

        @param global_times: The global_time values for each message that has been removed from the
         database.
        @type global_time: [int or long]
        """
        assert isinstance(global_times, (tuple, list))
        assert len(global_times) > 0
        assert not filter(lambda x: not isinstance(x, (int, long)), global_times)

        if __debug__: dprint("freeing ", len(global_times), " messages")

        # update
        if __debug__: debug_time_high = 0
        for global_time in global_times:
            for sync_range in self._sync_ranges:
                if sync_range.time_low <= global_time:
                    sync_range.free()
                    if __debug__: dprint("free from [", sync_range.time_low, ":", debug_time_high if debug_time_high else "inf", "] @", global_time)
                    break
                if __debug__: debug_time_high = sync_range.time_low

        # remove completely freed ranges
        if __debug__:
            time_high = 0
            for sync_range in self._sync_ranges:
                if sync_range.space_freed >= sync_range.capacity - sync_range.space_remaining:
                    dprint("remove obsolete sync range [", sync_range.time_low, ":", time_high if time_high else "inf", "]")
                time_high = sync_range.time_low
        self._sync_ranges = [sync_range for sync_range in self._sync_ranges if sync_range.space_freed < sync_range.capacity - sync_range.space_remaining]

        # merge neighboring ranges
        if len(self._sync_ranges) > 1:
            for low_index in xrange(len(self._sync_ranges)-1, 0, -1):

                start = self._sync_ranges[low_index]
                end_index = -1
                used = start.capacity - start.space_remaining - start.space_freed
                if used == start.capacity:
                    continue

                for index in xrange(low_index-1, -1, -1):
                    current = self._sync_ranges[index]
                    current_used = current.capacity - current.space_remaining - current.space_freed
                    if current_used == current.capacity:
                        break
                    used += current_used
                    if used <= start.capacity:
                        end_index = index
                    else:
                        break

                if end_index >= 0:
                    time_high = self._sync_ranges[end_index - 1].time_low - 1 if end_index > 0 else self._time_high
                    if __debug__:
                        dprint("merge sync range [", self._sync_ranges[low_index].time_low, ":", time_high, "]")
                        dprint([dict(low=r.time_low, freed=r.space_freed, remaining=r.space_remaining) for r in self._sync_ranges], pprint=1)

                    self._sync_ranges[low_index].clear()
                    map(self._sync_ranges[low_index].add, (str(packet) for packet, in self._dispersy.database.execute(u"SELECT packet FROM sync WHERE community = ? AND global_time BETWEEN ? AND ?",
                                                                                                                      (self._database_id, self._sync_ranges[low_index].time_low, time_high))))
                    del self._sync_ranges[end_index:low_index]

                    if __debug__:
                        dprint([dict(low=r.time_low, freed=r.space_freed, remaining=r.space_remaining) for r in self._sync_ranges], pprint=1)

                    # break.  because the loop over low_index may be invalid now
                    break

    def update_sync_range(self, messages):
        """
        Update our local view of the global time and the sync ranges using the given messages.

        @param messages: The messages that need to update the global time and sync ranges.
        @type messages: [Message.Implementation]
        """
        assert isinstance(messages, list)
        assert len(messages) > 0

        if __debug__: dprint("updating ", len(messages), " messages")

        for message_index, message in zip(count(), sorted(messages, lambda a, b: a.distribution.global_time - b.distribution.global_time or cmp(a.packet, b.packet))):
            if __debug__: last_time_low = 0

            for index, sync_range in zip(count(), self._sync_ranges):
                if sync_range.time_low <= message.distribution.global_time:

                    # possibly add a new sync range
                    if sync_range.space_remaining <= sync_range.space_freed:
                        if message.distribution.global_time > self._time_high:
                            assert last_time_low == last_time_low if last_time_low else self._time_high
                            assert index == 0
                            sync_range = SyncRange(self._time_high + 1, self.dispersy_sync_bloom_filter_bits, self.dispersy_sync_bloom_filter_error_rate, self.dispersy_sync_bloom_filter_redundancy)
                            self._sync_ranges.insert(0, sync_range)
                            if __debug__: dprint("new ", sync_range.bloom_filters[0].capacity, " capacity filter created for range [", sync_range.time_low, ":inf]")

                    # add the packet
                    sync_range.add(message.packet)
                    if __debug__: dprint("add in [", sync_range.time_low, ":", last_time_low - 1 if last_time_low else "inf", "] ", message.name, "@", message.distribution.global_time, "; remaining: ", sync_range.space_remaining, " (", sync_range.space_remaining - sync_range.space_freed, " effectively)")
                    assert message.distribution.global_time >= sync_range.time_low
                    break

                if __debug__: last_time_low = sync_range.time_low
            self._time_high = max(self._time_high, message.distribution.global_time)
        self._global_time = max(self._global_time, self._time_high)

        # possibly split sync ranges
        while True:
            last_time_low = self._time_high + 1
            for index, sync_range in zip(count(), self._sync_ranges):
                if sync_range.space_remaining < sync_range.space_freed and sync_range.time_low < last_time_low:
                    assert last_time_low >= 0
                    assert index >= 0

                    # get all items in this range (from the database, and from this call to update_sync_range)
                    items = list(self._dispersy_database.execute(u"SELECT global_time, packet FROM sync WHERE community = ? AND global_time BETWEEN ? AND ? ORDER BY global_time, packet", (self.database_id, sync_range.time_low, last_time_low - 1)))
                    # split the current range
                    index_middle = int((len(items) + 1) / 2)
                    time_middle = items[index_middle][0]
                    # the middle index may not be the same as len(ITEMS)/2 because
                    # TIME_MIDDLE may occur any number of times in ITEMS.  It may even be
                    # that all elements in ITEMS are at TIME_MIDDLE.
                    for skew in xrange(1, index_middle + 1):
                        if items[index_middle-skew][0] != time_middle:
                            index_middle -= skew - 1
                            break
                        if len(items) > index_middle+skew and items[index_middle+skew][0] != time_middle:
                            index_middle += skew
                            break
                    else:
                        # did not break, meaning, every items in this sync range has the
                        # same global time.  we can not split this range, this will result
                        # in an increased chance for false positives
                        if __debug__: dprint("unable to split sync range [", sync_range.time_low, ":", last_time_low - 1, "] @", time_middle, " further because all items have the same global time", level="warning")
                        assert not filter(lambda x: not x[0] == time_middle, items)
                        index_middle = 0

                    if index_middle > 0:
                        time_middle = items[index_middle][0]

                        if __debug__: dprint("split [", sync_range.time_low, ":", last_time_low - 1, "] into [", sync_range.time_low, ":", time_middle - 1, "] and [", time_middle, ":", last_time_low - 1, "] with ", len(items[:index_middle]), " and ", len(items[index_middle:]), " items, respectively")
                        assert index_middle == 0 or items[index_middle-1][0] < items[index_middle][0]

                        # clear and fill range [sync_range.time_low:time_middle-1]
                        sync_range.clear()
                        map(sync_range.add, (str(packet) for _, packet in items[:index_middle]))
                        if __debug__:
                            for global_time, _, in items[:index_middle]:
                                dprint("re-add in [", sync_range.time_low, ":", time_middle - 1, "] @", global_time)
                                assert sync_range.time_low <= global_time < time_middle

                        # create and fill range [time_middle:last_time_low-1]
                        new_sync_range = SyncRange(time_middle, self.dispersy_sync_bloom_filter_bits, self.dispersy_sync_bloom_filter_error_rate, self.dispersy_sync_bloom_filter_redundancy)
                        self._sync_ranges.insert(index, new_sync_range)
                        map(new_sync_range.add, (str(packet) for _, packet in items[index_middle:]))
                        if __debug__:
                            for global_time, _, in items[index_middle:]:
                                dprint("re-add in [", new_sync_range.time_low, ":", last_time_low - 1, "] @", global_time)
                                assert new_sync_range.time_low <= global_time < last_time_low
                        break

                last_time_low = sync_range.time_low

            else:
                # did not break, meaning, we can not split any more sync ranges
                return

    def clear_subjective_set_cache(self, member, cluster, packet="", subjective_set=None):
        """
        Either remove or replace an entry in the subjective set cache.

        @param member: The member for who we want the subjective set.
        @type member: Member

        @param cluster: The cluster identifier.  Where 0 < cluster < 255.
        @type cluster: int

        @param packet: Optional.  The binary packet representing the dispersy-subjective-set message.
        @type packet: string

        @param subjective_set: Optional.  The subjective set.
        @type subjective_set: BloomFilter
        """
        assert isinstance(member, Member)
        assert isinstance(cluster, int)
        assert cluster in self._subjective_set_clusters, (cluster, self._subjective_set_clusters)
        assert isinstance(packet, str)
        assert subjective_set is None or isinstance(subjective_set, BloomFilter)
        assert (packet and subjective_set) or (not packet and not subjective_set)
        key = (member, cluster)
        if packet and subjective_set:
            self._subjective_sets[key] = SubjectiveSetCache(packet, subjective_set)
        else:
            del self._subjective_sets[key]

    def get_subjective_set_cache(self, member, cluster):
        """
        Returns the SubjectiveSetCache object for a certain member and cluster.

        This cache object contains two parameters: packet and subjective_set.  The packet parameter
        is a string containing the binary representation of the dispersy-subjective-set message.
        The subjective_set is a bloom_filter containing the subjective set.

        @param member: The member for who we want the subjective set.
        @type member: Member

        @param cluster: The cluster identifier.  Where 0 < cluster < 255.
        @type cluster: int

        @return: The cache object or None
        @rtype: SubjectiveSetCache or None
        """
        assert isinstance(member, Member)
        assert isinstance(cluster, int)
        assert cluster in self._subjective_set_clusters, (cluster, self._subjective_set_clusters)
        key = (member, cluster)
        if not key in self._subjective_sets:
            try:
                subjective_set_message_id = self.get_meta_message(u"dispersy-subjective-set").database_id
            except KeyError:
                # dispersy-subjective-set message is disabled
                return None

            # cache fail... fetch from database.  note that we will add all clusters in the cache
            # regardless of the requested cluster
            for packet, in self._dispersy_database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND meta_message = ?",
                                                           (self._database_id, member.database_id, subjective_set_message_id)):
                packet = str(packet)

                # check that this is the packet we are looking for, i.e. has the right cluster
                conversion = self.get_conversion(packet[:22])
                message = conversion.decode_message(("", -1), packet)
                tmp_key = (member, message.payload.cluster)
                if not tmp_key in self._subjective_sets:
                    self._subjective_sets[tmp_key] = SubjectiveSetCache(packet, message.payload.subjective_set)

        return self._subjective_sets.get(key)

    def get_subjective_set(self, member, cluster):
        """
        Returns the subjective set for a certain member and cluster.

        @param member: The member for who we want the subjective set.
        @type member: Member

        @param cluster: The cluster identifier.  Where 0 < cluster < 255.
        @type cluster: int

        @return: The subjective set bloom filter or None
        @rtype: BloomFilter or None
        """
        assert isinstance(member, Member)
        assert isinstance(cluster, int)
        assert cluster in self._subjective_set_clusters, (cluster, self._subjective_set_clusters)
        cache = self.get_subjective_set_cache(member, cluster)
        return cache.subjective_set if cache else None

    def get_subjective_sets(self, member):
        """
        Returns all subjective sets for a certain member.

        Each cluster that is used in this community will be represented in the result, however, when
        we are missing a subjective set the entry will be None.  In this case, the subjective set
        can be retrieved using a dispersy-missing-subjective-set message.

        @param member: The member for who we want the subjective sets.
        @type member: Member

        @return: A dictionary with all cluster/bloomfilter pairs
        @rtype: {cluster:bloom-filter} where bloom-filter may be None
        """
        assert isinstance(member, Member)
        return dict((cluster, self.get_subjective_set(member, cluster)) for cluster in self._subjective_set_clusters)

    def get_member(self, public_key):
        """
        Returns a Member instance associated with public_key.

        since we have the public_key, we can create this user when it didn't already exist.  Hence,
        this method always succeeds.

        @param public_key: The public key of the member we want to obtain.
        @type public_key: string

        @return: The Member instance associated with public_key.
        @rtype: Member

        @note: This returns -any- Member, it may not be a member that is part of this community.

        @todo: Since this method returns Members that are not specifically bound to any community,
         this method should be moved to Dispersy
        """
        assert isinstance(public_key, str)
        # note that this allows a security attack where someone might obtain a crypographic key that
        # has the same sha1 as the master member, however unlikely.  the only way to prevent this,
        # as far as we know, is to increase the size of the community identifier, for instance by
        # using sha256 instead of sha1.
        return Member.get_instance(public_key)

    def get_members_from_id(self, mid):
        """
        Returns zero or more Member instances associated with mid, where mid is the sha1 digest of a
        member public key.

        As we are using only 20 bytes to represent the actual member public key, this method may
        return multiple possible Member instances.  In this case, other ways must be used to figure
        out the correct Member instance.  For instance: if a signature or encryption is available,
        all Member instances could be used, but only one can succeed in verifying or decrypting.

        Since we may not have the public key associated to MID, this method may return an empty
        list.  In such a case it is sometimes possible to DelayPacketByMissingMember to obtain the
        public key.

        @param mid: The 20 byte sha1 digest indicating a member.
        @type mid: string

        @return: A list containing zero or more Member instances.
        @rtype: [Member]

        @note: This returns -any- Member, it may not be a member that is part of this community.

        @todo: Since this method returns Members that are not specifically bound to any community,
         this method should be moved to Dispersy
        """
        assert isinstance(mid, str)
        assert len(mid) == 20
        # note that this allows a security attack where someone might obtain a crypographic key that
        # has the same sha1 as the master member, however unlikely.  the only way to prevent this,
        # as far as we know, is to increase the size of the community identifier, for instance by
        # using sha256 instead of sha1.
        return [Member.get_instance(str(public_key))
                for public_key,
                in list(self._dispersy_database.execute(u"SELECT public_key FROM member WHERE mid = ?", (buffer(mid),)))
                if public_key]

    def get_members_from_address(self, address, verified=True):
        """
        Returns zero or more Member instances that are or have been reachable at address.

        Each member distributes dispersy-identity messages, these messages contain the address where
        this member is reachable or was reachable in the past.

        TODO: Currently we trust that the information in the dispersy-identity is correct.
        Obviously this is not always the case.  Hence we will need to verify the truth by contacting
        the peer at a certain address and performing a secure handshake.

        @param address: The address that we want members from.
        @type address: (str, int)

        @param verified: When True only verified members are returned. (TODO, currently this
         parameter is unused and all returned members are unverified)
        @type verified: bool

        @return: A list containing zero or more Member instances.
        @rtype: [Member]

        @note: This returns -any- Member, it may not be a member that is part of this community.

        @todo: Since this method returns Members that are not specifically bound to any community,
         this method should be moved to Dispersy
        """
        assert isinstance(address, tuple)
        assert len(address) == 2
        assert isinstance(address[0], str)
        assert isinstance(address[1], int)
        assert isinstance(verified, bool)
        if verified:
            # TODO we should not just trust this information, a member can put any address in their
            # dispersy-identity message.  The database should contain a column with a 'verified'
            # flag.  This flag is only set when a handshake was successful.
            sql = u"SELECT DISTINCT member.public_key FROM identity JOIN member ON member.id = identity.member WHERE identity.host = ? AND identity.port = ? -- AND verified = 1"
        else:
            sql = u"SELECT DISTINCT member.public_key FROM identity JOIN member ON member.id = identity.member WHERE identity.host = ? AND identity.port = ?"
        return [Member.get_instance(str(public_key)) for public_key, in list(self._dispersy_database.execute(sql, (unicode(address[0]), address[1])))]

    def get_conversion(self, prefix=None):
        """
        returns the conversion associated with prefix.

        prefix is an optional 22 byte sting.  Where the first byte is
        the dispersy version, the second byte is the community version
        and the last 20 bytes is the community identifier.

        When no prefix is given, i.e. prefix is None, then the default Conversion is returned.
        Conversions are assigned to a community using add_conversion().

        @param prefix: Optional prefix indicating a conversion.
        @type prefix: string

        @return A Conversion instance indicated by prefix or the default one.
        @rtype: Conversion
        """
        assert prefix is None or isinstance(prefix, str)
        assert prefix is None or len(prefix) == 22
        return self._conversions[prefix]

    def add_conversion(self, conversion, default=False):
        """
        Add a Conversion to the Community.

        A conversion instance converts between the internal Message structure and the on-the-wire
        message.

        When default is True the conversion is set to be the default conversion.  The default
        conversion is used (by default) when a message is implemented and no prefix is given.

        @param conversion: The new conversion instance.
        @type conversion: Conversion

        @param default: Indicating if this is to become the default conversion.
        @type default: bool
        """
        if __debug__:
            from conversion import Conversion
        assert isinstance(conversion, Conversion)
        assert isinstance(default, bool)
        assert not conversion.prefix in self._conversions
        if default:
            self._conversions[None] = conversion
        self._conversions[conversion.prefix] = conversion

    @documentation(Dispersy.get_message)
    def get_dispersy_message(self, member, global_time):
        return self._dispersy.get_message(self, member, global_time)

    @documentation(Dispersy.create_authorize)
    def create_dispersy_authorize(self, permission_triplets, sign_with_master=False, store=True, update=True, forward=True):
        return self._dispersy.create_authorize(self, permission_triplets, sign_with_master, store, update, forward)

    @documentation(Dispersy.create_revoke)
    def create_dispersy_revoke(self, permission_triplets, sign_with_master=False, store=True, update=True, forward=True):
        return self._dispersy.create_revoke(self, permission_triplets, sign_with_master, store, update, forward)

    @documentation(Dispersy.create_undo)
    def create_dispersy_undo(self, message, sign_with_master=False, store=True, update=True, forward=True):
        return self._dispersy.create_undo(self, message, sign_with_master, store, update, forward)

    @documentation(Dispersy.create_identity)
    def create_dispersy_identity(self, store=True, update=True):
        return self._dispersy.create_identity(self, store, update)

    @documentation(Dispersy.create_signature_request)
    def create_dispersy_signature_request(self, message, response_func, response_args=(), timeout=10.0, store=True, forward=True):
        return self._dispersy.create_signature_request(self, message, response_func, response_args, timeout, store, forward)

    @documentation(Dispersy.create_destroy_community)
    def create_dispersy_destroy_community(self, degree, sign_with_master=False, store=True, update=True, forward=True):
        return self._dispersy.create_destroy_community(self, degree, sign_with_master, store, update, forward)

    @documentation(Dispersy.create_subjective_set)
    def create_dispersy_subjective_set(self, cluster, members, reset=True, store=True, update=True, forward=True):
        return self._dispersy.create_subjective_set(self, cluster, members, reset, store, update, forward)

    @documentation(Dispersy.create_dynamic_settings)
    def create_dispersy_dynamic_settings(self, policies, sign_with_master=False, store=True, update=True, forward=True):
        return self._dispersy.create_dynamic_settings(self, policies, sign_with_master, store, update, forward)

    def dispersy_on_dynamic_settings(self, messages, initializing=False):
        return self._dispersy.on_dynamic_settings(self, messages, initializing)

    def dispersy_cleanup_community(self, message):
        """
        A dispersy-destroy-community message is received.

        Once a community is destroyed, it must be reclassified to ensure that it is not loaded in
        its regular form.  This method returns the class that the community will be reclassified
        into.  The default is either the SoftKilledCommunity or the HardKilledCommunity class,
        depending on the received dispersy-destroy-community message.

        Depending on the degree of the destroy message, we will need to cleanup in different ways.

         - soft-kill: The community is frozen.  Dispersy will retain the data it has obtained.
           However, no messages beyond the global-time of the dispersy-destroy-community message
           will be accepted.  Responses to dispersy-sync messages will be send like normal.

         - hard-kill: The community is destroyed.  Dispersy will throw away everything except the
           dispersy-destroy-community message and the authorize chain that is required to verify
           this message.  The community should also remove all its data and cleanup as much as
           possible.

        Similar to other on_... methods, this method may raise a DropMessage exception.  In this
        case the message will be ignored and no data is removed.  However, each dispersy-sync that
        is sent is likely to result in the same dispersy-destroy-community message to be received.

        @param address: The address from where we received this message.
        @type address: (string, int)

        @param message: The received message.
        @type message: Message.Implementation

        @rtype: Community class
        """
        # override to implement community cleanup
        if message.payload.is_soft_kill:
            raise NotImplementedError()

        elif message.payload.is_hard_kill:
            return HardKilledCommunity

    def dispersy_malicious_member_detected(self, member, packets):
        """
        Proof has been found that MEMBER is malicious

        @param member: The malicious member.
        @type member: Member

        @param packets: One or more packets proving that the member is malicious.  All packets must
         be associated to the same community.
        @type packets: [Packet]
        """
        pass

    def get_meta_message(self, name):
        """
        Returns the meta message by its name.

        @param name: The name of the message.
        @type name: unicode

        @return: The meta message.
        @rtype: Message

        @raise KeyError: When there is no meta message by that name.
        """
        assert isinstance(name, unicode)
        if __debug__:
            if not name in self._meta_messages:
                dprint("this community does not support the ", name, " message", level="warning")
        return self._meta_messages[name]

    def get_meta_messages(self):
        """
        Returns all meta messages.

        @return: The meta messages.
        @rtype: [Message]
        """
        return self._meta_messages.values()

    def initiate_meta_messages(self):
        """
        Create the meta messages for one community instance.

        This method is called once for each community when it is created.  The resulting meta
        messages can be obtained by either get_meta_message(name) or get_meta_messages().

        To distinct the meta messages that the community provides from those that Dispersy provides,
        none of the messages may have a name that starts with 'dispersy-'.

        @return: The new meta messages.
        @rtype: [Message]
        """
        raise NotImplementedError()

    def initiate_conversions(self):
        """
        Create the Conversion instances for this community instance.

        This method is called once for each community when it is created.  The resulting Conversion
        instances can be obtained using the get_conversion(prefix) method.

        Returns a list with all Conversion instances that this community will support.  The last
        item in the list will be used as the default conversion.

        @rtype: [Conversion]
        """
        raise NotImplementedError()

class HardKilledCommunity(Community):
    def _initialize_meta_messages(self):
        super(HardKilledCommunity, self)._initialize_meta_messages()

        # remove all messages that we no longer need
        meta_messages = self._meta_messages
        self._meta_messages = {}
        for name in [u"dispersy-introduction-request",
                     u"dispersy-introduction-response",
                     u"dispersy-identity",
                     u"dispersy-missing-identity"]:
            self._meta_messages[name] = meta_messages[name]

    @property
    def dispersy_candidate_request_initial_delay(self):
        # we no longer send candidate messages
        return 0.0

    @property
    def dispersy_candidate_request_interval(self):
        # we no longer send candidate messages
        return 0.0

    @property
    def dispersy_candidate_cleanup_age_threshold(self):
        # all candidated can be removed
        return 0.0

    @property
    def dispersy_sync_initial_delay(self):
        # we no longer send sync messages
        return 0.0

    @property
    def dispersy_sync_interval(self):
        # we no longer send sync messages
        return 0.0

    def initiate_meta_messages(self):
        # there are no community messages
        return []

    def initiate_conversions(self):
        # TODO we will not be able to use this conversion because the community version will not
        # match
        return [DefaultConversion(self)]

    def get_conversion(self, prefix=None):
        if not prefix in self._conversions:

            # the dispersy version MUST BE available.  Currently we
            # only support \x00: BinaryConversion
            if prefix[0] == "\x00":
                self._conversions[prefix] = BinaryConversion(self, prefix[1])

            else:
                raise KeyError("Unknown conversion")

            # use highest version as default
            if None in self._conversions:
                if self._conversions[None].version < self._conversions[prefix].version:
                    self._conversions[None] = self._conversions[prefix]
            else:
                self._conversions[None] = self._conversions[prefix]

        return self._conversions[prefix]

    if __debug__:
        def get_meta_message(self, name):
            # we do not want to dprint when name is not found (since many messages are disabled in
            # this Community
            assert isinstance(name, unicode)
            return self._meta_messages[name]
