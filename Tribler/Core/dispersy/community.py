# Python 2.5 features
from __future__ import with_statement

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

from authentication import NoAuthentication, MemberAuthentication, MultiMemberAuthentication
from bloomfilter import BloomFilter
from conversion import BinaryConversion, DefaultConversion
from crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from decorator import documentation
from destination import CommunityDestination, AddressDestination
from dispersy import Dispersy
from dispersydatabase import DispersyDatabase
from distribution import FullSyncDistribution, LastSyncDistribution, DirectDistribution
from encoding import encode
from member import Private, ElevatedMasterMember, MasterMember, MyMember, Member
from message import Message, DropMessage
from resolution import PublicResolution
from timeline import Timeline

if __debug__:
    from dprint import dprint

class SyncRange(object):
    def __init__(self, time_low, bits, error_rate, redundancy=3):
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

    def free(self):
        self.space_freed += 1
        assert self.space_freed <= self.capacity - self.space_remaining, "May never free more than added"

    def clear(self):
        self.space_freed = 0
        self.space_remaining = self.capacity
        for bloom_filter in self.bloom_filters:
            bloom_filter.clear()

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

        @param args: optional argumets that are passed to the community constructor.
        @type args: tuple

        @param kargs: optional keyword arguments that are passed to the community constructor.
        @type args: dictionary

        @return: The created community instance.
        @rtype: Community
        """
        assert isinstance(my_member, MyMember), my_member
        ec = ec_generate_key(u"high")
        master_public_key = ec_to_public_bin(ec)
        master_private_key = ec_to_private_bin(ec)
        cid = sha1(master_public_key).digest()

        database = DispersyDatabase.get_instance()
        with database as execute:
            execute(u"INSERT INTO community (user, classification, cid, public_key) VALUES(?, ?, ?, ?)", (my_member.database_id, cls.get_classification(), buffer(cid), buffer(master_public_key)))
            database_id = database.last_insert_rowid
            execute(u"INSERT INTO user (mid, public_key) VALUES(?, ?)", (buffer(cid), buffer(master_public_key)))
            execute(u"INSERT INTO key (public_key, private_key) VALUES(?, ?)", (buffer(master_public_key), buffer(master_private_key)))
            execute(u"INSERT INTO candidate (community, host, port, incoming_time, outgoing_time) SELECT ?, host, port, incoming_time, outgoing_time FROM candidate WHERE community = 0", (database_id,))

        # new community instance
        community = cls.load_community(cid, master_public_key, *args, **kargs)

        # create the dispersy-identity for the master member
        meta = community.get_meta_message(u"dispersy-identity")
        message = meta.implement(meta.authentication.implement(community.master_member),
                                 meta.distribution.implement(community.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(("0.0.0.0", 0)))
        community.dispersy.store_update_forward([message], True, False, True)

        # create the dispersy-identity for my member
        community.create_dispersy_identity()

        # authorize MY_MEMBER for each message
        permission_triplets = []
        for message in community.get_meta_messages():
            if not isinstance(message.resolution, PublicResolution):
                for allowed in (u"authorize", u"revoke", u"permit"):
                    permission_triplets.append((my_member, message, allowed))
        if permission_triplets:
            community.create_dispersy_authorize(permission_triplets, sign_with_master=True)

        return community

    @classmethod
    def join_community(cls, cid, master_public_key, my_member, *args, **kargs):
        """
        Join an existing community.

        Once you have discovered an existing community, i.e. you have obtained the public master key
        from a community, you can join this community.

        Joining a community does not mean that you obtain permissions in that community, those will
        need to be granted by another member who is allowed to do so.  However, it will let you
        receive, send, and disseminate messages that do not require any permission to use.

        @param cid: The community identifier, i.e. the sha1 digest of
        the master_public_key.
        @type cid: string

        @param master_public_key: The public key of the master member of the community that is to be
         joined.  This may be an empty sting.
        @type master_public_key: string

        @param my_member: The Member that will be granted Permit, Authorize, and Revoke for all
         messages.
        @type my_member: Member

        @param args: optional argumets that are passed to the
        community constructor.
        @type args: tuple

        @param kargs: optional keyword arguments that are passed to
        the community constructor.
        @type args: dictionary

        @return: The created community instance.
        @rtype: Community

        @todo: we should probably change MASTER_PUBLIC_KEY to require a master member instance, or the cid
         that we want to join.
        """
        assert isinstance(cid, str)
        assert len(cid) == 20
        assert isinstance(master_public_key, str)
        assert not master_public_key or cid == sha1(master_public_key).digest()
        assert isinstance(my_member, MyMember)
        if __debug__: dprint(cid.encode("HEX"))
        database = DispersyDatabase.get_instance()
        database.execute(u"INSERT INTO community(user, classification, cid, public_key) VALUES(?, ?, ?, ?)",
                         (my_member.database_id, cls.get_classification(), buffer(cid), buffer(master_public_key)))

        # new community instance
        community = cls.load_community(cid, master_public_key, *args, **kargs)

        # send out my initial dispersy-identity
        community.create_dispersy_identity()

        return community

    @classmethod
    def load_communities(cls, *args, **kargs):
        """
        Load all joined or created communities of this type.

        Typically the load_communities is called when the main application is launched.  This will
        ensure that all communities are loaded and attached to Dispersy.

        @return: A list with zero or more Community instances.
        @rtype: list
        """
        database = DispersyDatabase.get_instance()
        return [cls.load_community(str(cid), str(master_public_key), *args, **kargs)
                for cid, master_public_key
                in list(database.execute(u"SELECT cid, public_key FROM community WHERE classification = ?", (cls.get_classification(),)))]

    @classmethod
    def load_community(cls, cid, master_public_key, *args, **kargs):
        """
        Load a single community.

        Will raise a ValueError exception when cid is unavailable.

        @param cid: The community identifier, i.e. the sha1 digest of the master_public_key.
        @type cid: string

        @param master_public_key: The community identifier, i.e. the public key of the community
         master member.  This may be an empty string.
        @type cid: string
        """
        assert isinstance(cid, str)
        assert len(cid) == 20
        assert isinstance(master_public_key, str)
        assert not master_public_key or cid == sha1(master_public_key).digest()
        if __debug__: dprint(cid.encode("HEX"))
        community = cls(cid, master_public_key, *args, **kargs)

        # tell dispersy that there is a new community
        community._dispersy.attach_community(community)

        return community

    @classmethod
    def unload_communities(cls):
        """
        Unload all communities that have the same classification as cls.
        """
        if __debug__: dprint(self._cid.encode("HEX"))
        dispersy = Dispersy.get_instance()
        classification = cls.get_classification()
        for community in dispersy.get_communities():
            if community.get_classification() == classification:
                community.unload_community()

    def __init__(self, cid, master_public_key):
        """
        Initialize a community.

        Generally a new community is created using create_community.  Or an existing community is
        loaded using load_communities.  These two methods prepare and call this __init__ method.

        @param cid: The community identifier, i.e. the sha1 digest of the master_public_key.
        @type cid: string

        @param master_public_key: The community identifier, i.e. the public key of the community
         master member.  This may be an empty string.
        @type cid: string
        """
        assert isinstance(cid, str)
        assert len(cid) == 20
        assert isinstance(master_public_key, str)
        assert not master_public_key or cid == sha1(master_public_key).digest()
        if __debug__: dprint(cid.encode("HEX"))

        # dispersy
        self._dispersy = Dispersy.get_instance()
        self._dispersy_database = DispersyDatabase.get_instance()

        # obtain some generic data from the database
        for database_id, db_master_public_key, user_public_key in self._dispersy_database.execute(u"""
            SELECT community.id, community.public_key, user.public_key
            FROM community
            LEFT JOIN user ON community.user = user.id
            WHERE community.cid == ?
            LIMIT 1""", (buffer(cid),)):
            # the database returns <buffer> types, we use the binary <str> type internally
            db_master_public_key = str(db_master_public_key)
            user_public_key = str(user_public_key)

            if not master_public_key:
                master_public_key = db_master_public_key
                break

            elif db_master_public_key == master_public_key:
                break

        else:
            raise ValueError(u"Community not found in database [" + cid.encode("HEX") + "]")

        # instance members
        self._cid = cid
        self._database_id = database_id
        self._my_member = MyMember.get_instance(user_public_key)
        self._master_member = None
        self._initialize_master_member(master_public_key)
        assert isinstance(self._database_id, (int, long))
        assert isinstance(self._my_member, MyMember)
        assert self._master_member is None or isinstance(self._master_member, MasterMember)

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

        # initial timeline.  the timeline will keep track of member permissions
        self._timeline = Timeline()
        self._initialize_timeline()

        # the subjective sets.  the dictionary contains all our, most recent, subjective sets per
        # cluster.  These are made when a meta message uses the SubjectiveDestination policy.
        # self._subjective_sets = self.get_subjective_sets(self._my_member)

    def _initialize_master_member(self, master_public_key):
        if master_public_key:
            try:
                master_private_key, = self._dispersy_database.execute(u"SELECT private_key FROM key WHERE public_key = ?", (buffer(master_public_key),)).next()
            except StopIteration:
                # we only have the public part of the master member
                self._master_member = MasterMember.get_instance(master_public_key)
            else:
                # we have the private part of the master member
                self._master_member = ElevatedMasterMember.get_instance(master_public_key, str(master_private_key))

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

    def _initialize_sync_ranges(self):
        assert isinstance(self._sync_ranges, list)
        assert len(self._sync_ranges) == 0
        assert self._global_time == 0
        assert self._time_high == 1

        # ensure that at least one bloom filter exists
        sync_range = SyncRange(1, self.dispersy_sync_bloom_filter_bits, self.dispersy_sync_bloom_filter_error_rate)
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
                    sync_range = SyncRange(current_global_time, self.dispersy_sync_bloom_filter_bits, self.dispersy_sync_bloom_filter_error_rate)
                    self._sync_ranges.insert(0, sync_range)

                map(sync_range.add, packets)
                if __debug__: dprint("add in [", sync_range.time_low, ":inf] ", len(packets), " packets @", current_global_time, "; remaining: ", sync_range.space_remaining)

                packets = [str(packet)]
                current_global_time = global_time

        if packets:
            if len(packets) > sync_range.space_remaining:
                sync_range = SyncRange(global_time, self.dispersy_sync_bloom_filter_bits, self.dispersy_sync_bloom_filter_error_rate)
                self._sync_ranges.insert(0, sync_range)

            map(sync_range.add, packets)
            if __debug__: dprint("add in [", sync_range.time_low, ":inf] ", len(packets), " packets @", current_global_time, "; remaining: ", sync_range.space_remaining)

        # todo: maybe we can add a callback or event notifier to give a progress indication while
        # loading millions of packets...

    def _initialize_timeline(self):
        # load existing permissions from the database
        try:
            authorize = self.get_meta_message(u"dispersy-authorize")
            revoke = self.get_meta_message(u"dispersy-revoke")

        except KeyError:
            if __debug__: dprint("unable to load permissions from database [could not obtain 'dispersy-authorize' or 'dispersy-revoke']", level="warning")

        else:
            mapping = {authorize.database_id:authorize.handle_callback, revoke.database_id:revoke.handle_callback}
            with self._dispersy_database as execute:
                for name, packet in execute(u"SELECT name, packet FROM sync WHERE community = ? AND name IN (?, ?) ORDER BY global_time, packet", (self.database_id, authorize.database_id, revoke.database_id)):
                    packet = str(packet)
                    # TODO: when a packet conversion fails we must drop something, and preferably check
                    # all messages in the database again...
                    message = self.get_conversion(packet[:22]).decode_message(("", -1), packet)
                    mapping[name]([message])

    # @property
    def __get_dispersy_auto_load(self):
        """
        When True, this community will automatically be loaded when a packet is received.
        """
        # currently we grab it directly from the database
        return bool(self._dispersy_database.execute(u"SELECT auto_load FROM community WHERE cid = ? AND (public_key = '' OR public_key = ?)",
                                                    (buffer(self._cid), buffer(self._master_member.public_key if self._master_member else ""))).next()[0])

    # @dispersu_auto_load.setter
    def __set_dispersy_auto_load(self, auto_load):
        """
        Sets the auto_load flag for this community.
        """
        assert isinstance(auto_load, bool)
        self._dispersy_database.execute(u"UPDATE community SET auto_load = ? WHERE cid = ? AND (public_key = '' OR public_key = ?)",
                                        (1 if auto_load else 0, buffer(self._cid), buffer(self._master_member.public_key if self._master_member else "")))
    # .setter was introduced in Python 2.6
    dispersy_auto_load = property(__get_dispersy_auto_load, __set_dispersy_auto_load)

    @property
    def dispersy_candidate_request_initial_delay(self):
        return 0.1

    @property
    def dispersy_candidate_request_interval(self):
        """
        The interval between sending dispersy-candidate-request messages.
        """
        return 60.0

    @property
    def dispersy_candidate_age_range(self):
        """
        The valid age range, in seconds, that an entry in the candidate table must be in order to be
        forwarded in a dispersy-candidate-request or dispersy-candidate-response message.
        @rtype: (float, float)
        """
        return (0.0, 300.0)

    @property
    def dispersy_candidate_request_member_count(self):
        """
        The number of members that a dispersy-candidate-request message is sent to each interval.
        @rtype: int
        """
        return 10

    @property
    def dispersy_candidate_request_destination_diff_range(self):
        """
        The difference between last-incoming and last-outgoing time, for the selection of a
        destination node, when sending a dispersy-candidate-request message.
        @rtype: (float, float)
        """
        return (10.0, 30.0)

    @property
    def dispersy_candidate_request_destination_age_range(self):
        """
        The difference between the last-incoming and current time, for the selection of a
        destination node, when sending a dispersy-candidate-request message.
        @rtype: (float, float)
        """
        return (300.0, 900.0)

    @property
    def dispersy_candidate_cleanup_age_threshold(self):
        """
        Once an entry in the candidate table becomes older than the threshold, the entry is deleted
        from the database.
        @rtype: float
        """
        # 24 hours ~ 86400.0 seconds
        return 86400.0

    @property
    def dispersy_candidate_limit(self):
        """
        The number of candidates to place in a dispersy-candidate request and response.

        We want one dispersy-candidate-request/response message to fit within a single MTU.  There
        are several numbers that need to be taken into account.

        - A typical MTU is 1500 bytes

        - A typical IP header is 20 bytes

        - The maximum IP header is 60 bytes (this includes information for VPN, tunnels, etc.)

        - The UDP header is 8 bytes

        - The dispersy header is 2 + 20 + 1 + 20 + 8 = 51 bytes (version, cid, type, user,
          global-time)

        - The signature is usually 60 bytes.  This depends on what public/private key was choosen.
          The current value is: self._my_member.signature_length

        - The dispersy-candidate-request/response message payload is 6 + 6 + 2 = 14 bytes (contains
          my-external-address, their-external-address, our-conversion-version)

        - Each candidate in the payload requires 4 + 2 + 2 bytes (host, port, age)
        """
        return (1500 - 60 - 8 - 51 - self._my_member.signature_length - 14) // 8

    @property
    def dispersy_sync_initial_delay(self):
        return 10.0

    @property
    def dispersy_sync_interval(self):
        """
        The interval between sending dispersy-sync messages.
        @rtype: float
        """
        return 30.0

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
    def dispersy_sync_bloom_filter_bits(self):
        """
        The size in bits of this bloom filter.

        We want one dispersy-sync message to fit within a single MTU.  There are several numbers
        that need to be taken into account.

        - A typical MTU is 1500 bytes

        - A typical IP header is 20 bytes

        - The maximum IP header is 60 bytes (this includes information for VPN, tunnels, etc.)

        - The UDP header is 8 bytes

        - The dispersy header is 2 + 20 + 1 + 20 + 8 = 51 bytes (version, cid, type, user,
          global-time)

        - The signature is usually 60 bytes.  This depends on what public/private key was choosen.
          The current value is: self._my_member.signature_length

        - The dispersy-sync message uses 16 bytes to indicate the sync range and 4 bytes for the
          num_slices, bits_per_slice, and the prefix
        """
        return (1500 - 60 - 8 - 51 - self._my_member.signature_length - 16 - 4) * 8

    @property
    def dispersy_sync_bloom_filters(self):
        """
        The bloom filters that should be sent this interval.

        The list that is returned must contain (time_low, time_high, bloom_filter) tuples.  For the
        most recent bloom filter it is good practice to send 0 (zero) instead of time_high, this
        will ensure that messages newer than time_high are also retrieved.

        Bloom filters at index 0 indicates the most recent bloom filter range, while a higher number
        indicates an older range.

        It sounds reasonable to ensure that the more recent ranges are returned more frequently.
        Several strategied can be used:

         1. Always return index 0 and pick another index at random.

         2. Always return index 0 and pick another index using a gaussian probability distribution
            favoring the more recent ranges.

         3. Use a gaussion probability distribution favoring the more recent ranges.

        The default is option 3.  However, each community is free to implement this how they see
        fit.

        @note: The returned indexes need to exist.
        @rtype [(time_low, time_high, bloom_filter)]
        """
        size = len(self._sync_ranges)
        index = int(abs(gauss(0, sqrt(size))))
        while index >= size:
            index = int(abs(gauss(0, sqrt(size))))

        if index == 0:
            sync_range = self._sync_ranges[index]
            return [(sync_range.time_low, 0, choice(sync_range.bloom_filters))]

        else:
            newer_range, sync_range = self._sync_ranges[index - 1:index + 1]
            return [(sync_range.time_low, newer_range.time_low, choice(sync_range.bloom_filters))]

    @property
    def dispersy_sync_member_count(self):
        """
        The number of members that are selected each time a dispersy-sync message is send.

        Any value higher than 1 has a chance to result in duplicate incoming packets, as multiple
        recipients can provide the same missing data.

        @rtype: int
        """
        return 1

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
        The community MasterMember instance.
        @rtype: MasterMember
        """
        return self._master_member

    @property
    def my_member(self):
        """
        Our own MyMember instance that is used to sign the messages that we create.
        @rtype: MyMember
        """
        return self._my_member

    @property
    def dispersy(self):
        """
        The Dispersy instance.
        @rtype: Dispersy
        """
        return self._dispersy

    def unload_community(self):
        """
        Unload a single community.
        """
        self._dispersy.detach_community(self)

    @property
    def global_time(self):
        """
        The most recent global time.
        @rtype: int or long
        """
        return max(1, self._global_time)

    def claim_global_time(self):
        """
        Increments the current global time by one and returns this value.
        @rtype: int or long
        """
        self._global_time += 1
        return self._global_time

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
            for low_index in xrange(len(self._sync_ranges)-1, 1, -1):

                start = self._sync_ranges[low_index]
                end_index = -1
                used = start.capacity - start.space_remaining - start.space_freed
                if used == start.capacity:
                    continue

                for index in xrange(low_index-1, 1, -1):
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

                    self._sync_ranges[low_index].clear()
                    map(self._sync_ranges[low_index].add, (str(packet) for packet, in self._dispersy.database.execute(u"SELECT packet FROM sync WHERE community = ? AND global_time BETWEEN ? AND ?",
                                                                                                                      (self._database_id, self._sync_ranges[low_index].time_low, time_high))))
                    del self._sync_ranges[end_index:low_index]

                    # break.  the loop over low_index may be invalid now
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
            last_time_low = 0

            for index, sync_range in zip(count(), self._sync_ranges):
                if sync_range.time_low <= message.distribution.global_time:

                    if sync_range.space_remaining <= 0:
                        if message.distribution.global_time > self._time_high:
                            assert last_time_low == last_time_low if last_time_low else self._time_high
                            assert index == 0
                            # add a new sync range
                            sync_range = SyncRange(self._time_high + 1, self.dispersy_sync_bloom_filter_bits, self.dispersy_sync_bloom_filter_error_rate)
                            self._sync_ranges.insert(0, sync_range)
                            if __debug__: dprint("new ", sync_range.bloom_filters[0].capacity, " capacity filter created for range [", sync_range.time_low, ":inf]")

                        else:
                            assert last_time_low >= 0
                            assert index >= 0
                            if last_time_low == 0:
                                last_time_low = self._time_high + 1

                            # get all items in this range (from the database, and from this call to update_sync_range)
                            items = list(self._dispersy_database.execute(u"SELECT global_time, packet FROM sync WHERE community = ? AND global_time BETWEEN ? AND ?", (self.database_id, sync_range.time_low, last_time_low - 1)))
                            items.extend((msg.distribution.global_time, msg.packet) for msg in messages[:message_index] if sync_range.time_low <= msg.distribution.global_time < last_time_low)
                            items.sort()
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
                                # same global time.  we can not split this range, false positives
                                # will be the result.
                                if __debug__: dprint("unable to split sync range [", sync_range.time_low, ":", last_time_low - 1, "] @", time_middle, " further because all items have the same global time", level="warning")
                                assert not filter(lambda x: not x[0] == time_middle, items)
                                index_middle = 0

                            if index_middle:
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
                                new_sync_range = SyncRange(time_middle, self.dispersy_sync_bloom_filter_bits, self.dispersy_sync_bloom_filter_error_rate)
                                self._sync_ranges.insert(index, new_sync_range)
                                map(new_sync_range.add, (str(packet) for _, packet in items[index_middle:]))
                                if __debug__:
                                    for global_time, _, in items[index_middle:]:
                                        dprint("re-add in [", new_sync_range.time_low, ":", last_time_low - 1, "] @", global_time)
                                        assert new_sync_range.time_low <= global_time < last_time_low

                                # make sure we use the correct sync range to add the message
                                if message.distribution.global_time >= new_sync_range.time_low:
                                    sync_range = new_sync_range
                                else:
                                    last_time_low = new_sync_range.time_low

                    sync_range.add(message.packet)
                    if __debug__: dprint("add in [", sync_range.time_low, ":", last_time_low - 1 if last_time_low else "inf", "] ", message.name, "@", message.distribution.global_time, "; remaining: ", sync_range.space_remaining)
                    assert message.distribution.global_time >= sync_range.time_low
                    break

                last_time_low = sync_range.time_low
            self._time_high = max(self._time_high, message.distribution.global_time)
        self._global_time = max(self._global_time, self._time_high)

    def get_subjective_set(self, member, cluster):
        """
        Returns the subjective set for a certain member and cluster.

        @param member: The member for who we want the subjective set.
        @type member: Member

        @param cluster: The cluster identifier.  Where 0 < cluster < 255.
        @type cluster: int

        @return: The bloom filter associated to the member and cluster or None
        @rtype: BloomFilter or None

        @raise KeyError: When the subjective set is not known.
        """
        assert isinstance(member, Member)
        assert isinstance(cluster, int)
        assert 0 < cluster < 2^8, "CLUSTER must fit in one byte"
        # assert cluster in self._subjective_sets
        subjective_set = self.get_subjective_sets(member)
        return subjective_set[cluster]
        # if not member in self._subjective_sets:
        #     self._subjective_sets[member] = self.get_subjective_sets(member)
        # return self._subjective_sets[cluster]

    def get_subjective_sets(self, member):
        """
        Returns all subjective sets for a certain member.

        We can return an empty dictionary when no sets are available for this member.

        @param member: The member for who we want the subjective set.
        @type member: Member

        @return: A dictionary with all cluster / bloom filter pairs
        @rtype: {cluster:bloom-filter}
        """
        assert isinstance(member, Member)

        existing_sets = {}

        try:
            meta_message = self.get_meta_message(u"dispersy-subjective-set")

        except KeyError:
            # dispersy-subjective-set message is disabled
            pass

        else:

            # retrieve all the subjective sets that were created by member
            sql = u"SELECT sync.packet FROM sync WHERE community = ? AND user = ? AND name = ?"

            # dprint(sql)
            # dprint((self._database_id, member.database_id, meta_message.database_id))

            for packet, in self._dispersy_database.execute(sql, (self._database_id, member.database_id, meta_message.database_id)):
                assert isinstance(packet, buffer)
                packet = str(packet)
                conversion = self.get_conversion(packet[:22])
                message = conversion.decode_message(("", -1), packet)
                assert message.name == "dispersy-subjective-set"
                assert not message.payload.cluster in existing_sets
                existing_sets[message.payload.cluster] = message.payload.subjective_set

        # # either use an existing or create a new bloom filter for each subjective set (cluster)
        # # that we are using
        # subjective_sets = {}
        # for meta_message in self._meta_messages.iter_values():
        #     if isinstance(meta_message.destination, SubjectiveDestination):
        #         cluster = meta_message.destination.cluster
        #         if not cluster in subjective_sets:
        #             if cluster in existing_sets:
        #                 subjective_sets[cluster] = existing_sets[cluster]
        #             elif create_new:
        #                 subjective_sets[cluster] = BloomFilter(500, 0.1)

        # # 3. return the sets.  this will be stored in self._subjective_sets for later reference.
        # return subjective_sets

        return existing_sets

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
        return [Member.get_instance(str(public_key)) for public_key, in list(self._dispersy_database.execute(u"SELECT public_key FROM user WHERE mid = ?", (buffer(mid),)))]

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
            # flag.  This flag is only set when a handshake was successfull.
            sql = u"SELECT public_key FROM user WHERE host = ? AND port = ? -- AND verified = 1"
        else:
            sql = u"SELECT public_key FROM user WHERE host = ? AND port = ?"
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

    @documentation(Dispersy.create_authorize)
    def create_dispersy_authorize(self, permission_triplets, sign_with_master=False, store=True, update=True, forward=True):
        return self._dispersy.create_authorize(self, permission_triplets, sign_with_master, store, update, forward)

    @documentation(Dispersy.create_revoke)
    def create_dispersy_revoke(self, permission_triplets, sign_with_master=False, store=True, update=True, forward=True):
        return self._dispersy.create_revoke(self, permission_triplets, sign_with_master, store, update, forward)

    @documentation(Dispersy.create_identity)
    def create_dispersy_identity(self, store=True, forward=True):
        return self._dispersy.create_identity(self, store, forward)

    @documentation(Dispersy.create_signature_request)
    def create_dispersy_signature_request(self, message, response_func, response_args=(), timeout=10.0, store=True, forward=True):
        return self._dispersy.create_signature_request(self, message, response_func, response_args, timeout, store, forward)

#     @documentation(Dispersy.create_similarity)
#     def create_dispersy_similarity(self, message, keywords, store=True, update=True, forward=True):
#         return self._dispersy.create_similarity(self, message, keywords, store, update, forward)

    @documentation(Dispersy.create_destroy_community)
    def create_dispersy_destroy_community(self, degree, sign_with_master=False, store=True, update=True, forward=True):
        return self._dispersy.create_destroy_community(self, degree, sign_with_master, store, update, forward)

    @documentation(Dispersy.create_subjective_set)
    def create_dispersy_subjective_set(self, cluster, members, reset=True, store=True, update=True, forward=True):
        return self._dispersy.create_subjective_set(self, cluster, members, reset, store, update, forward)

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
                dprint("this community does not support the dispersy-subjective-set message", level="warning")
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
        for name in [u"dispersy-candidate-request",     # we still receive this message
                     u"dispersy-candidate-response",    # we still send this message
                     u"dispersy-identity",              # we still receive this message for new peers who send us
                                                        # candidate requests
                     u"dispersy-identity-request",      # we still send this to obtain identity messages
                     u"dispersy-sync"]:                 # we still need to spread the destroy-community message
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
