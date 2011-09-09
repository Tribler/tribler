# Python 2.5 features
from __future__ import with_statement

"""
The Distributed Permission System, or Dispersy, is a platform to simplify the design of distributed
communities.  At the heart of Dispersy lies a simple identity and message handling system where each
community and each user is uniquely and securely identified using elliptic curve cryptography.

Since we can not guarantee each member to be online all the time, messages that they created at one
point in time should be able to retain their meaning even when the member is off-line.  This can be
achieved by signing such messages and having them propagated though other nodes in the network.
Unfortunately, this increases the strain on these other nodes, which we try to alleviate using
specific message policies, which will be described below.

Following from this, we can easily package each message into one UDP packet to simplify
connectability problems since UDP packets are much easier to pass though NAT's and firewalls.

Earlier we hinted that messages can have different policies.  A message has the following four
different policies, and each policy defines how a specific part of the message should be handled.

 - Authentication defines if the message is signed, and if so, by how many members.

 - Resolution defines how the permission system should resolve conflicts between messages.

 - Distribution defines if the message is send once or if it should be gossipped around.  In the
   latter case, it can also define how many messages should be kept in the network.

 - Destination defines to whom the message should be send or gossipped.

To ensure that every node handles a messages in the same way, i.e. has the same policies associated
to each message, a message exists in two stages.  The meta-message and the implemented-message
stage.  Each message has one meta-message associated to it and tells us how the message is supposed
to be handled.  When a message is send or received an implementation is made from the meta-message
that contains information specifically for that message.  For example: a meta-message could have the
member-authentication-policy that tells us that the message must be signed by a member but only the
an implemented-message will have data and this signature.

A community can tweak the policies and how they behave by changing the parameters that the policies
supply.  Aside from the four policies, each meta-message also defines the community that it is part
of, the name it uses as an internal identifier, and the class that will contain the payload.
"""

from datetime import datetime
from hashlib import sha1
from itertools import groupby, islice, count
from os.path import abspath
from random import random, shuffle
from sys import maxint
from threading import Lock

from authentication import NoAuthentication, MemberAuthentication, MultiMemberAuthentication
from bloomfilter import BloomFilter
from bootstrap import get_bootstrap_addresses
from callback import Callback
from candidate import Candidate
from crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from destination import CommunityDestination, AddressDestination, MemberDestination, SubjectiveDestination
from dispersydatabase import DispersyDatabase
from distribution import SyncDistribution, FullSyncDistribution, LastSyncDistribution, DirectDistribution
from member import Member
from message import Packet, Message
from message import DropPacket, DelayPacket
from message import DropMessage, DelayMessage, DelayMessageByProof, DelayMessageBySequence, DelayMessageBySubjectiveSet
from payload import AuthorizePayload, RevokePayload, UndoPayload
from payload import CandidateRequestPayload, CandidateResponsePayload
from payload import DestroyCommunityPayload
from payload import DynamicSettingsPayload
from payload import IdentityPayload, MissingIdentityPayload
from payload import MissingMessagePayload
from payload import MissingSequencePayload, MissingProofPayload
from payload import SignatureRequestPayload, SignatureResponsePayload
from payload import SubjectiveSetPayload, MissingSubjectiveSetPayload
from payload import SyncPayload
from resolution import PublicResolution, LinearResolution
from singleton import Singleton
from trigger import TriggerCallback, TriggerPacket, TriggerMessage

if __debug__:
    from dprint import dprint
    from time import clock

class DummySocket(object):
    """
    A dummy socket class.

    When Dispersy starts it does not yet have a socket object, however, it may (under certain
    conditions) start sending packets anyway.

    To avoid problems we initialize the Dispersy socket to this dummy object that will do nothing
    but throw away all packets it is supposed to sent.
    """
    def send(address, data):
        if __debug__: dprint("Thrown away ", len(data), " bytes worth of outgoing data", level="warning")

class Statistics(object):
    def __init__(self):
        self._drop = {}
        self._delay = {}
        self._success = {}
        self._outgoing = {}
        self._sequence_number = 0
        self._total_up = 0
        self._total_down = 0

    def reset(self):
        """
        Returns, and subsequently removes, all statistics.
        """
        try:
            return {"drop":self._drop,
                    "delay":self._delay,
                    "success":self._success,
                    "outgoing":self._outgoing,
                    "sequence_number":self._sequence_number,
                    "total_up": self._total_up,
                    "total_down": self._total_down}

        finally:
            self._drop = {}
            self._delay = {}
            self._success = {}
            self._outgoing = {}
            self._sequence_number += 1
            self._total_up = 0
            self._total_down = 0

    def drop(self, key, bytes, count=1):
        """
        Called when an incoming packet or message failed a check and was dropped.
        """
        assert isinstance(key, (str, unicode))
        assert isinstance(bytes, (int, long))
        assert isinstance(count, (int, long))
        a, b = self._drop.get(key, (0, 0))
        self._drop[key] = (a+count, b+bytes)

    def delay(self, key, bytes, count=1):
        """
        Called when an incoming packet or message was delayed.
        """
        assert isinstance(key, (str, unicode))
        assert isinstance(bytes, (int, long))
        assert isinstance(count, (int, long))
        a, b = self._delay.get(key, (0, 0))
        self._delay[key] = (a+count, b+bytes)

    def success(self, key, bytes, count=1):
        """
        Called when an incoming message was accepted.
        """
        assert isinstance(key, (str, unicode))
        assert isinstance(bytes, (int, long))
        assert isinstance(count, (int, long))
        a, b = self._success.get(key, (0, 0))
        self._success[key] = (a+count, b+bytes)

    def outgoing(self, address, key, bytes, count=1):
        """
        Called when a message send using the _send(...) method
        """
        assert isinstance(address, tuple)
        assert len(address) == 2
        assert isinstance(address[0], str)
        assert isinstance(address[1], int)
        assert isinstance(key, (str, unicode))
        assert isinstance(bytes, (int, long))
        assert isinstance(count, (int, long))
        subdict = self._outgoing.setdefault(address, {})
        a, b = subdict.get(key, (0, 0))
        subdict[key] = (a+count, b+bytes)

    def increment_total_up(self, bytes):
        assert isinstance(bytes, (int, long))
        self._total_up += bytes

    def increment_total_down(self, bytes):
        assert isinstance(bytes, (int, long))
        self._total_down += bytes

class Dispersy(Singleton):
    """
    The Dispersy class provides the interface to all Dispersy related commands, managing the in- and
    outgoing data for, possibly, multiple communities.
    """
    def __init__(self, callback, working_directory):
        """
        Initialize the Dispersy singleton instance.

        Currently we use the rawserver to schedule events.  This may change in the future to offload
        all data processing to a different thread.  The only mechanism used from the rawserver is
        the add_task method.

        @param callback: Object for callback scheduling.
        @type rawserver: Callback

        @param working_directory: The directory where all files should be stored.
        @type working_directory: unicode
        """
        assert isinstance(callback, Callback)
        assert isinstance(working_directory, unicode)

        # the raw server
        self._callback = callback

        # batch caching incoming packets
        self._batch_cache = {}
        if __debug__:
            self._debug_batch_cache_performance = {}

        # where we store all data
        self._working_directory = abspath(working_directory)

        # our data storage
        self._database = DispersyDatabase.get_instance(working_directory)

        # our external address
        try:
            host, = self._database.execute(u"SELECT value FROM option WHERE key = 'my_external_ip' LIMIT 1").next()
            host = str(host)
        except StopIteration:
            host = "0.0.0.0"

        try:
            port, = self._database.execute(u"SELECT value FROM option WHERE key = 'my_external_port' LIMIT 1").next()
        except StopIteration:
            port = 0

        if __debug__: dprint("my external address is ", host, ":", port)
        self._my_external_address = (host, port)
        self._external_address_votes = {self._my_external_address:set()}
        self.external_address_vote(self._my_external_address, ("", -1))

        # bootstrap peers
        self._bootstrap_addresses = get_bootstrap_addresses()
        for peer in self._bootstrap_addresses:
            if peer is None:
                self._callback.register(self._retry_bootstrap_addresses)
                self._bootstrap_addresses = [peer for peer in self._bootstrap_addresses if peer]
                break

        # all available communities.  cid:Community pairs.
        self._communities = {}

        # outgoing communication
        self._socket = DummySocket()

        # triggers for incoming messages
        self._triggers = []

        self._check_distribution_batch_map = {DirectDistribution:self._check_direct_distribution_batch,
                                              FullSyncDistribution:self._check_full_sync_distribution_batch,
                                              LastSyncDistribution:self._check_last_sync_distribution_batch}

        # # check connectability periodically
        # self._callback.register(self._periodically_connectability)

        # cleanup the database periodically
        self._callback.register(self._periodically_cleanup_database)

        # commit changes to the database periodically
        self._callback.register(self._watchdog)

        # statistics...
        self._statistics = Statistics()

    def _retry_bootstrap_addresses(self):
        """
        One or more bootstrap addresses could not be retrieved.

        The first 30 seconds we will attempt to resolve the addresses once every second.  If we did
        not succeed after 30 seconds will will retry once every 30 seconds until we succeed.
        """
        if __debug__: dprint("unable to resolve all bootstrap addresses", level="warning")
        for counter in count(1):
            yield 1.0 if counter < 30 else 30.0
            if __debug__: dprint("attempt #", counter, level="warning")
            addresses = get_bootstrap_addresses()
            for address in addresses:
                if address is None:
                    break
            else:
                if __debug__: dprint("resolved all bootstrap addresses")
                self._bootstrap_addresses = addresses
                break

    @property
    def working_directory(self):
        """
        The full directory path where all dispersy related files are stored.
        @rtype: unicode
        """
        return self._working_directory

    # @property
    def __get_socket(self):
        """
        The socket object used to send packets.
        @rtype: Object with a send(address, data) method
        """
        return self._socket
    # @socket.setter
    def __set_socket(self, socket):
        """
        Set a socket object.
        @param socket: The socket object.
        @type socket: Object with a send(address, data) method
        """
        self._socket = socket
        self.external_address_vote(socket.get_address(), ("", -1))
    # .setter was introduced in Python 2.6
    socket = property(__get_socket, __set_socket)

    @property
    def external_address(self):
        """
        The external address where we believe that we can be found.

        Our external address is determined by majority voting.  Each time when we receive a message
        that contains anothers opinion about our external address, we take this into account.  The
        address with the most votes wins.

        Votes can be added by calling the external_address_vote(...) method.

        Usually these votes are received through dispersy-candidate-request and
        dispersy-candidate-response messages.

        @rtype: (str, int)
        """
        return self._my_external_address

    @property
    def callback(self):
        return self._callback

    @property
    def database(self):
        """
        The Dispersy database singleton.
        @rtype: DispersyDatabase
        """
        return self._database

    def initiate_meta_messages(self, community):
        """
        Create the meta messages that Dispersy uses.

        This method is called once for each community when it is created.  The resulting meta
        messages can be obtained by either community.get_meta_message(name) or
        community.get_meta_messages().

        Since these meta messages will be used along side the meta messages that each community
        provides, all message names are prefixed with 'dispersy-' to ensure that the names are
        unique.

        @param community: The community that will get the messages.
        @type community: Community

        @return: The new meta messages.
        @rtype: [Message]
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        return [Message(community, u"dispersy-candidate-request", MemberAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), CandidateRequestPayload(), self._generic_timeline_check, self.on_candidate_request, delay=0.0),
                Message(community, u"dispersy-candidate-response", MemberAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), CandidateResponsePayload(), self._generic_timeline_check, self.on_candidate_response, delay=2.5),
                Message(community, u"dispersy-identity", MemberAuthentication(encoding="bin"), PublicResolution(), LastSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=16, history_size=1), CommunityDestination(node_count=0), IdentityPayload(), self._generic_timeline_check, self.on_identity, priority=512, delay=1.0),
                Message(community, u"dispersy-sync", MemberAuthentication(), PublicResolution(), DirectDistribution(), CommunityDestination(node_count=community.dispersy_sync_member_count), SyncPayload(), self.check_sync, self.on_sync, delay=0.0),
                Message(community, u"dispersy-signature-request", NoAuthentication(), PublicResolution(), DirectDistribution(), MemberDestination(), SignatureRequestPayload(), self.check_signature_request, self.on_signature_request, delay=0.0),
                Message(community, u"dispersy-signature-response", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), SignatureResponsePayload(), self._generic_timeline_check, self.on_signature_response, delay=0.0),
                Message(community, u"dispersy-authorize", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=10), AuthorizePayload(), self._generic_timeline_check, self.on_authorize, priority=504, delay=1.0),
                Message(community, u"dispersy-revoke", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=10), RevokePayload(), self._generic_timeline_check, self.on_revoke, priority=504, delay=1.0),
                Message(community, u"dispersy-undo", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=10), UndoPayload(), self.check_undo, self.on_undo, priority=500, delay=1.0),
                Message(community, u"dispersy-destroy-community", MemberAuthentication(), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=192), CommunityDestination(node_count=50), DestroyCommunityPayload(), self._generic_timeline_check, self.on_destroy_community, delay=0.0),
                Message(community, u"dispersy-subjective-set", MemberAuthentication(), PublicResolution(), LastSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=16, history_size=1), CommunityDestination(node_count=0), SubjectiveSetPayload(), self._generic_timeline_check, self.on_subjective_set, delay=1.0),
                Message(community, u"dispersy-dynamic-settings", MemberAuthentication(), LinearResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"ASC", priority=191), CommunityDestination(node_count=10), DynamicSettingsPayload(), self._generic_timeline_check, self.on_dynamic_settings, delay=0.0),

                #
                # when something is missing, a dispersy-missing-... message can be used to request
                # it from another peer
                #

                # when we have a member id (20 byte sha1 of the public key) but not the public key
                Message(community, u"dispersy-missing-identity", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), MissingIdentityPayload(), self._generic_timeline_check, self.on_missing_identity, delay=0.0),

                # when we are missing one or more SyncDistribution messages in a certain sequence
                Message(community, u"dispersy-missing-sequence", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), MissingSequencePayload(), self._generic_timeline_check, self.on_missing_sequence, delay=0.0),

                # when we have a reference to a message that we do not have.  a reference consists
                # of the community identifier, the member identifier, and the global time
                Message(community, u"dispersy-missing-message", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), MissingMessagePayload(), self._generic_timeline_check, self.on_missing_message, delay=0.0),

                # when we are missing the subjective set, with a specific cluster, from a member
                Message(community, u"dispersy-missing-subjective-set", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), MissingSubjectiveSetPayload(), self._generic_timeline_check, self.on_missing_subjective_set, delay=0.0),

                # when we might be missing a dispersy-authorize message
                Message(community, u"dispersy-missing-proof", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), MissingProofPayload(), self._generic_timeline_check, self.on_missing_proof, delay=0.0),

                # when we are missing one or more LastSyncDistribution messages from a single member
                # ... so far we do not need a generic missing-last message.  unfortunately all
                # ... messages that it could replace contain payload specific things that make it
                # ... difficult, if not impossible, to replace
                # Message(community, u"dispersy-missing-last", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), MissingLastPayload(), self.check_missing_last, self.on_missing_last, delay=0.0),
                ]

    @staticmethod
    def _rawserver_task_id(community, prefix):
        """
        Periodically sending sync and candidate messages requires a rawserver tast to be identified
        per community.  To ensure that each community is uniquely idntified we use both the
        community id and the memory address id(community).

        This may still give problems when detaching and attaching (i.e. because of a reclassify).
        But it is the best we can do at this point.
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(prefix, str)
        return "-".join((prefix, str(id(community)), community.cid.encode("HEX")))

    def attach_community(self, community):
        """
        Add a community to the Dispersy instance.

        Each community must be known to Dispersy, otherwise an incoming message will not be able to
        be passed along to it's associated community.

        In general this method is called from the Community.__init__(...) method.

        @param community: The community that will be added.
        @type community: Community
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert not community.cid in self._communities
        if __debug__: dprint(community.cid.encode("HEX"), " ", community.get_classification())
        self._communities[community.cid] = community

        # periodically send dispery-sync messages
        if __debug__: dprint("start in ", community.dispersy_sync_initial_delay, " every ", community.dispersy_sync_interval, " seconds call _periodically_create_sync")
        self._callback.register(self._periodically_create_sync, (community,), delay=community.dispersy_sync_initial_delay, id_=self._rawserver_task_id(community, "id:sync"))

        # periodically send dispery-candidate-request messages
        if __debug__: dprint("start in ", community.dispersy_candidate_request_initial_delay, " every ", community.dispersy_candidate_request_interval, " seconds call _periodically_create_candidate_request")
        self._callback.register(self._periodically_create_candidate_request, (community,), delay=community.dispersy_candidate_request_initial_delay, id_=self._rawserver_task_id(community, "id:candidate"))

    def detach_community(self, community):
        """
        Remove an attached community from the Dispersy instance.

        Once a community is detached it will no longer receive incoming messages.  When the
        community is marked as auto_load it will be loaded, using community.load_community(...),
        when a message for this community is received.

        @param community: The community that will be added.
        @type community: Community
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert community.cid in self._communities
        if __debug__: dprint(community.cid.encode("HEX"), " ", community.get_classification())
        self._callback.unregister(self._rawserver_task_id(community, "id:sync"))
        self._callback.unregister(self._rawserver_task_id(community, "id:candidate"))
        del self._communities[community.cid]

    def reclassify_community(self, source, destination):
        """
        Change a community classification.

        Each community has a classification that dictates what source code is handling this
        community.  By default the classification of a community is the unicode name of the class in
        the source code.

        In some cases it may be usefull to change the classification, for instance: if community A
        has a subclass community B, where B has similar but reduced capabilities, we could
        reclassify B to A at some point and keep all messages collected so far while using the
        increased capabilities of community A.

        @param source: The community that will be reclassified.  This must be either a Community
         instance (when the community is loaded) or a Member instance giving the master member (when
         the community is not loaded).
        @type source: Community or Member

        @param destination: The new community classification.  This must be a Community class.
        @type destination: Community class
        """
        if __debug__:
            from community import Community
        assert isinstance(source, (Community, Member))
        assert issubclass(destination, Community)

        if isinstance(source, Member):
            if __debug__: dprint("reclassify ??? -> ", destination.get_classification())
            master = source

        else:
            if __debug__: dprint("reclassify ", source.get_classification(), " -> ", destination.get_classification())
            master = source.master_member
            source.unload_community()

        self._database.execute(u"UPDATE community SET classification = ? WHERE master = ?",
                               (destination.get_classification(), master.database_id))
        assert self._database.changes == 1
        return destination.load_community(master)

    def has_community(self, cid):
        """
        Returns True when there is a community CID.
        """
        return cid in self._communities

    def get_community(self, cid, load=False, auto_load=True):
        """
        Returns a community by its community id.

        The community id, or cid, is the binary representation of the public key of the master
        member for the community.

        When the community is available but not currently loaded it will be automatically loaded
        when (a) the load parameter is True or (b) the auto_load parameter is True and the auto_load
        flag for this community is True (this flag is set in the database).

        @param cid: The community identifier.
        @type cid: string

        @param load: When True, will load the community when available and not yet loaded.
        @type load: bool

        @param auto_load: When True, will load the community when available, the auto_load flag is
         True, and, not yet loaded.
        @type load: bool

        @warning: It is possible, however unlikely, that multiple communities will have the same
         cid.  This is currently not handled.
        """
        assert isinstance(cid, str)
        assert len(cid) == 20
        assert isinstance(load, bool)
        assert isinstance(auto_load, bool)

        if not cid in self._communities:
            try:
                # did we load this community at one point and set it to auto-load?
                classification, auto_load_flag, master_public_key = self._database.execute(u"SELECT community.classification, community.auto_load, member.public_key FROM community JOIN member ON member.id = community.master WHERE mid = ?",
                                                                                           (buffer(cid),)).next()

            except StopIteration:
                pass

            else:
                if load or (auto_load and auto_load_flag):

                    def recursive_subclasses(cls):
                        l = set()
                        for subcls in cls.__subclasses__():
                            l.add(subcls)
                            l.update(recursive_subclasses(subcls))
                        return l

                    # todo: get some other mechanism to obtain the class from classification
                    from community import Community

                    # master_public_key may be None
                    if master_public_key:
                        master_public_key = str(master_public_key)
                        master = Member.get_instance(str(master_public_key))
                    else:
                        master = Member.get_instance(cid, public_key_available=False)

                    # attempt to load this community
                    for cls in recursive_subclasses(Community):
                        if classification == cls.get_classification():
                            self._communities[cid] = cls.load_community(master)
                            break

                    else:
                        if __debug__: dprint("Failed to obtain class [", classification, "]", level="warning")

        return self._communities[cid]

    def get_communities(self):
        """
        Returns a list with all known Community instances.
        """
        return self._communities.values()

    def get_message(self, community, member, global_time):
        """
        Returns a Member.Implementation instance uniquely identified by its community, member, and
        global_time.

        Returns None if this message is not in the local database.
        """
        try:
            packet, = self._database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                             (community.database_id, member.database_id, global_time)).next()
        except StopIteration:
            return None
        else:
            return community.get_conversion(packet[:22]).decode_message(("", -1), packet)

    def external_address_vote(self, address, voter_address):
        """
        Add one vote and possibly re-determine our external address.

        Our external address is determined by majority voting.  Each time when we receive a message
        that contains anothers opinion about our external address, we take this into account.  The
        address with the most votes wins.

        Usually these votes are received through dispersy-candidate-request and
        dispersy-candidate-response messages.

        @param address: The external address that the voter believes us to have.
        @type address: (str, int)

        @param voter_address: The address of the voter.
        @type voter_address: (str, int)
        """
        assert isinstance(address, tuple)
        assert len(address) == 2
        assert isinstance(address[0], str)
        assert isinstance(address[1], int)
        assert isinstance(voter_address, tuple)
        assert len(voter_address) == 2
        assert isinstance(voter_address[0], str)
        assert isinstance(voter_address[1], int)
        if self._is_valid_external_address(address):
            if not address in self._external_address_votes:
                self._external_address_votes[address] = set()
            self._external_address_votes[address].add(voter_address)

            # change when new vote count equal or higher than old address vote count
            if self._my_external_address != address and len(self._external_address_votes[address]) >= len(self._external_address_votes[self._my_external_address]):
                if __debug__: dprint("Update my external address: ", self._my_external_address, " -> ", address)
                self._my_external_address = address
                self._database.execute(u"REPLACE INTO option (key, value) VALUES ('my_external_ip', ?)", (unicode(address[0]),))
                self._database.execute(u"REPLACE INTO option (key, value) VALUES ('my_external_port', ?)", (address[1],))

                # notify all communities that our external address has changed.
                for community in self._communities.itervalues():
                    community.create_dispersy_identity()

    def _check_identical_payload_with_different_signature(self, message):
        """
        There is a possibility that a message is created that contains exactly the same payload
        but has a different signature.

        This can occur when a message is created, forwarded, and for some reason the database is
        reset.  The next time that the client starts the exact same message may be generated.
        However, because EC sigantures contain a random element the signature will be different.

        This results in continues transfers because the bloom filters identify the two messages
        as different while the community/member/global_time triplet is the same.

        To solve this, we will silently replace one message with the other.  We choose to keep
        the message with the highest binary value while destroying the one with the lower binary
        value.

        To further optimize, we will add both messages to our bloom filter whenever we detect
        this problem.  This will ensure that we do not needlessly receive the 'invalid' message
        until the bloom filter is synced with the database again.

        Returns False when the message is not a duplicate with anything in the database.
        Otherwise returns True when the message is a duplicate and must be dropped.
        """
        # fetch the duplicate binary packet from the database
        try:
            packet_id, packet = self._database.execute(u"SELECT id, packet FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                       (message.community.database_id, message.authentication.member.database_id, message.distribution.global_time)).next()
        except StopIteration:
            # we are checking two messages just received in the same batch
            # process the message
            return False

        else:
            packet = str(packet)
            if packet == message.packet:
                # exact duplicates, do NOT process the message
                pass

            else:
                signature_length = message.authentication.member.signature_length
                if packet[:signature_length] == message.packet[:signature_length]:
                    # the message payload is binary unique (only the signature is different)
                    if __debug__: dprint("received identical message with different signature [member:", message.authentication.member.database_id, "; @", message.distribution.global_time, "]", level="warning")

                    if packet < message.packet:
                        # replace our current message with the other one
                        self._database.execute(u"UPDATE sync SET packet = ? WHERE community = ? AND member = ? AND global_time = ?",
                                               (buffer(message.packet), message.community.database_id, message.authentication.member.database_id, message.distribution.global_time))

                    # add the newly received message.packet to the bloom filter
                    message.community.update_sync_range([message])

                else:
                    if __debug__: dprint("received message with duplicate community/member/global-time triplet.  possibly malicious behavior", level="warning")

                # TODO: if we decide that this is malicious behavior, handle it (note that this code
                # is checked into release-5.3.x while the declare_malicious_member code is currently
                # only in the mainbranch.
                #
                # else:
                #     # the message payload is different while having the same
                #     # community/member/global-time triplet.  this is considered malicious behavior
                #     for packet_meta in message.community.get_meta_messages():
                #         if packet_meta.database_id == name_id:
                #             self.declare_malicious_member(message.authentication.member, [message, Packet(packet_meta, packet, packet_id)])
                #             break

        # do NOT process the message
        return True

    def _check_full_sync_distribution_batch(self, messages):
        """
        Ensure that we do not yet have the messages and that, if sequence numbers are enabled, we
        are not missing any previous messages.

        This method is called when a batch of messages with the FullSyncDistribution policy is
        received.  Duplicate messages will yield DropMessage.  And if enable_sequence_number is
        True, missing messages will yield the DelayMessageBySequence exception.

        @param messages: The messages that are to be checked.
        @type message: [Message.Implementation]

        @return: A generator with messages, DropMessage, or DelayMessageBySequence instances
        @rtype: [Message.Implementation|DropMessage|DelayMessageBySequence]
        """
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert not filter(lambda x: not isinstance(x, Message.Implementation), messages)
        assert not filter(lambda x: not x.community == messages[0].community, messages), "All messages need to be from the same community"
        assert not filter(lambda x: not x.meta == messages[0].meta, messages), "All messages need to have the same meta"

        # a message is considered unique when (creator, global-time), i.r. (authentication.member,
        # distribution.global_time), is unique.
        unique = set()
        execute = self._database.execute
        enable_sequence_number = messages[0].meta.distribution.enable_sequence_number

        # sort the messages by their (1) global_time and (2) binary packet
        messages = sorted(messages, lambda a, b: a.distribution.global_time - b.distribution.global_time or cmp(a.packet, b.packet))

        if enable_sequence_number:
            # obtain the highest sequence_number from the database
            highest = {}
            for message in messages:
                if not message.authentication.member in highest:
                    seq, = execute(u"SELECT COUNT(1) FROM sync WHERE member = ? AND sync.meta_message = ?",
                                   (message.authentication.member.database_id, message.database_id)).next()
                    highest[message.authentication.member] = seq

            # all messages must follow the sequence_number order
            for message in messages:
                key = (message.authentication.member, message.distribution.global_time)
                if key in unique:
                    yield DropMessage(message, "duplicate message by member^global_time (1)")

                else:
                    unique.add(key)
                    seq = highest[message.authentication.member]

                    if seq >= message.distribution.sequence_number:
                        # we already have this message (drop)
                        # TODO: something similar to _check_identical_payload_with_different_signature can occur...
                        yield DropMessage(message, "duplicate message by sequence_number (1)")

                    elif seq + 1 == message.distribution.sequence_number:
                        # we have the previous message, check for duplicates based on community,
                        # member, and global_time
                        try:
                            execute(u"SELECT 1 FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                    (message.community.database_id, message.authentication.member.database_id, message.distribution.global_time)).next()

                        except StopIteration:
                            # we accept this message
                            highest[message.authentication.member] += 1
                            yield message

                        else:
                            # we have the previous message (drop)
                            if self._check_identical_payload_with_different_signature(message):
                                yield DropMessage(message, "duplicate message by global_time (1)")

                    else:
                        # we do not have the previous message (delay and request)
                        yield DelayMessageBySequence(message, seq+1, message.distribution.sequence_number-1)

        else:
            for message in messages:
                key = (message.authentication.member, message.distribution.global_time)
                if key in unique:
                    yield DropMessage(message, "duplicate message by member^global_time (2)")

                else:
                    unique.add(key)

                    # check for duplicates based on community, member, and global_time
                    try:
                        execute(u"SELECT 1 FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                (message.community.database_id, message.authentication.member.database_id, message.distribution.global_time)).next()

                    except StopIteration:
                        # we accept this message
                        yield message

                    else:
                        # we have the previous message (drop)
                        if self._check_identical_payload_with_different_signature(message):
                            yield DropMessage(message, "duplicate message by global_time (2)")

    def _check_last_sync_distribution_batch(self, messages):
        """
        Check that the messages do not violate any database consistency rules.

        This method is called when a batch of messages with the LastSyncDistribution policy is
        received.  A iterator will be returned where each element is either: DropMessage (for
        duplicate and old messages), DelayMessage (for messages that requires something before they
        can be processed), or Message.Implementation when the message does not violate any rules.

        The rules:

         - The combination community, member, global_time must be unique.

         - When sequence numbers are enabled, the message with the previous sequence number must be
           present (either in MESSAGES or in the database).

         - When the MemberAuthentication policy is used: the message owner may not have more than
           history_size messages in the database at any one time.  Hence, if this limit is reached
           and the new message is older than the older message that is already available, it is
           dropped.

         - When the MultiMemberAuthentication policy is used: the members that signed the message
           may not have more than history_size messages in the database at any one time.  Hence, if
           this limit is reached and the new message is older than the older message that is already
           available, it is dropped.  Note that the signature order is not important.

        @param messages: The messages that are to be checked.
        @type message: [Message.Implementation]

        @return: A generator with messages, DropMessage, or DelayMessageBySequence instances
        @rtype: [Message.Implementation|DropMessage|DelayMessageBySequence]
        """
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert not filter(lambda x: not isinstance(x, Message.Implementation), messages)
        assert not filter(lambda x: not x.community == messages[0].community, messages), "All messages need to be from the same community"
        assert not filter(lambda x: not x.meta == messages[0].meta, messages), "All messages need to have the same meta"
        assert not filter(lambda x: not isinstance(x.authentication, (MemberAuthentication.Implementation, MultiMemberAuthentication.Implementation)), messages)

        def check_member_and_global_time(unique, times, message):
            """
            The member + global_time combination must always be unique in the database
            """
            assert isinstance(unique, set)
            assert isinstance(times, dict)
            assert isinstance(message, Message.Implementation)
            assert isinstance(message.distribution, LastSyncDistribution.Implementation)

            key = (message.authentication.member, message.distribution.global_time)
            if key in unique:
                return DropMessage(message, "already processed message by member^global_time")

            else:
                unique.add(key)

                if message.authentication.member in times:
                    tim = times[message.authentication.member]
                else:
                    tim = [global_time for global_time, in self._database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?",
                                                                                  (message.community.database_id, message.authentication.member.database_id, message.database_id))]
                    assert len(tim) <= message.distribution.history_size
                    times[message.authentication.member] = tim

                if message.distribution.global_time in tim and self._check_identical_payload_with_different_signature(message):
                    return DropMessage(message, "duplicate message by member^global_time (3)")

                elif len(tim) >= message.distribution.history_size and min(tim) > message.distribution.global_time:
                    # we have newer messages (drop)

                    # if the history_size is one, we can send that on message back because
                    # apparently the sender does not have this message yet
                    if message.distribution.history_size == 1:
                        try:
                            packet, = self._database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? ORDER BY global_time DESC LIMIT 1",
                                                             (message.community.database_id, message.authentication.member.database_id)).next()
                        except StopIteration:
                            # TODO can still fail when packet is in one of the received messages
                            # from this batch.
                            pass
                        else:
                            self._send([message.address], [str(packet)], u"-sequence-")

                    return DropMessage(message, "old message by member^global_time")


                else:
                    # we accept this message
                    tim.append(message.distribution.global_time)
                    return message

        def check_multi_member_and_global_time(unique, times, message):
            """
            No other message may exist with this message.authentication.members / global_time
            combination, regardless of the ordering of the members
            """
            assert isinstance(unique, set)
            assert isinstance(times, dict)
            assert isinstance(message, Message.Implementation)
            assert isinstance(message.authentication, MultiMemberAuthentication.Implementation)

            key = (message.authentication.member, message.distribution.global_time)
            if key in unique:
                return DropMessage(message, "already processed message by member^global_time")

            else:
                unique.add(key)

                members = tuple(sorted(member.database_id for member in message.authentication.members))
                key = members + (message.distribution.global_time,)
                if key in unique:
                    return DropMessage(message, "already processed message by members^global_time")

                else:
                    unique.add(key)

                    # ensure that the community / member / global_time is always unique
                    try:
                        self._database.execute(u"SELECT 1 FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                               (message.community.database_id, message.authentication.member.database_id, message.distribution.global_time)).next()
                    except StopIteration:
                        pass
                    else:
                        # we have the previous message (drop)
                        if self._check_identical_payload_with_different_signature(message):
                            return DropMessage(message, "duplicate message by member^global_time (4)")

                    if members in times:
                        tim = times[members]

                    else:
                        # the next query obtains a list with all global times that we have in the
                        # database for all message.meta messages that were signed by
                        # message.authentication.members where the order of signing is not taken
                        # into account.
                        tim = [global_time
                               for count, global_time
                               in self._database.execute(u"""
                               SELECT COUNT(*), sync.global_time
                               FROM sync
                               JOIN reference_member_sync ON reference_member_sync.sync = sync.id
                               WHERE sync.community = ? AND sync.meta_message = ? AND reference_member_sync.member IN (%s)
                               GROUP BY sync.id
                               """ % ", ".join("?" for _ in xrange(len(members))),
                                          (message.community.database_id, message.database_id) + members)
                               if count == message.authentication.count]
                        times[members] = tim

                    if message.distribution.global_time in tim and self._check_identical_payload_with_different_signature(message):
                        # we have the previous message (drop)
                        return DropMessage(message, "duplicate message by members^global_time")

                    elif len(tim) >= message.distribution.history_size and min(tim) > message.distribution.global_time:
                        # we have newer messages (drop)

                        # if the history_size is one, we can sent that on message back because
                        # apparently the sender does not have this message yet
                        if message.distribution.history_size == 1:
                            assert len(tim) == 1
                            packets = [packet
                                       for count, packet
                                       in self._database.execute(u"""
                                       SELECT COUNT(*), sync.packet
                                       FROM sync
                                       JOIN reference_member_sync ON reference_member_sync.sync = sync.id
                                       WHERE sync.community = ? AND sync.global_time = ? AND sync.meta_message = ? AND reference_member_sync.member IN (%s)
                                       GROUP BY sync.id
                                       """ % ", ".join("?" for _ in xrange(len(members))),
                                                                 (message.community.database_id, tim[0], message.database_id) + members)
                                       if count == message.authentication.count]

                            if packets:
                                assert len(packets) == 1
                                self._send([message.address], map(str, packets), u"-sequence-")

                            else:
                                # TODO can still fail when packet is in one of the received messages
                                # from this batch.
                                pass

                        return DropMessage(message, "old message by members^global_time")

                    else:
                        # we accept this message
                        tim.append(message.distribution.global_time)
                        return message

        def check_sequence_number(highest, message):
            """
            The message.distribution.sequence_number must be the next number in line
            """
            assert isinstance(highest, dict)
            assert isinstance(message, Message.Implementation)

            if message.authentication.member in highest:
                seq = highest[message.authentication.member]
            else:
                # we can not simply count the msgs in the database because this is useses the
                # LastSyncDistribution policy
                try:
                    packet, = self._database.execute(u"SELECT packet FROM sync WHERE member = ? AND sync.meta_message = ? ORDER BY global_time DESC LIMIT 1",
                                                     (message.authentication.member.database_id, message.database_id)).next()
                except StopIteration:
                    seq = 0
                else:
                    msg = self.convert_packet_to_message(str(packet))
                    if msg:
                        seq = msg.distribution.sequence_number
                    else:
                        seq = 0
                highest[message.authentication.member] = seq

            if seq >= message.distribution.sequence_number:
                # we already have this message (drop)
                return DropMessage(message, "duplicate message by sequence_number (2)")

            elif seq + 1 == message.distribution.sequence_number:
                # we have the previous message
                highest[message.authentication.member] += 1
                return message

            else:
                # we do not have the previous message (delay and request)
                return DelayMessageBySequence(message, seq+1, message.distribution.sequence_number-1)

        # meta message
        meta = messages[0].meta

        # sort the messages by their (1) global_time and (2) binary packet
        messages = sorted(messages, lambda a, b: a.distribution.global_time - b.distribution.global_time or cmp(a.packet, b.packet))

        if isinstance(meta.authentication, MemberAuthentication):
            # a message is considered unique when (creator, global-time), i.r. (authentication.member,
            # distribution.global_time), is unique.  UNIQUE is used in the check_member_and_global_time
            # function
            unique = set()
            times = {}
            messages = [check_member_and_global_time(unique, times, message) for message in messages]

        # instead of storing HISTORY_SIZE messages for each authentication.member, we will store
        # HISTORY_SIZE messages for each combination of authentication.members.
        else:
            assert isinstance(meta.authentication, MultiMemberAuthentication)
            unique = set()
            times = {}
            messages = [check_multi_member_and_global_time(unique, times, message) for message in messages]

        # when sequence numbers are enabled, we need to have the previous message in the sequence
        # before we can process this message
        if meta.distribution.enable_sequence_number:
            highest = {}
            messages = [check_sequence_number(highest, message) if isinstance(message, Message.Implementation) else message for message in messages]

        return messages

    def _check_direct_distribution_batch(self, messages):
        """
        Returns the messages in the correct processing order.

        This method is called when a message with the DirectDistribution policy is received.  This
        message is not stored and hence we will not be able to see if we have already received this
        message.

        Receiving the same DirectDistribution multiple times indicates that the sending -wanted- to
        send this message multiple times.

        @param messages: Ignored.
        @type messages: [Message.Implementation]

        @return: All messages that are not dropped, i.e. all messages
        @rtype: [Message.Implementation]
        """
        # sort the messages by their (1) global_time and (2) binary packet
        return sorted(messages, lambda a, b: a.distribution.global_time - b.distribution.global_time or cmp(a.packet, b.packet))

    def data_came_in(self, packets):
        """
        UDP packets were received from the Tribler rawserver.

        This must be called on the Triber rawserver thread.  It will add the packets to the Dispersy
        Callback thread for processing.
        """
        self._callback.register(self.on_incoming_packets, (packets,))

    def load_message(self, community, member, global_time):
        """
        Returns the message identified by community, member, and global_time.

        Each message is uniquely identified by the community that it is created in, the member it is
        created by and the global time when it is created.  Using these three parameters we return
        the associated the Message.Implementation instance.  None is returned when we do not have
        this message or it can not be decoded.
        """
        try:
            packet_id, packet = self._database.execute(u"SELECT id, packet FROM sync WHERE community = ? AND member = ? AND global_time = ? LIMIT 1",
                                                       (community.database_id, member.database_id, global_time)).next()
        except StopIteration:
            return None

        # find associated conversion
        try:
            conversion = community.get_conversion(packet[:22])
        except KeyError:
            if __debug__: dprint("unable to convert a ", len(packet), " byte packet (unknown conversion)", level="warning")
            return None

        try:
            message = conversion.decode_message(("", -1), packet)

        except (DropPacket, DelayPacket), exception:
            if __debug__: dprint("unable to convert a ", len(packet), " byte packet (", exception, ")", level="warning")
            return None

        message.packet_id = packet_id
        return message

    def convert_packet_to_message(self, packet, community=None, load=True, auto_load=True):
        """
        Returns the Message representing the packet or None when no conversion is possible.
        """
        if __debug__:
            from community import Community
        assert isinstance(packet, str)
        assert isinstance(community, (type(None), Community))
        assert isinstance(load, bool)
        assert isinstance(auto_load, bool)

        # find associated community
        if not community:
            try:
                community = self.get_community(packet[2:22], load, auto_load)
            except KeyError:
                if __debug__: dprint("unable to convert a ", len(packet), " byte packet (unknown community)", level="warning")
                return None

        # find associated conversion
        try:
            conversion = community.get_conversion(packet[:22])
        except KeyError:
            if __debug__: dprint("unable to convert a ", len(packet), " byte packet (unknown conversion)", level="warning")
            return None

        try:
            return conversion.decode_message(("", -1), packet)

        except (DropPacket, DelayPacket), exception:
            if __debug__: dprint("unable to convert a ", len(packet), " byte packet (", exception, ")", level="warning")
            return None

    def convert_packets_to_messages(self, packets):
        """
        Returns a list with messages representing each packet or None when no conversion is
        possible.
        """
        return [self.convert_packet_to_message(packet) for packet in packets]

    def on_incoming_packets(self, packets, cache=True):
        """
        Process incoming UDP packets.

        This method is called to process one or more UDP packets.  This occurs when new packets are
        received, to attempt to process previously delayed packets, or when a member explicitly
        creates a packet to process.  The last option should only occur for debugging purposes.

        All the received packets are processed in batches, a batch consists of all packets for the
        same community and the same meta message.  Batches are formed with the following steps:

         1. The associated community is retrieved.  Failure results in packet drop.

         2. The associated conversion is retrieved.  Failure results in packet drop, this probably
            indicates that we are running outdated software.

         3. The associated meta message is retrieved.  Failure results in a packet drop, this
            probably indicates that we are running outdated software.

        All packets are grouped by their meta message.  All batches are scheduled based on the
        meta.delay and meta.priority.  Finally, the candidate table is updated in regards to the
        incoming source addresses.

        @param packets: The sequence of packets.
        @type packets: [(address, packet)]
        """
        assert isinstance(packets, (tuple, list))
        assert len(packets) > 0
        assert not filter(lambda x: not len(x) == 2, packets)
        assert isinstance(cache, bool)

        bytes_received = sum(len(packet) for _, packet in packets)
        self._statistics.increment_total_down(bytes_received)

        addresses = set()
        sort_key = lambda tup: (tup[0].priority, tup[0]) # meta, address, packet, conversion
        groupby_key = lambda tup: tup[0] # meta, address, packet, conversion
        for meta, iterator in groupby(sorted(self._convert_packets_into_batch(packets), key=sort_key), key=groupby_key):
            batch = [(address, packet, conversion) for _, address, packet, conversion in iterator]
            if __debug__: dprint("processing ", len(batch), " ", meta.name, " messages (unchecked)")

            # build unique set containing source addresses
            addresses.update(address for address, _, _ in batch)

            # schedule batch processing (taking into account the message priority)
            if meta.delay and cache:
                if meta in self._batch_cache:
                    self._batch_cache[meta].extend(batch)
                    if __debug__:
                        self._debug_batch_cache_performance[meta].append(len(batch))
                else:
                    self._batch_cache[meta] = batch
                    self._callback.register(self._on_batch_cache_timeout, (meta,), delay=meta.delay, priority=meta.priority)
                    if __debug__:
                        self._debug_batch_cache_performance[meta] = [len(batch)]

            else:
                # ignore cache, process batch immediately
                self._on_batch_cache(meta, batch)

        # update candidate table.  We know that some peer (not necessarily
        # message.authentication.member) exists at this address.
        self._database.executemany(u"INSERT OR REPLACE INTO candidate (community, host, port, incoming_time) VALUES (?, ?, ?, DATETIME('now'))",
                                   ((meta.community.database_id, unicode(host), port) for host, port in addresses))

    def _on_batch_cache_timeout(self, meta):
        """
        Start processing a batch of messages once the cache timeout occurs.

        This method is called meta.delay seconds after the first message in this batch arrived.  All
        messages in this batch have been 'cached' together in self._batch_cache[meta].  Hopefully
        the delay caused the batch to collect as many messages as possible.
        """
        assert meta in self._batch_cache
        assert meta in self._debug_batch_cache_performance
        if __debug__:
            performance = self._debug_batch_cache_performance.pop(meta)
            if meta.delay:
                dprint("batch size: ", sum(performance), " [", ":".join(map(str, performance)), "] for ", meta.name, " after ", meta.delay, "s")
        return self._on_batch_cache(meta, self._batch_cache.pop(meta))

    def _on_batch_cache(self, meta, batch):
        """
        Start processing a batch of messages.

        The batch is processed in the following steps:

         1. All duplicate binary packets are removed.

         2. All binary packets are converted into Message.Implementation instances.  Some packets
            are dropped or delayed at this stage.

         3. All remaining messages are passed to on_message_batch.
        """
        def unique(batch):
            unique = set()
            for address, packet, conversion in batch:
                assert isinstance(packet, str)
                if packet in unique:
                    if __debug__: dprint("drop a ", len(packet), " byte packet (duplicate in batch) from ", address[0], ":", address[1], level="warning")
                    self._statistics.drop("_convert_packets_into_batch:duplicate in batch", len(packet))
                else:
                    unique.add(packet)
                    yield address, packet, conversion

        # remove duplicated
        # todo: make _convert_batch_into_messages accept iterator instead of list to avoid conversion
        batch = list(unique(batch))

        # convert binary packets into Message.Implementation instances
        messages = list(self._convert_batch_into_messages(batch))
        assert not filter(lambda x: not isinstance(x, Message.Implementation), messages), "_convert_batch_into_messages must return only Message.Implementation instances"
        assert not filter(lambda x: not x.meta == meta, messages), "All Message.Implementation instances must be in the same batch"
        if __debug__: dprint(len(messages), " ", meta.name, " messages after conversion")

        # handle the incoming messages
        if messages:
            self.on_message_batch(messages)

    def on_messages(self, messages):
        batches = dict()
        for message in messages:
            if not message.meta in batches:
                batches[message.meta] = set()
            batches[message.meta].add(message)

        for messages in batches.itervalues():
            self.on_message_batch(list(messages))

    def on_message_batch(self, messages):
        """
        Process one batch of messages.

        This method is called to process one or more Message.Implementation instances that all have
        the same meta message.  This occurs when new packets are received, to attempt to process
        previously delayed messages, or when a member explicitly creates a message to process.  The
        last option should only occur for debugging purposes.

        The messages are processed with the following steps:

         1. Messages created by a member in our blacklist are droped.

         2. Messages that are old or duplicate, based on their distribution policy, are dropped.

         3. The meta.check_callback(...) is used to allow messages to be dropped or delayed.

         4. Messages are stored, based on their distribution policy.

         5. The meta.handle_callback(...) is used to process the messages.

         6. A check is performed if any of these messages triggers a delayed action.

        @param packets: The sequence of messages with the same meta message from the same community.
        @type packets: [Message.Implementation]
        """
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert not filter(lambda x: not isinstance(x, Message.Implementation), messages)
        assert not filter(lambda x: not x.meta == messages[0].meta, messages), ("All messages need to have the same meta", messages[0].name, len(messages))
        assert not filter(lambda x: not x.community == messages[0].community, messages), ("All messages need to be from the same community", messages[0].name, len(messages))

        def _filter_fail(message):
            if isinstance(message, DelayMessage):
                self._statistics.delay("on_message_batch:%s" % message, len(message.delayed.packet))
                if __debug__: dprint(message.request.address[0], ":", message.request.address[1], ": delay a ", len(message.request.packet), " byte message (", message, ")")
                # try to extend an existing Trigger with the same pattern
                for trigger in self._triggers:
                    if isinstance(trigger, TriggerMessage) and trigger.extend(message.pattern, [message.delayed]):
                        if __debug__: dprint("extended an existing TriggerMessage")
                        break
                else:
                    # create a new Trigger with this pattern
                    trigger = TriggerMessage(message.pattern, self.on_messages, [message.delayed])
                    if __debug__: dprint("created a new TriggeMessage")
                    self._triggers.append(trigger)
                    self._callback.register(trigger.on_timeout, delay=10.0)
                    self._send([message.delayed.address], [message.request.packet], message.request.name)
                return False

            elif isinstance(message, DropMessage):
                if __debug__: dprint("drop: ", message.dropped.name, " (", message, ")", level="warning")
                self._statistics.drop("on_message_batch:%s" % message, len(message.dropped.packet))
                return False

            else:
                return True

        meta = messages[0].meta

        if __debug__:
            debug_count = len(messages)
            debug_begin = clock()

        # drop all duplicate or old messages
        assert type(meta.distribution) in self._check_distribution_batch_map
        messages = list(self._check_distribution_batch_map[type(meta.distribution)](messages))
        assert len(messages) > 0 # should return at least one item for each message
        assert not filter(lambda x: not isinstance(x, (Message.Implementation, DropMessage, DelayMessage)), messages)

        # handle/remove DropMessage and DelayMessage instances
        messages = [message for message in messages if _filter_fail(message)]
        if not messages:
            return 0

        # check all remaining messages on the community side.  may yield Message.Implementation,
        # DropMessage, and DelayMessage instances
        messages = list(meta.check_callback(messages))
        assert len(messages) >= 0 # may return zero messages
        assert not filter(lambda x: not isinstance(x, (Message.Implementation, DropMessage, DelayMessage)), messages)

        # handle/remove DropMessage and DelayMessage instances
        messages = [message for message in messages if _filter_fail(message)]
        if not messages:
            return 0

        # store to disk and update locally
        if __debug__: dprint("in... ", len(messages), " ", meta.name, " messages")
        self._statistics.success(meta.name, sum(len(message.packet) for message in messages), len(messages))
        self.store_update_forward(messages, True, True, False)

        # try to 'trigger' zero or more previously delayed 'things'
        self._triggers = [trigger for trigger in self._triggers if trigger.on_messages(messages)]

        # tell what happened
        if __debug__: dprint("handled ", len(messages), "/", debug_count, " %.2fs" %(clock() - debug_begin), " ", meta.name, " messages (after ", meta.delay, "s cache delay, for community ", meta.community.cid.encode("HEX"))

        # return the number of messages that were correctly handled (non delay, duplictes, etc)
        return len(messages)

    def _convert_packets_into_batch(self, packets):
        """
        Convert a list with one or more (address, data) tuples into a list with zero or more
        (Message, (address, packet, conversion)) tuples using a generator.

        # 22/06/11 boudewijn: no longer checks for duplicates.  duplicate checking is pointless
        # because new duplicates may be introduces because of the caching mechanism.
        #
        # Duplicate packets are removed.  This will result in drops when two we receive the exact same
        # binary packet from multiple nodes.  While this is usually not a problem, packets are usually
        # signed and hence unique, in rare cases this may result in invalid drops.

        Packets from invalid sources are removed.  The _is_valid_external_address is used to
        determine valid addresses.

        Packets associated with an unknown community are removed.  Packets from a known community
        encoded in an unknown conversion, are also removed.

        The results can be used to easily create a dictionary batch using
         > batch = dict(_convert_packets_into_batch(packets))
        """
        assert isinstance(packets, (tuple, list))
        assert len(packets) > 0
        assert not filter(lambda x: not len(x) == 2, packets)

        # unique = set()
        for address, packet in packets:
            assert isinstance(address, tuple)
            assert len(address) == 2
            assert isinstance(address[0], str)
            assert isinstance(address[1], int)
            assert isinstance(packet, str)

            # # we may have receive this packet in this on_incoming_packets callback
            # if packet in unique:
            #     if __debug__: dprint("drop a ", len(packet), " byte packet (duplicate in batch) from ", address[0], ":", address[1], level="warning")
            #     self._statistics.drop("_convert_packets_into_batch:duplicate in batch", len(packet))
            #     continue

            # is it from an external source
            if not self._is_valid_external_address(address):
                if __debug__: dprint("drop a ", len(packet), " byte packet (received from an invalid source) from ", address[0], ":", address[1], level="warning")
                self._statistics.drop("_convert_packets_into_batch:invalid source", len(packet))
                continue

            # find associated community
            try:
                community = self.get_community(packet[2:22])
            except KeyError:
                if __debug__: dprint("drop a ", len(packet), " byte packet (received packet for unknown community) from ", address[0], ":", address[1], level="warning")
                self._statistics.drop("_convert_packets_into_batch:unknown community", len(packet))
                continue

            # find associated conversion
            try:
                conversion = community.get_conversion(packet[:22])
            except KeyError:
                if __debug__: dprint("drop a ", len(packet), " byte packet (received packet for unknown conversion) from ", address[0], ":", address[1], level="warning")
                self._statistics.drop("_convert_packets_into_batch:unknown conversion", len(packet))
                continue

            try:
                # convert binary data into the meta message
                yield conversion.decode_meta_message(packet), address, packet, conversion

            except DropPacket, exception:
                if __debug__: dprint(address[0], ":", address[1], ": drop a ", len(packet), " byte packet (", exception, ")", level="warning")
                self._statistics.drop("_convert_packets_into_batch:decode_meta_message:%s" % exception, len(packet))

    def _convert_batch_into_messages(self, batch):
        if __debug__:
            from conversion import Conversion
        assert isinstance(batch, (list, set))
        assert len(batch) > 0
        assert not filter(lambda x: not isinstance(x, tuple), batch)
        assert not filter(lambda x: not len(x) == 3, batch)

        if __debug__:
            begin_stats = Conversion.debug_stats.copy()

        for address, packet, conversion in batch:
            assert isinstance(address, tuple)
            assert isinstance(address[0], str)
            assert isinstance(address[1], int)
            assert isinstance(packet, str)
            assert isinstance(conversion, Conversion)

            try:
                # convert binary data to internal Message
                yield conversion.decode_message(address, packet)

            except DropPacket, exception:
                if __debug__: dprint(address[0], ":", address[1], ": drop a ", len(packet), " byte packet (", exception, ")", level="warning")
                self._statistics.drop("_convert_batch_into_messages:%s" % exception, len(packet))

            except DelayPacket, delay:
                if __debug__: dprint(address[0], ":", address[1], ": delay a ", len(packet), " byte packet (", delay, ")")
                self._statistics.delay("_convert_batch_into_messages:%s" % delay, len(packet))
                # try to extend an existing Trigger with the same pattern
                for trigger in self._triggers:
                    if isinstance(trigger, TriggerPacket) and trigger.extend(delay.pattern, [(address, packet)]):
                        if __debug__: dprint("extended an existing TriggerPacket")
                        break
                else:
                    # create a new Trigger with this pattern
                    trigger = TriggerPacket(delay.pattern, self.on_incoming_packets, [(address, packet)])
                    if __debug__: dprint("created a new TriggerPacket")
                    self._triggers.append(trigger)
                    self._callback.register(trigger.on_timeout, delay=10.0)
                    self._send([address], [delay.request_packet], u"-delay-packet-")

        if __debug__:
            if len(batch) > 100:
                for key, value in sorted(Conversion.debug_stats.iteritems()):
                    if value - begin_stats[key] > 0.0:
                        dprint("[", value - begin_stats[key], " cnv] ", len(batch), "x ", key)

    def _store(self, messages):
        """
        Store a message in the database.

        Messages with the Last- or Full-SyncDistribution policies need to be stored in the database
        to allow them to propagate to other members.

        Messages with the LastSyncDistribution policy may also cause an older message to be removed
        from the database.

        Messages created by a member that we have marked with must_store will also be stored in the
        database, and hence forwarded to others.

        @param message: The unstored message with the SyncDistribution policy.
        @type message: Message.Implementation
        """
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert not filter(lambda x: not isinstance(x, Message.Implementation), messages)
        assert not filter(lambda x: not x.community == messages[0].community, messages), "All messages need to be from the same community"
        assert not filter(lambda x: not x.meta == messages[0].meta, messages), "All messages need to have the same meta"
        assert not filter(lambda x: not isinstance(x.distribution, SyncDistribution.Implementation), messages)
        # ensure no duplicate messages are present, this MUST HAVE been checked before calling this
        # method!
        assert len(messages) == len(set((message.authentication.member.database_id, message.distribution.global_time) for message in messages)), messages[0].name

        meta = messages[0].meta
        if __debug__: dprint("attempting to store ", len(messages), " ", meta.name, " messages")
        is_subjective_destination = isinstance(meta.destination, SubjectiveDestination)
        is_multi_member_authentication = isinstance(meta.authentication, MultiMemberAuthentication)

        update_sync_range = []
        free_sync_range = []
        for message in messages:
            # the signature must be set
            assert isinstance(message.authentication, (MemberAuthentication.Implementation, MultiMemberAuthentication.Implementation)), message.authentication
            assert message.authentication.is_signed
            assert not message.packet[-10:] == "\x00" * 10, message.packet[-10:].encode("HEX")

            # we do not store a message when it uses SubjectiveDestination and it is not in our set
            if is_subjective_destination and not message.destination.is_valid:
                # however, ignore the SubjectiveDestination when we are forced so store this message
                if not message.authentication.member.must_store:
                    if __debug__: dprint("not storing message")
                    continue

            # add packet to database
            self._database.execute(u"INSERT INTO sync (community, member, global_time, meta_message, packet) VALUES (?, ?, ?, ?, ?)",
                    (message.community.database_id,
                     message.authentication.member.database_id,
                     message.distribution.global_time,
                     message.database_id,
                     buffer(message.packet)))
            assert self._database.changes == 1
            update_sync_range.append(message)

            # ensure that we can reference this packet
            message.packet_id = self._database.last_insert_rowid
            if __debug__: dprint("insert_rowid: ", message.packet_id, " for ", message.name)

            # link multiple members is needed
            if is_multi_member_authentication:
                self._database.executemany(u"INSERT INTO reference_member_sync (member, sync) VALUES (?, ?)",
                                           [(member.database_id, message.packet_id) for member in message.authentication.members])
                assert self._database.changes == message.authentication.count

        if isinstance(meta.distribution, LastSyncDistribution):
            # delete packets that have become obsolete
            items = set()
            if is_multi_member_authentication:
                for member_database_ids in set(tuple(sorted(member.database_id for member in message.authentication.members)) for message in messages):
                    OR = u" OR ".join(u"reference_member_sync.member = ?" for _ in xrange(meta.authentication.count))
                    iterator = self._database.execute(u"""
                            SELECT sync.id, sync.member, sync.global_time, reference_member_sync.member
                            FROM sync
                            JOIN reference_member_sync ON reference_member_sync.sync = sync.id
                            WHERE sync.community = ? AND sync.meta_message = ? AND (%s)
                            ORDER BY sync.global_time, sync.packet""" % OR,
                                       (meta.community.database_id, meta.database_id) + member_database_ids)
                    all_items = []
                    # TODO: weird.  group by using row[0], that is sync.id, and that is unique, so
                    # groupby makes no sence.  Furthermore, groupby requires row[0] to be sorted,
                    # and that is not the case either.
                    for id_, group in groupby(iterator, key=lambda row: row[0]):
                        group = list(group)
                        if len(group) == meta.authentication.count and member_database_ids == tuple(sorted(check_member_id for _, _, _, check_member_id in group)):
                            _, creator_database_id, global_time, _ = group[0]
                            all_items.append((id_, creator_database_id, global_time))

                    if len(all_items) > meta.distribution.history_size:
                        items.update(all_items[:len(all_items) - meta.distribution.history_size])

            else:
                for member_database_id in set(message.authentication.member.database_id for message in messages):
                    all_items = list(self._database.execute(u"SELECT id, member, global_time FROM sync WHERE community = ? AND meta_message = ? AND member = ? ORDER BY global_time, packet",
                                             (meta.community.database_id, meta.database_id, member_database_id)))
                    if len(all_items) > meta.distribution.history_size:
                        items.update(all_items[:len(all_items) - meta.distribution.history_size])

            if items:
                self._database.executemany(u"DELETE FROM sync WHERE id = ?", [(id_,) for id_, _, _ in items])
                assert len(items) == self._database.changes
                if __debug__: dprint("deleted ", self._database.changes, " messages ", [id_ for id_, _, _ in items])

                if is_multi_member_authentication:
                    community_database_id = meta.community.database_id
                    self._database.executemany(u"DELETE FROM reference_member_sync WHERE sync = ?", [(id_,) for id_, _, _ in items])
                    assert len(items) * meta.authentication.count == self._database.changes

                free_sync_range.extend(global_time for _, _, global_time in items)

        if update_sync_range:
            # add items to the sync bloom filters
            meta.community.update_sync_range(update_sync_range)

        if free_sync_range:
            # update bloom filters
            meta.community.free_sync_range(free_sync_range)

    def yield_online_candidates(self, community, limit, clusters=(), batch=100, bootstrap=False):
        """
        Returns a generator that yields at most LIMIT Candicate objects representing nodes that are
        likely to be online.

        The following community properties affect the candidate choices:
         - dispersy_candidate_online_scores
         - dispersy_candidate_direct_observation_score
         - dispersy_candidate_indirect_observation_score
         - dispersy_candidate_subjective_set_score
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(limit, int)
        assert isinstance(batch, int)
        assert isinstance(clusters, (tuple, list))
        assert not filter(lambda x: not isinstance(x, int), clusters)
        assert not filter(lambda x: not x in community.subjective_set_clusters, clusters)
        return islice(self._yield_online_candidates(community, clusters, batch, bootstrap), limit)

    def _yield_online_candidates(self, community, clusters, batch, bootstrap):
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(batch, int)
        assert isinstance(clusters, (tuple, list))
        assert not filter(lambda x: not isinstance(x, int), clusters)
        assert not filter(lambda x: not x in community.subjective_set_clusters, clusters)
        assert isinstance(bootstrap, bool)

        def get_observation(observation_score, host, port, incoming_age, outgoing_age, external_age):
            candidate = Candidate(str(host), int(port), incoming_age, outgoing_age, external_age)

            # add direct observation score
            total_score = observation_score

            # add recently online score
            for high, score in online_scores:
                if incoming_age <= high:
                    total_score += score
                    break

            # add subjective set score (i.e. am I interested in HER data?)
            if subjective_sets:
                for member in candidate.members:
                    for subjective_set in subjective_sets:
                        if member.public_key in subjective_set:
                            total_score += subjective_set_score
                            break

            score = total_score * (probabilistic_factor_min + (probabilistic_factor_max - probabilistic_factor_min) * random())
            if __debug__: dprint("SCORE ", total_score, " -> ", score, " for ", host, ":", port)
            return score, candidate

        direct_observation_sql = u"SELECT host, port, STRFTIME('%s', 'now') - STRFTIME('%s', incoming_time) AS incoming_age, STRFTIME('%s', 'now') - STRFTIME('%s', outgoing_time) AS outgoing_age, STRFTIME('%s', 'now') - STRFTIME('%s', external_time) AS external_age FROM candidate WHERE community = ? AND incoming_age BETWEEN ? AND ? ORDER BY incoming_age ASC LIMIT ? OFFSET ?"
        indirect_observation_sql = u"SELECT host, port, STRFTIME('%s', 'now') - STRFTIME('%s', incoming_time) AS incoming_age, STRFTIME('%s', 'now') - STRFTIME('%s', outgoing_time) AS outgoing_age, STRFTIME('%s', 'now') - STRFTIME('%s', external_time) AS external_age FROM candidate WHERE community = ? AND incoming_age NOT BETWEEN ? AND ? AND external_age BETWEEN ? AND ? ORDER BY external_age ASC LIMIT ? OFFSET ?"

        subjective_sets = [community.get_subjective_set(community.my_member, cluster) for cluster in clusters]
        incoming_time_low, incoming_time_high = community.dispersy_candidate_online_range
        online_scores = community.dispersy_candidate_online_scores
        direct_observation_score = community.dispersy_candidate_direct_observation_score
        indirect_observation_score = community.dispersy_candidate_indirect_observation_score
        subjective_set_score = community.dispersy_candidate_subjective_set_score
        probabilistic_factor_min, probabilistic_factor_max = community.dispersy_candidate_probabilistic_factor

        sorting_key = lambda tup: tup[0]

        for offset in xrange(0, maxint, batch):
            # cache all items returned from the select statement, otherwise the cursur will be
            # re-used whenever another query is performed by the caller
            candidates = []
            candidates.extend(get_observation(direct_observation_score, *tup) for tup in list(self._database.execute(direct_observation_sql, (community.database_id, incoming_time_low, incoming_time_high, batch, offset))))
            candidates.extend(get_observation(indirect_observation_score, *tup) for tup in list(self._database.execute(indirect_observation_sql, (community.database_id, incoming_time_low, incoming_time_high, incoming_time_low, incoming_time_high, batch, offset))))

            if __debug__: dprint("there are ", len(candidates), " candidates in this batch")
            if not candidates:
                break

            # the sql queries should result in unique candidates
            if __debug__:
                unique = set(candidate.address for _, candidate in candidates)
                assert len(unique) == len(candidates), (len(unique), len(candidates))

            for score, candidate in sorted(candidates, key=sorting_key, reverse=True):
                # skip bootstrap peers when BOOTSTRAP is False
                if not bootstrap and candidate.address in self._bootstrap_addresses:
                    continue

                if __debug__: dprint("Yield ", candidate.host, ":", candidate.port, " with score ", score)
                yield candidate

    def yield_subjective_candidates(self, community, limit, cluster, batch=100, bootstrap=False):
        """
        Returns a generator that yields at most LIMIT unique Candidate objects ordered by most
        likely to least likely to be online and who we believe have our public key in their
        subjective set.

        Usefull when we create a messages that uses the SubjectiveDestination policy and we want to
        spread this to nodes that are likely to be interested in these messages.
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(limit, int)
        assert isinstance(cluster, int)
        assert cluster in community.subjective_set_clusters
        assert isinstance(batch, int)
        assert isinstance(bootstrap, bool)

        for candidate in islice(self._yield_online_candidates(community, [cluster], batch, bootstrap), limit):
            # we need to check the members associated to these candidates and see if they are
            # interested in this cluster
            for member in candidate.members:
                subjective_set = community.get_subjective_set(member, cluster)
                # TODO when we do not have a subjective_set from member, we should request it to
                # ensure that we make a valid decision next time
                if subjective_set and community.my_member.public_key in subjective_set:
                    yield candidate

    def yield_mixed_candidates(self, community, limit, clusters=(), batch=100):
        """
        Returns a generator that yields LIMIT unique Candidate objects where the selection is a
        mixed between peers that are most likely to be online and peers that are less likely to be
        online.
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(limit, int)
        assert isinstance(clusters, (tuple, list))
        assert not filter(lambda x: not isinstance(x, int), clusters)
        assert not filter(lambda x: not x in community.subjective_set_clusters, clusters)
        assert isinstance(batch, int)

        counter = 0
        for counter, candidate in enumerate(islice(self._yield_online_candidates(community, clusters, batch, True), limit)):
            yield candidate

        if counter + 1 < limit:
            # at this point we do not have sufficient nodes that were online recently.  as an
            # alternative we will add the addresses of dispersy routers that should always be online
            shuffle(self._bootstrap_addresses)
            for address in self._bootstrap_addresses:
                yield Candidate(address[0], address[1], 0, 0, 0)

    def store_update_forward(self, messages, store, update, forward):
        """
        Usually we need to do three things when we have a valid messages: (1) store it in our local
        database, (2) process the message locally by calling the handle_callback method, and (3)
        forward the message to other nodes in the community.  This method is a shorthand for doing
        those three tasks.

        To reduce the disk activity, namely syncing the database to disk, we will perform the
        database commit not after the (1) store operation but after the (2) update operation.  This
        will ensure that any database changes from handling the message are also synced to disk.  It
        is important to note that the sync will occur before the (3) forward operation to ensure
        that no external nodes will obtain data that we have not safely synced ourselves.

        For performance reasons messages are processed in batches, where each batch contains only
        messages from the same community and the same meta message instance.  This method, or more
        specifically the methods that handle the actual storage, updating, and forwarding, assume
        this clustering.

        @param messages: A list with the messages that need to be stored, updated, and forwarded.
         All messages need to be from the same community and meta message instance.
        @type messages: [Message.Implementation]

        @param store: When True the messages are stored (as defined by their message distribution
         policy) in the local dispersy database.  This parameter should (almost always) be True, its
         inclusion is mostly to allow certain debugging scenarios.
        @type store: bool

        @param update: When True the messages are passed to their handle_callback methods.  This
         parameter should (almost always) be True, its inclusion is mostly to allow certain
         debugging scenarios.
        @type update: bool

        @param forward: When True the messages are forwarded (as defined by their message
         destination policy) to other nodes in the community.  This parameter should (almost always)
         be True, its inclusion is mostly to allow certain debugging scenarios.
        @type store: bool
        """
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert not filter(lambda x: not isinstance(x, Message.Implementation), messages)
        assert not filter(lambda x: not x.community == messages[0].community, messages), "All messages need to be from the same community"
        assert not filter(lambda x: not x.meta == messages[0].meta, messages), "All messages need to have the same meta"
        assert isinstance(store, bool)
        assert isinstance(update, bool)
        assert isinstance(forward, bool)

        store = store and isinstance(messages[0].meta.distribution, SyncDistribution)
        if store:
            self._store(messages)

        if update:
            # TODO in theory we do not need to update_global_time when we store...
            messages[0].community.update_global_time(max(message.distribution.global_time for message in messages))
            messages[0].handle_callback(messages)

        if store:
            self._database.commit()

        if forward:
            self._forward(messages)

    def _forward(self, messages):
        """
        Queue a sequence of messages to be sent to other members.

        First all messages that use the SyncDistribution policy are stored to the database to allow
        them to propagate when a dispersy-sync message is received.

        Second all messages are sent depending on their destination policy:

         - AddressDestination causes a message to be sent to the addresses in
           message.destination.addresses.

         - MemberDestination causes a message to be sent to the address associated to the member in
           message.destination.members.

         - CommunityDestination causes a message to be sent to one or more addresses to be picked
           from the database candidate table.

         - SubjectiveDestination is currently handled in the same way as CommunityDestination.
           Obviously this needs to be modified.

        @param messages: A sequence with one or more messages.
        @type messages: [Message.Implementation]
        """
        assert isinstance(messages, (tuple, list))
        assert len(messages) > 0
        assert not filter(lambda x: not isinstance(x, Message.Implementation), messages)

        # todo: we can optimize below code given the following two restrictions
        assert not filter(lambda x: not x.community == messages[0].community, messages), "All messages need to be from the same community"
        assert not filter(lambda x: not x.meta == messages[0].meta, messages), "All messages need to have the same meta"

        for message in messages:
            if isinstance(message.destination, CommunityDestination.Implementation):
                if message.destination.node_count > 0: # CommunityDestination.node_count is allowed to be zero
                    addresses = [candidate.address
                                 for candidate
                                 in self.yield_online_candidates(message.community, message.destination.node_count, message.community.subjective_set_clusters)]
                    if addresses:
                        self._send(addresses, [message.packet], message.name)

                    if __debug__:
                        if addresses:
                            dprint("outgoing ", message.name, " (", len(message.packet), " bytes) to ", ", ".join("%s:%d" % address for address in addresses))
                        else:
                            dprint("failed to send ", message.name, " (", len(message.packet), " bytes) because there are no destination addresses", level="warning")

            elif isinstance(message.destination, SubjectiveDestination.Implementation):
                if message.destination.node_count > 0: # CommunityDestination.node_count is allowed to be zero
                    addresses = [candidate.address
                                 for candidate
                                 in self.yield_subjective_candidates(message.community, message.destination.node_count, message.destination.cluster)]
                    if addresses:
                        self._send(addresses, [message.packet], message.name)

                    if __debug__:
                        if addresses:
                            dprint("outgoing ", message.name, " (", len(message.packet), " bytes) to ", ", ".join("%s:%d" % address for address in addresses))
                        else:
                            dprint("failed to send ", message.name, " (", len(message.packet), " bytes) because there are no destination addresses", level="warning")

            elif isinstance(message.destination, AddressDestination.Implementation):
                if __debug__: dprint("outgoing ", message.name, " (", len(message.packet), " bytes) to ", ", ".join("%s:%d" % address for address in message.destination.addresses))
                self._send(message.destination.addresses, [message.packet], message.name)

            elif isinstance(message.destination, MemberDestination.Implementation):
                if __debug__:
                    for member in message.destination.members:
                        if not self._is_valid_external_address(member.address):
                            dprint("unable to send ", message.name, " to member (", member.address, ")", level="error")
                    dprint("outgoing ", message.name, " (", len(message.packet), " bytes) to ", ", ".join("%s:%d" % member.address for member in message.destination.members))
                self._send([member.address for member in message.destination.members], [message.packet], message.name)

            else:
                raise NotImplementedError(message.destination)

    def _send(self, addresses, packets, key=u"unspecified"):
        """
        Send one or more packets to one or more addresses.

        To clarify: every packet is sent to every address.

        @param addresses: A sequence with one or more addresses.
        @type addresses: [(string, int)]

        @param packets: A sequence with one or more packets.
        @type packets: string

        @param key: A unicode string purely used for statistics.  Indicating the type of data send.
        @type key: unicode
        """
        assert isinstance(addresses, (tuple, list, set)), type(addresses)
        assert isinstance(packets, (tuple, list, set)), type(packets)
        assert isinstance(key, unicode), type(key)

        bytes_send = sum(len(packet) for packet in packets)
        self._statistics.increment_total_up(bytes_send)

        if __debug__:
            if not addresses:
                # this is a programming bug.
                dprint("no addresses given (wanted to send ", len(packets), " packets)", level="error", stack=True)
            if not packets:
                # this is a programming bug.
                dprint("no packets given (wanted to send to ", len(addresses), " addresses)", level="error", stack=True)

        # update candidate table and send packets
        for address in addresses:
            assert isinstance(address, tuple), address
            assert isinstance(address[0], str), address
            assert isinstance(address[1], int), address

            if not self._is_valid_external_address(address):
                # this is a programming bug.  apparently an invalid address is being used
                if __debug__: dprint("aborted sending ", len(packets), "x ", key, "(", sum(len(packet) for packet in packets), " bytes) to ", address[0], ":", address[1], " (invalid external address)", level="error")
                continue

            for packet in packets:
                assert isinstance(packet, str)
                self._socket.send(address, packet)
            self._statistics.outgoing(address, key, sum(len(packet) for packet in packets), len(packets))
            if __debug__: dprint("out... ", len(packets), "x ", key, " (", sum(len(packet) for packet in packets), " bytes) to ", address[0], ":", address[1])
            self._database.execute(u"UPDATE candidate SET outgoing_time = DATETIME('now') WHERE host = ? AND port = ?", (unicode(address[0]), address[1]))

    def await_message(self, footprint, response_func, response_args=(), timeout=10.0, max_responses=1):
        """
        Register a callback to occur when a message with a specific footprint is received, or after
        a certain timeout occurs.

        When the footprint of an incoming message matches the regular expression footprint it is
        passed to both the response_func (or several if the message matches multiple footprints) and
        its regular message handler.  First the regular message handler is called, followed by
        response_func.

        The response_func is called each time when a message is received that matches the expression
        footprint or after timeout seconds when fewer than max_responses incoming messages have
        matched footprint.  The first argument is the sender address (or ('', -1) on a timeout), the
        second argument is the incoming message, following this are any optional arguments in
        response_args.

        Response_args is a tuple that can be given optional values that are included in the call to
        response_func, following the address and message arguments.

        When the timeout expires and less than max_responses messages have matched the expression
        footprint, the response_func is called one last time.  The address and the message will be
        sent to ('', -1) None, respectively and response_args will be appended as normal.  Once a
        timeout callback is given no further callbacks will be made.

        The Trigger that is created will be removed either on timeout or when max_responses messages
        have matched the expression footprint.

        The footprint matching is done as follows: for each incoming message a message footprint is
        made.  This footprint is a string that contains a summary of all the message properties.
        Such as 'MemberAuthentication:ABCDE' and 'FullSyncDistribution:102'.

        @param footprint: The regular expression to match all incoming messages.
        @type footprint: string

        @param response_func: The method called when a message matches footprint.
        @type response_func: callable

        @param response_args: Optional arguments to added when calling response_func.
        @type response_args: tuple

        @param timeout: Number of seconds until a timeout occurs.
        @type timeout: float

        @param max_responses: Maximal number of messages to match until the Trigger is removed.
        @type max_responses: int
        """
        assert isinstance(footprint, str)
        assert hasattr(response_func, "__call__")
        assert isinstance(response_args, tuple)
        assert isinstance(timeout, float)
        assert timeout > 0.0
        assert isinstance(max_responses, (int, long))
        assert max_responses > 0

        trigger = TriggerCallback(footprint, response_func, response_args, max_responses)
        self._triggers.append(trigger)
        self._callback.register(trigger.on_timeout, delay=timeout)

    def declare_malicious_member(self, member, packets):
        """
        Provide one or more signed messages that prove that the creator is malicious.

        The messages are stored separately as proof that MEMBER is malicious, furthermore, all other
        messages that MEMBER created are removed from the dispersy database (limited to one
        community) to prevent further spreading of its data.

        Furthermore, whenever data is received that is signed by a malicious member, the incoming
        data is ignored and the proof is given to the sender to allow her to prevent her from
        forwarding any more data.

        Finally, the community is notified.  The community can choose what to do, however, it is
        important to note that messages from the malicious member are no longer propagated.  Hence,
        unless all traces from the malicious member are removed, no global consensus can ever be
        achieved.

        @param member: The malicious member.
        @type member: Member

        @param packets: One or more packets proving that the member is malicious.  All packets must
         be associated to the same community.
        @type packets: [Packet]
        """
        if __debug__:
            from member import Member
            assert isinstance(member, Member)
            assert not member.must_blacklist, "must not already be blacklisted"
            assert isinstance(packets, list)
            assert len(packets) > 0
            assert not filter(lambda x: not isinstance(x, Packet), packets)
            assert not filter(lambda x: not x.meta == packets[0].meta, packets)

        if __debug__: dprint("proof based on ", len(packets), " packets")

        # notify the community
        community = packets[0].community
        community.dispersy_malicious_member_detected(member, packets)

        # set the member blacklisted tag
        member.must_blacklist = True

        # store the proof
        self._database.executemany(u"INSERT INTO malicious_proof (community, member, packet) VALUES (?, ?, ?)",
                                   ((community.database_id, member.database_id, buffer(packet.packet)) for packet in packets))

        # remove all messages created by the malicious member
        self._database.execute(u"DELETE FROM sync WHERE community = ? AND member = ?",
                               (community.database_id, member.database_id))

        # TODO: if we have a address for the malicious member, we can also remove her from the
        # candidate table

    def send_malicious_proof(self, community, member, address):
        """
        If we have proof that MEMBER is malicious in COMMUNITY, usually in the form of one or more
        signed messages, then send this proof to ADDRESS.

        @param community: The community where member was malicious.
        @type community: Community

        @param member: The malicious member.
        @type member: Member

        @param address: The address where we want the proof to be send.
        @type address: (str, int) tuple
        """
        if __debug__:
            from community import Community
            from member import Member
            assert isinstance(community, Community)
            assert isinstance(member, Member)
            assert member.must_blacklist, "must be blacklisted"
            assert isinstance(address, tuple)
            assert isinstance(address[0], str)
            assert isinstance(address[1], int)

        packets = [str(packet) for packet, in self._database.execute(u"SELECT packet FROM malicious_proof WHERE community = ? AND member = ?",
                                                                     (community.database_id, member.database_id))]
        if packets:
            self._send([address], packets)

    def create_missing_message(self, community, address, member, global_time, response_func=None, response_args=(), timeout=10.0, forward=True):
        """
        Create a dispersy-missing-message message.

        Each sync message in dispersy can be uniquely identified using the community identifier,
        member identifier, and global time.  This message requests a unique dispersy message from
        another peer.

        If the peer at ADDRESS (1) receives the request, (2) has the requested message, and (3) is
        willing to upload, the optional RESPONSE_FUNC will be called.  Note that if there is a
        callback for the requested message, that will always be called regardless of RESPONSE_FUNC.

        If RESPONSE_FUNC is given and there is no response withing TIMEOUT seconds, the
        RESPONSE_FUNC will be called but the message parameter will be None.
        """
        if __debug__:
            from community import Community
            assert isinstance(community, Community)
            assert isinstance(address, tuple)
            assert isinstance(address[0], str)
            assert isinstance(address[1], int)
            assert isinstance(footprint, str)
            assert isinstance(member, Member)
            assert isinstance(global_time, (int, long))
            assert callable(response_func)
            assert isinstance(response_args, tuple)
            assert isinstance(timeout, float)
            assert timeout > 0.0
            assert isinstance(forward, bool)

        meta = community.get_meta_message(u"dispersy-missing-message")
        request = meta.impl(distribution=(meta.community.global_time,), payload=(member, global_time))

        if response_func:
            # generate footprint
            footprint = "".join(("Community:", community.cid.encode("HEX"),
                                 "\s", "(MemberAuthentication:", member.mid.encode("HEX"), "|MultiMemberAuthentication:[^\s]*", member.mid.encode("HEX"), "[^\s]*)",
                                 "\s", "(Relay|Direct|Sync|)Distribution:", str(global_time), ",[0-9]+"))
            self.await_message(footprint, response_func, response_args, timeout, 1)

        self.store_update_forward([request], False, False, forward)
        return request

    def on_missing_message(self, messages):
        responses = [] # (address, packet) tuples
        for message in messages:
            address = message.address
            community_database_id = message.community.database_id
            member_database_id = message.payload.member.database_id
            for global_time in message.payload.global_times:
                try:
                    packet, = self._database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community_database_id, member_database_id, global_time)).next()
                except StopIteration:
                    pass
                else:
                    responses.append((address, packet))

        for address, responses in groupby(responses, key=lambda tup: tup[0]):
            self._send([address], [str(packet) for _, packet in responses])

    # def create_missing_last(self, community, address, member, message, response_func=None, response_args=(), timeout=10.0, forward=True):
    #     """
    #     Create a dispersy-missing-last message.

    #     Multiple sync messages in dispersy can be identified using the community identifier, member
    #     identifier, and meta message.  We only allow the LastSyncDistribution messages to be
    #     requested.  Typically this should only be used when history_size is one.

    #     If the peer at ADDRESS (1) receives the request, (2) has the requested message, and (3) is
    #     willing to upload, the optional RESPONSE_FUNC will be called.  Note that if there is a
    #     callback for the requested message, that will always be called regardless of RESPONSE_FUNC.

    #     If RESPONSE_FUNC is given and there is no response withing TIMEOUT seconds, the
    #     RESPONSE_FUNC will be called but the message parameter will be None.
    #     """
    #     assert isinstance(community, Community)
    #     assert isinstance(address, tuple)
    #     assert isinstance(address[0], str)
    #     assert isinstance(address[1], int)
    #     assert isinstance(footprint, str)
    #     assert isinstance(member, Member)
    #     assert isinstance(message, Message)
    #     assert isinstance(message.distribution, LastSyncDistribution)
    #     assert callable(response_func)
    #     assert isinstance(response_args, tuple)
    #     assert isinstance(timeout, float)
    #     assert timeout > 0.0
    #     assert isinstance(forward, bool)
    #     meta = community.get_meta_message(u"dispersy-missing-last")
    #     request = meta.implement(meta.authentication.implement(community.my_member),
    #                              meta.distribution.implement(meta.community.global_time),
    #                              meta.destination.implement(address),
    #                              meta.payload.implement(member, meta_message))

    #     if response_func:
    #         # generate footprint
    #         footprint = "".join((message.name.encode("UTF-8"),
    #                              "\s", "Community:", community.cid.encode("HEX"),
    #                              "\s", "(MemberAuthentication:", member.mid.encode("HEX"), "|MultiMemberAuthentication:[^\s]*", member.mid.encode("HEX"), "[^\s]*)"))
    #         self.await_message(footprint, response_func, response_args, timeout, message.distribution.history_size)

    #     self.store_update_forward([request], False, False, forward)
    #     return request

    # def check_missing_last(self, messages):
    #     for message in messages:
    #         if not message.community._timeline.check(message):
    #             yield DropMessage(message, "TODO: implement delay of proof")
    #             continue
    #         yield message

    # def on_missing_last(self, messages):
    #     responses = [] # (address, packet) tuples
    #     for message in messages:
    #         packet_iterator = self._database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND meta_message = ? ORDER BY global_time",
    #                                                  (message.community.database_id, message.payload.member.database_id, message.payload.meta_message.database_id))
    #         responses.extend((message.address, packet) for packet in packet_iterator)

    #     for address, responses in groupby(responses):
    #         self._send([address], [packet for _, packet in responses])

    def create_candidate_request(self, community, address, routes, response_func=None, response_args=(), timeout=10.0, max_responses=1, store=True, forward=True):
        """
        Create a dispersy-candidate-request message.

        The dispersy-candidate-request and -response messages are used to keep track of the address
        where a member can be found.  It is also used to check if the member is still alive because
        it triggers a response message.  Finally, it is used to spread addresses of other members
        aswell.

        The optional response_func is used to obtain a callback for this specific request.  The
        parameters response_func, response_args, timeout, and max_responses are all related to this
        callback and are explained in the await_message method.

        @param community: The community for wich the dispersy-candidate-request message will be
         created.
        @type community: Community

        @param address: The destination address.
        @type address: (string, int)

        @param response_func: The method called when a message matches footprint.
        @type response_func: callable

        @param response_args: Optional arguments to added when calling response_func.
        @type response_args: tuple

        @param timeout: Number of seconds until a timeout occurs.
        @type timeout: float

        @param max_responses: Maximal number of messages to match until the Trigger is removed.
        @type max_responses: int

        @param store: When True the messages are stored (as defined by their message distribution
         policy) in the local dispersy database.  This parameter should (almost always) be True, its
         inclusion is mostly to allow certain debugging scenarios.
        @type store: bool

        @param forward: When True the messages are forwarded (as defined by their message
         destination policy) to other nodes in the community.  This parameter should (almost always)
         be True, its inclusion is mostly to allow certain debugging scenarios.
        @type store: bool
        """
        assert isinstance(community, Community)
        assert isinstance(address, tuple)
        assert isinstance(address[0], str)
        assert isinstance(address[1], int)
        assert isinstance(routes, (tuple, list))
        assert not filter(lambda route: not isinstance(route, tuple), routes)
        assert not filter(lambda route: not len(route) == 2, routes)
        assert not filter(lambda route: not isinstance(route[0], tuple), routes)
        assert not filter(lambda route: not len(route[0]) == 2, routes)
        assert not filter(lambda route: not isinstance(route[0][0], str), routes)
        assert not filter(lambda route: not isinstance(route[0][1], (int, long)), routes)
        assert not filter(lambda route: not isinstance(route[1], float), routes)
        assert hasattr(response_func, "__call__")
        assert isinstance(response_args, tuple)
        assert isinstance(timeout, float)
        assert timeout > 0.0
        assert isinstance(max_responses, (int, long))
        assert max_responses > 0
        assert isinstance(store, bool)
        assert isinstance(forward, bool)
        meta = community.get_meta_message(u"dispersy-candidate-request")
        request = meta.impl(authentication=(community.my_member,),
                            distribution=(meta.community.global_time,),
                            destination=(address,),
                            payload=(self._my_external_address, address, community.get_conversion(), routes))

        if response_func:
            meta = community.get_meta_message(u"dispersy-candidate-response")
            footprint = meta.generate_footprint(payload=(sha1(request.packet).digest(),))
            self.await_message(footprint, response_func, response_args, timeout, max_responses)

        self.store_update_forward([request], store, False, forward)
        return request

    def _is_valid_external_address(self, address):
        if address[0] == "":
            return False

        if address[1] <= 0:
            return False

        if address[0].endswith(".0"):
            return False

        if address[0].endswith(".255"):
            return False

        if address == self._my_external_address:
            return False

        if address == ("127.0.0.1", self._my_external_address[1]):
            return False

        return True

    def _update_routes_from_external_source(self, community, routes):
        assert isinstance(routes, (tuple, list))
        assert not filter(lambda x: not isinstance(x, tuple), routes)
        assert not filter(lambda x: not len(x) == 2, routes)
        assert not filter(lambda x: not isinstance(x[0], tuple), routes), "(host, ip) tuple"
        assert not filter(lambda x: not isinstance(x[1], float), routes), "age in seconds"

        self._database.executemany(u"INSERT OR REPLACE INTO candidate (community, host, port, external_time) VALUES (?, ?, ?, DATETIME('now', ?))",
                                   ((community.database_id, unicode(address[0]), address[1], u"-%d seconds" % age) for address, age in routes if self._is_valid_external_address(address)))

        if __debug__:
            for address, age in routes:
                if self._is_valid_external_address(address):
                    dprint("updated candidate ", address[0], ":", address[1], " age ", age, " seconds")
                else:
                    level = "normal" if address == self.external_address else "warning"
                    dprint("dropping invalid route ", address[0], ":", address[1], level=level)

    def on_candidate_request(self, messages):
        """
        We received a dispersy-candidate-request message.

        This message contains the external address that the sender believes it has
        (message.payload.source_address), and our external address
        (message.payload.destination_address).

        We should send a dispersy-candidate-response message back.  Allowing us to inform them of
        their external address.

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-sync message.
        @type message: Message.Implementation
        """
        community = messages[0].community
        meta = community.get_meta_message(u"dispersy-candidate-response")
        minimal_age, maximal_age = community.dispersy_candidate_online_range
        sql = u"""SELECT host, port, STRFTIME('%s', 'now') - STRFTIME('%s', incoming_time) AS age
            FROM candidate
            WHERE community = ? AND age BETWEEN ? AND ?
            ORDER BY age
            LIMIT 30"""
        routes = [((str(host), port), float(age)) for host, port, age in self._database.execute(sql, (community.database_id, minimal_age, maximal_age))]
        responses = []

        for message in messages:
            assert message.name == u"dispersy-candidate-request"
            if __debug__: dprint(message)

            if __debug__: dprint("Our external address may be: ", message.payload.destination_address)
            self.external_address_vote(message.payload.destination_address, message.address)
            routes.extend(message.payload.routes)

            responses.append(meta.impl(authentication=(community.my_member,),
                                       distribution=(community.global_time,),
                                       destination=(message.address,),
                                       payload=(sha1(message.packet).digest(), self._my_external_address, message.address, meta.community.get_conversion().version, routes)))

        # add routes in our candidate table
        self._update_routes_from_external_source(community, routes)

        # send response
        self.store_update_forward(responses, False, False, True)

    def on_candidate_response(self, messages):
        """
        We received dispersy-candidate-response messages.

        This message contains the external address that the sender believes it has
        (message.payload.source_address), and our external address
        (message.payload.destination_address).

        We need to be carefull with this message.  It is very much possible that the
        destination_address is invalid.  Furthermore, currently anyone is free to send this message,
        making it very easy to generate any number of members to override simple security schemes
        that use counting.

        @param messages: The dispersy-candidate-response messages.
        @type messages: [Message.Implementation]
        """
        community = messages[0].community
        routes = []
        for message in messages:
            if __debug__: dprint("Our external address may be: ", message.payload.destination_address)
            self.external_address_vote(message.payload.destination_address, message.address)
            routes.extend(message.payload.routes)

        # add routes in our candidate table
        self._update_routes_from_external_source(community, routes)

    def create_identity(self, community, store=True, update=True):
        """
        Create a dispersy-identity message.

        The dispersy-identity message contains information on community.my_member.  Such as your
        public key and the IP address and port where you are reachable.

        Typically, every member is represented my the most recent dispersy-identity message that she
        created and provided to the network.  Generally one such message is created whenever a
        member joins an existing community for the first time, or when she creates a new community.

        @param community: The community for wich the dispersy-identity message will be created.
        @type community: Community

        @param store: When True the messages are stored (as defined by their message distribution
         policy) in the local dispersy database.  This parameter should (almost always) be True, its
         inclusion is mostly to allow certain debugging scenarios.
        @type store: bool
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(store, bool)
        meta = community.get_meta_message(u"dispersy-identity")
        message = meta.impl(authentication=(community.my_member,),
                            distribution=(community.claim_global_time(),),
                            payload=(self._my_external_address,))
        self.store_update_forward([message], store, update, False)
        return message

    def on_identity(self, messages):
        """
        We received a dispersy-identity message.

        @see: create_identity

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-identity message.
        @type message: Message.Implementation
        """
        for message in messages:
            assert message.name == u"dispersy-identity"
            if __debug__: dprint(message)
            host, port = message.payload.address
            # TODO: we should drop messages that contain invalid addresses... or at the very least we
            # should ignore the address part.

            self._database.execute(u"INSERT OR REPLACE INTO identity (community, member, host, port) VALUES (?, ?, ?, ?)",
                                   (message.community.database_id, message.authentication.member.database_id, unicode(host), port))

            if __debug__:
                # there may be a Member instance indexed at the mid
                member = message.authentication.member
                assert member.public_key
                if Member.has_instance(member.mid):
                    assert id(Member.has_instance(member.mid)) == id(member)
                    assert Member.has_instance(member.mid).public_key, "the public key should now be available"

            # update the in-memory member instance
            message.authentication.member.update()

    # def create_identity_request(self, community, mid, addresses, forward=True):
    #     """
    #     Create a dispersy-identity-request message.

    #     To verify a message signature we need the corresponding public key from the member who made
    #     the signature.  When we are missing a public key, we can request a dispersy-identity message
    #     which contains this public key.

    #     The missing member is identified by the sha1 digest over the member key.  This mid can
    #     indicate multiple members, hence the dispersy-identity-response will contain one or more
    #     public keys.

    #     Most often we will need to request a dispersy-identity when we receive a message containing
    #     an, to us, unknown mid.  Hence, sending the request to the address where we got that message
    #     from is usually most effective.

    #     @see: create_identity

    #     @param community: The community for wich the dispersy-identity message will be created.
    #     @type community: Community

    #     @param mid: The 20 byte identifier for the member.
    #     @type mid: string

    #     @param address: The address to send the request to.
    #     @type address: (string, int)

    #     @param forward: When True the messages are forwarded (as defined by their message
    #      destination policy) to other nodes in the community.  This parameter should (almost always)
    #      be True, its inclusion is mostly to allow certain debugging scenarios.
    #     @type forward: bool
    #     """
    #     meta = community.get_meta_message(u"dispersy-identity-request")
    #     message = meta.implement(meta.authentication.implement(),
    #                              meta.distribution.implement(community.global_time),
    #                              meta.destination.implement(*addresses),
    #                              meta.payload.implement(mid))
    #     self.store_update_forward([message], False, False, forward)
    #     return message

    def on_missing_identity(self, messages):
        """
        We received dispersy-missing-identity messages.

        The message contains the mid of a member.  The sender would like to obtain one or more
        associated dispersy-identity messages.

        @see: create_identity_request

        @param messages: The dispersy-identity message.
        @type messages: [Message.Implementation]
        """
        meta = messages[0].community.get_meta_message(u"dispersy-identity")
        for message in messages:
            # we are assuming that no more than 10 members have the same sha1 digest.
            sql = u"SELECT packet FROM sync JOIN member ON member.id = sync.member WHERE sync.community = ? AND sync.meta_message = ? AND member.mid = ? LIMIT 10"
            packets = [str(packet) for packet, in self._database.execute(sql, (message.community.database_id, meta.database_id, buffer(message.payload.mid)))]
            if packets:
                if __debug__: dprint("responding with ", len(packets), " identity messages")
                self._send([message.address], packets, u"dispersy-identity")
            else:
                if __debug__: dprint("could not find any missing members.  no response is sent", level="warning")

    def create_subjective_set(self, community, cluster, members, reset=True, store=True, update=True, forward=True):
        if __debug__:
            from community import Community
            from member import Member
        assert isinstance(community, Community)
        assert isinstance(cluster, int)
        assert isinstance(members, (tuple, list))
        assert not filter(lambda member: not isinstance(member, Member), members)
        assert isinstance(reset, bool)
        assert isinstance(store, bool)
        assert isinstance(update, bool)
        assert isinstance(forward, bool)

        # modify the subjective set (bloom filter)
        subjective_set = community.get_subjective_set(community.my_member, cluster)
        if not subjective_set:
            # TODO set the correct bloom filter params
            subjective_set = BloomFilter(community.dispersy_subjective_set_error_rate, community.dispersy_subjective_set_bits)
        if reset:
            subjective_set.clear()
        map(subjective_set.add, (member.public_key for member in members))

        # implement the message
        meta = community.get_meta_message(u"dispersy-subjective-set")
        message = meta.impl(authentication=(community.my_member,),
                            distribution=(community.claim_global_time(),),
                            payload=(cluster, subjective_set))
        self.store_update_forward([message], store, update, forward)
        return message

    def on_subjective_set(self, messages):
        for message in messages:
            message.community.clear_subjective_set_cache(message.authentication.member, message.payload.cluster, message.packet, message.payload.subjective_set)

    def on_missing_subjective_set(self, messages):
        """
        We received a dispersy-missing-subjective-set message.

        The dispersy-subjective-set-request message contains a list of Member instance for which the
        subjective set is requested.  We will search our database any subjective sets that we have.

        If the subjective set for self.my_member is requested and this is not found in the database,
        a default subjective set will be created.

        @see: create_subjective_set_request

        @param messages: The dispersy-missing-subjective-set messages.
        @type messages: [Message.Implementation]
        """
        community = messages[0].community
        subjective_set_message_id = community.get_meta_message(u"dispersy-subjective-set").database_id

        for message in messages:
            packets = []
            for member in message.payload.members:
                cache = community.get_subjective_set_cache(member, message.payload.cluster)
                if cache:
                    packets.append(cache.packet)

            if packets:
                self._send([message.address], packets, u"dispersy-subjective-set")

    # def create_subjective_set_request(community, community, cluster, members, update_locally=True, store_and_forward=True):
    #     if __debug__:
    #         from community import Community
    #         from member import Member
    #     assert isinstance(community, Community)
    #     assert isinstance(cluster, int)
    #     assert isinstance(members, (tuple, list))
    #     assert not filter(lambda member: not isinstance(member, Member), members)
    #     assert isinstance(update_locally, bool)
    #     assert isinstance(store_and_forward, bool)

    #     # implement the message
    #     meta = community.get_meta_message(u"dispersy-missing-subjective-set")
    #     message = meta.implement(meta.authentication.implement(),
    #                              meta.distribution.implement(community.global_time),
    #                              meta.destination.implement(),
    #                              meta.payload.implement(cluster, members))

    #     if update_locally:
    #         assert community._timeline.check(message)
    #         message.handle_callback(("", -1), message)

    #     if store_and_forward:
    #         self.store_and_forward([message])

    #     return message

    def create_signature_request(self, community, message, response_func, response_args=(), timeout=10.0, store=True, forward=True):
        """
        Create a dispersy-signature-request message.

        The dispersy-signature-request message contains a sub-message that is to be signed my
        multiple members.  The sub-message must use the MultiMemberAuthentication policy in order to
        store the multiple members and their signatures.

        Typically, each member that should add a signature will receive the
        dispersy-signature-request message.  If they choose to add their signature, a
        dispersy-signature-response message is send back.  This in turn will result in a call to
        response_func with the message that now has one additional signature.

        Each dispersy-signed-response message will result in one call to response_func.  The
        parameters for this call are the address where the response came from and the sub-message.
        When all signatures are available the property sub-message.authentication.is_signed will be
        True.

        If not all members sent a reply withing timeout seconds, one final call to response_func is
        made with parameters ('', -1) and None, for the address and message respectively.

        @param community: The community for wich the dispersy-signature-request message will be
         created.
        @type community: Community

        @param message: The message that is to receive multiple signatures.
        @type message: Message.Implementation

        @param response_func: The method that is called when a signature or a timeout is received.
        @type response_func: callable method

        @param response_args: Optional arguments added when calling response_func.
        @type response_args: tuple

        @param timeout: How long before a timeout is generated.
        @type timeout: float

        @param store: When True the messages are stored (as defined by their message distribution
         policy) in the local dispersy database.  This parameter should (almost always) be True, its
         inclusion is mostly to allow certain debugging scenarios.
        @type store: bool

        @param forward: When True the messages are forwarded (as defined by their message
         destination policy) to other nodes in the community.  This parameter should (almost always)
         be True, its inclusion is mostly to allow certain debugging scenarios.
        @type store: bool
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(message, Message.Implementation)
        assert isinstance(message.authentication, MultiMemberAuthentication.Implementation)
        assert hasattr(response_func, "__call__")
        assert isinstance(response_args, tuple)
        assert isinstance(timeout, float)
        assert isinstance(store, bool)
        assert isinstance(forward, bool)

        # the members that need to sign
        members = [member for signature, member in message.authentication.signed_members if not (signature or member.private_key)]

        # the dispersy-signature-request message that will hold the
        # message that should obtain more signatures
        meta = community.get_meta_message(u"dispersy-signature-request")
        request = meta.impl(distribution=(community.global_time,),
                            destination=tuple(members),
                            payload=(message,))

        # set callback and timeout
        identifier = sha1(request.packet).digest()
        footprint = community.get_meta_message(u"dispersy-signature-response").generate_footprint(payload=(identifier,))
        self.await_message(footprint, self._on_signature_response, (request, response_func, response_args), timeout, len(members))

        self.store_update_forward([request], store, False, forward)
        return request

    def check_signature_request(self, messages):
        assert isinstance(messages[0].meta.authentication, NoAuthentication)
        for message in messages:
            # we can not timeline.check this message because it uses the NoAuthentication policy

            # submsg contains the message that should receive multiple signatures
            submsg = message.payload.message

            has_private_member = False
            try:
                for is_signed, member in submsg.authentication.signed_members:
                    # Security: do NOT allow to accidentally sign with master member.
                    if member == message.community.master_member:
                        raise DropMessage(message, "You may never ask for a master member signature")

                    # is this signature missing, and could we provide it
                    if not is_signed and member.private_key:
                        has_private_member = True
                        break
            except DropMessage, exception:
                yield exception
                continue

            # we must be one of the members that needs to sign
            if not has_private_member:
                yield DropMessage(message, "Nothing to sign")
                continue

            # we can not timeline.check the submessage because it uses the MultiMemberAuthentication policy
            # # the message that we are signing must be valid according to our timeline
            # # if not message.community._timeline.check(submsg):
            # #     raise DropMessage("Does not fit timeline")

            # the community must allow this signature
            if not submsg.authentication.allow_signature_func(submsg):
                yield DropMessage(message, "We choose not to add our signature")
                continue

            # allow message
            yield message

    def on_signature_request(self, messages):
        """
        We received a dispersy-signature-request message.

        This message contains a sub-message (message.payload) that the message creator would like to
        have us sign.  The message may, or may not, have already been signed by some of the other
        members.  Furthermore, we can choose for ourselves if we want to add our signature to the
        sub-message or not.

        Once we have determined that we could provide a signature and that the sub-message is valid,
        from a timeline perspective, we will ask the community to say yes or no to adding our
        signature.  This question is done by calling the
        sub-message.authentication.allow_signature_func method.

        Only when the allow_signature_func method returns True will we add our signature.  In this
        case a dispersy-signature-response message is send to the creator of the message, the first
        one in the authentication list.

        Note that if for whatever reason we can add multiple signatures, i.e. we have the private
        key for more that one member signing the sub-message, we will send one
        dispersy-signature-response message for each signature that we can supply.

        @see: create_signature_request

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-signature-request message.
        @type message: Message.Implementation
        """
        responses = []
        for message in messages:
            assert isinstance(message, Message.Implementation), type(message)
            assert isinstance(message.payload.message, Message.Implementation), type(message.payload.message)
            assert isinstance(message.payload.message.authentication, MultiMemberAuthentication.Implementation), type(message.payload.message.authentication)

            # submsg contains the message that should receive multiple signatures
            submsg = message.payload.message

            # create signature(s) and reply
            identifier = sha1(message.packet).digest()
            first_signature_offset = len(submsg.packet) - sum([member.signature_length for member in submsg.authentication.members])
            for member in submsg.authentication.members:
                if member.private_key:
                    signature = member.sign(submsg.packet, 0, first_signature_offset)

                    # send response
                    meta = message.community.get_meta_message(u"dispersy-signature-response")
                    responses.append(meta.impl(distribution=(message.community.global_time,),
                                               destination=(message.address,),
                                               payload=(identifier, signature)))

        self.store_update_forward(responses, False, False, True)

    def on_signature_response(self, messages):
        pass

    def _on_signature_response(self, response, request, response_func, response_args):
        """
        A Trigger matched a received dispersy-signature-response message.

        We sent out a dispersy-signature-request, though the create_signature_request method, and
        have now received a dispersy-signature-response in reply.  If the signature is valid, we
        will call response_func with address and sub-message, where sub-message is the message
        parameter given to the create_signature_request method.

        When a timeout occurs the response_func will also be called, although now the address and
        sub-message parameters will be set to ('', -1) and None, respectively.

        Note that response_func is also called when the sub-message does not yet contain all the
        signatures.  This can be checked using sub-message.authentication.is_signed.

        @see: create_signature_request

        @param address: The sender address.
        @type address: (string, int)

        @param response: The dispersy-signature-response message.
        @type response: Message.Implementation

        @param request: The dispersy-dispersy-request message.
        @type message: Message.Implementation

        @param response_func: The method that is called when a signature or a timeout is received.
        @type response_func: callable method

        @param response_args: Optional arguments added when calling response_func.
        @type response_args: tuple
        """
        assert response is None or isinstance(response, Message.Implementation)
        assert response is None or response.name == u"dispersy-signature-response"
        assert isinstance(request, Message.Implementation)
        assert request.name == u"dispersy-signature-request"
        assert hasattr(response_func, "__call__")
        assert isinstance(response_args, tuple)

        # check for timeout
        if response is None:
            if __debug__: dprint("timeout")
            response_func(response, *response_args)

        else:
            if __debug__: dprint("response")
            # the multi signed message
            submsg = request.payload.message

            first_signature_offset = len(submsg.packet) - sum([member.signature_length for member in submsg.authentication.members])
            body = submsg.packet[:first_signature_offset]

            for signature, member in submsg.authentication.signed_members:
                if not signature and member.verify(body, response.payload.signature):
                    submsg.authentication.set_signature(member, response.payload.signature)
                    response_func(submsg, *response_args)

                    # assuming this signature only matches one member, we can break
                    break

    def on_missing_sequence(self, messages):
        """
        We received a dispersy-missing-sequence message.

        The message contains a member and a range of sequence numbers.  We will send the messages,
        up to a certain limit, in this range back to the sender.

        To limit the amount of bandwidth used we will not sent back more data after a certain amount
        has been sent.  This magic number is subject to change.

        @param messages: dispersy-missing-sequence messages.
        @type messages: [Message.Implementation]

        @todo: we need to optimise this to include a bandwidth throttle.  Otherwise a node can
         easilly force us to send arbitrary large amounts of data.
        """
        for message in messages:
            # we limit the response by byte_limit bytes per incoming message
            byte_limit = message.community.dispersy_missing_sequence_response_limit

            packets = []
            payload = message.payload
            for packet, in self._database.execute(u"SELECT packet FROM sync WHERE member = ? AND meta_message = ? LIMIT ? OFFSET ?",
                                                  (payload.member.database_id, payload.message.database_id, payload.missing_low, payload.missing_high - payload.missing_low)):
                packet = str(packet)

                if __debug__: dprint("Syncing ", len(packet), " bytes from sync_full to " , message.address[0], ":", message.address[1])
                packets.append(packet)

                byte_limit -= len(packet)
                if byte_limit > 0:
                    if __debug__: dprint("Bandwidth throttle")
                    break

            if packets:
                self._send([message.address], packets, u"-sequence")

    def on_missing_proof(self, messages):
        community = messages[0].community
        for message in messages:
            try:
                packet, = self._database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND global_time = ? LIMIT 1",
                                                 (community.database_id, message.payload.member.database_id, message.payload.global_time)).next()

            except StopIteration:
                if __debug__: dprint("someone asked for proof for a message that we do not have", level="warning")

            else:
                packet = str(packet)
                msg = community.get_conversion(packet[:22]).decode_message(("", -1), packet)
                allowed, proofs = community._timeline.check(msg)
                if allowed:
                    if __debug__: dprint("found the proof someone was missing (", len(proofs), " packets)")
                    self._send([message.address], [proof.packet for proof in proofs], u"-proof-")

                else:
                    if __debug__: dprint("someone asked for proof for a message that is not allowed (", len(proofs), " packets)")

    def check_sync(self, messages):
        """
        We received a dispersy-sync message.

        The message contains a bloom-filter that needs to be checked.  If we find any messages that
        are not in the bloom-filter, we will sent those to the sender.

        To limit the amount of bandwidth used we will not sent back more data after a certain amount
        has been sent.  This magic number is subject to change.

        @param address: The sender address.
        @type address: (string, int)

        @param message: The dispersy-sync message.
        @type message: Message.Implementation

        @todo: we should look into optimizing this method, currently it just sends back data.
         Therefore, if multiple nodes receive this dispersy-sync message they will probably all send
         the same messages back.  So we need to make things smarter!

        @todo: we need to optimise this to include a bandwidth throttle.  Otherwise a node can
         easilly force us to send arbitrary large amounts of data.
        """
        # TODO we might improve performance if we made a VIEW in the database
        sql = u"""SELECT sync.packet, sync.meta_message, member.public_key
                  FROM sync
                  JOIN member ON member.id = sync.member
                  JOIN meta_message ON meta_message.id = sync.meta_message
                  WHERE sync.community = ? AND meta_message.priority > 32 AND NOT sync.undone AND sync.global_time BETWEEN ? AND ?
                  ORDER BY meta_message.priority, sync.global_time * meta_message.direction"""

        community = messages[0].community

        # obtain all available messages for this community
        meta_messages = dict((meta_message.database_id, meta_message) for meta_message in community.get_meta_messages())
        if __debug__: dprint(", ".join(meta_message.name for meta_message in community.get_meta_messages()))

        for message in messages:
            assert message.name == u"dispersy-sync", "this method is called in batches, i.e. community and meta message grouped together"
            assert message.community == community, "this method is called in batches, i.e. community and meta message grouped together"

            allowed, _ = community._timeline.check(message)
            if not allowed:
                yield DelayMessageByProof(message)
                continue

            # obtain all subjective sets for the sender of the dispersy-sync message
            subjective_sets = community.get_subjective_sets(message.authentication.member)

            # we limit the response by byte_limit bytes
            byte_limit = community.dispersy_sync_response_limit

            bloom_filter = message.payload.bloom_filter
            time_low = message.payload.time_low
            time_high = message.payload.time_high if message.payload.has_time_high else community.global_time
            packets = []

            for packet, meta_message_id, packet_public_key in self._database.execute(sql, (community.database_id, time_low, time_high)):
                packet = str(packet)
                packet_public_key = str(packet_public_key)

                if not packet in bloom_filter:
                    packet_meta = meta_messages.get(meta_message_id, None)
                    if not packet_meta:
                        if __debug__: dprint("not syncing missing unknown message (", len(packet), " bytes, id: ", meta_message_id, ")", level="warning")
                        continue

                    # check if the packet uses the SubjectiveDestination policy
                    if isinstance(packet_meta.destination, SubjectiveDestination):
                        packet_cluster = packet_meta.destination.cluster

                        # we need the subjective set for this particular cluster
                        assert packet_cluster in subjective_sets, "subjective_sets must contain all existing clusters, however, some may be None"
                        subjective_set = subjective_sets[packet_cluster]
                        if not subjective_set:
                            if __debug__: dprint("subjective set not available (not ", packet_cluster, " in ", subjective_sets.keys(), ")")
                            yield DelayMessageBySubjectiveSet(message, packet_cluster)
                            break

                        # is packet_public_key in the subjective set
                        if not packet_public_key in subjective_set:
                            if __debug__: dprint("found missing ", packet_meta.name, " not matching requestors subjective set.  not syncing")
                            continue

                    if __debug__:dprint("found missing ", packet_meta.name, " (", len(packet), " bytes)")

                    packets.append(packet)
                    byte_limit -= len(packet)
                    if byte_limit <= 0:
                        if __debug__:
                            dprint("bandwidth throttle")
                        break

            # let the message be processed, although that will not actually result in any processing
            # since we choose to already do everything...
            yield message

            if packets:
                if __debug__: dprint("syncing ", len(packets), " packets (", sum(len(packet) for packet in packets), " bytes) over [", time_low, ":", time_high, "] to " , message.address[0], ":", message.address[1])
                self._send([message.address], packets, u"-sync-")

            else:
                if __debug__: dprint("did not find anything to sync, ignoring dispersy-sync message")

    def on_sync(self, messages):
        # everything has already been done in check_sync.
        pass

    def create_authorize(self, community, permission_triplets, sign_with_master=False, store=True, update=True, forward=True):
        """
        Grant permissions to members in a community.

        This method will generate a message that grants the permissions in permission_triplets.
        Each item in permission_triplets contains (Member, Message, permission) where permission is
        either u'permit', u'authorize', or u'revoke'.

        By default, community.my_member is doing the authorization.  This means, that
        community.my_member must have the authorize permission for each of the permissions that she
        is authorizing.

        >>> # Authorize Bob to use Permit payload for 'some-message'
        >>> from Payload import Permit
        >>> bob = Member.get_instance(bob_public_key)
        >>> msg = self.get_meta_message(u"some-message")
        >>> self.create_authorize(community, [(bob, msg, u'permit')])

        @param community: The community where the permissions must be applied.
        @type sign_with_master: Community

        @param permission_triplets: The permissions that are granted.  Must be a list or tuple
         containing (Member, Message, permission) tuples.
        @type permissions_pairs: [(Member, Message, string)]

        @param sign_with_master: When True community.master_member is used to sign the authorize
         message.  Otherwise community.my_member is used.
        @type sign_with_master: bool

        @param store: When True the messages are stored (as defined by their message distribution
         policy) in the local dispersy database.  This parameter should (almost always) be True, its
         inclusion is mostly to allow certain debugging scenarios.
        @type store: bool

        @param update: When True the messages are passed to their handle_callback methods.  This
         parameter should (almost always) be True, its inclusion is mostly to allow certain
         debugging scenarios.
        @type update: bool

        @param forward: When True the messages are forwarded (as defined by their message
         destination policy) to other nodes in the community.  This parameter should (almost always)
         be True, its inclusion is mostly to allow certain debugging scenarios.
        @type store: bool
        """
        if __debug__:
            from community import Community
            from member import Member
            assert isinstance(community, Community)
            assert isinstance(permission_triplets, (tuple, list))
            for triplet in permission_triplets:
                assert isinstance(triplet, tuple)
                assert len(triplet) == 3
                assert isinstance(triplet[0], Member)
                assert isinstance(triplet[1], Message)
                assert isinstance(triplet[2], unicode)
                assert triplet[2] in (u'permit', u'authorize', u'revoke')

        meta = community.get_meta_message(u"dispersy-authorize")
        message = meta.impl(authentication=((community.master_member if sign_with_master else community.my_member),),
                            distribution=(community.claim_global_time(), self._claim_master_member_sequence_number(community, meta) if sign_with_master else meta.distribution.claim_sequence_number()),
                            payload=(permission_triplets,))

        self.store_update_forward([message], store, update, forward)
        return message

    # def check_authorize(self, messages):
    #     check = message.community._timeline.check

    #     for message in messages:
    #         allowed, proofs = check(message)
    #         if allowed:

    #             # ensure that the author has the authorize permission
    #             authorize_allowed, authorize_proofs = check(messageauthor, global_time, [(message, u"authorize") for _, message, __ in permission_triplets])
    #             if not authorize_allowed:
    #                 yield DelayMessageByProof(message)

    #             yield message
    #         else:
    #             yield DelayMessageByProof(message)

    def on_authorize(self, messages):
        """
        Process a dispersy-authorize message.

        This method is called to process a dispersy-authorize message.  This message is either
        received from an external source or locally generated.

        When the message is locally generated the address will be set to ('', -1).

        @param address: The address from where we received this message.
        @type address: (string, int)

        @param message: The received message.
        @type message: Message.Implementation
        @raise DropMessage: When unable to verify that this message is valid.
        @todo: We should raise a DelayMessageByProof to ensure that we request the proof for this
         message immediately.
        """
        for message in messages:
            message.community._timeline.authorize(message.authentication.member, message.distribution.global_time, message.payload.permission_triplets, message)

    def create_revoke(self, community, permission_triplets, sign_with_master=False, store=True, update=True, forward=True):
        """
        Revoke permissions from a members in a community.

        This method will generate a message that revokes the permissions in permission_triplets.
        Each item in permission_triplets contains (Member, Message, permission) where permission is
        either u'permit', u'authorize', or u'revoke'.

        By default, community.my_member is doing the revoking.  This means, that community.my_member
        must have the revoke permission for each of the permissions that she is revoking.

        >>> # Revoke the right of Bob to use Permit payload for 'some-message'
        >>> from Payload import Permit
        >>> bob = Member.get_instance(bob_public_key)
        >>> msg = self.get_meta_message(u"some-message")
        >>> self.create_revoke(community, [(bob, msg, u'permit')])

        @param community: The community where the permissions must be applied.
        @type sign_with_master: Community

        @param permission_triplets: The permissions that are revoked.  Must be a list or tuple
         containing (Member, Message, permission) tuples.
        @type permissions_pairs: [(Member, Message, string)]

        @param sign_with_master: When True community.master_member is used to sign the revoke
         message.  Otherwise community.my_member is used.
        @type sign_with_master: bool

        @param store: When True the messages are stored (as defined by their message distribution
         policy) in the local dispersy database.  This parameter should (almost always) be True, its
         inclusion is mostly to allow certain debugging scenarios.
        @type store: bool

        @param update: When True the messages are passed to their handle_callback methods.  This
         parameter should (almost always) be True, its inclusion is mostly to allow certain
         debugging scenarios.
        @type update: bool

        @param forward: When True the messages are forwarded (as defined by their message
         destination policy) to other nodes in the community.  This parameter should (almost always)
         be True, its inclusion is mostly to allow certain debugging scenarios.
        @type store: bool
        """
        if __debug__:
            from community import Community
            from member import Member
            assert isinstance(community, Community)
            assert isinstance(permission_triplets, (tuple, list))
            for triplet in permission_triplets:
                assert isinstance(triplet, tuple)
                assert len(triplet) == 3
                assert isinstance(triplet[0], Member)
                assert isinstance(triplet[1], Message)
                assert isinstance(triplet[2], unicode)
                assert triplet[2] in (u'permit', u'authorize', u'revoke')

        meta = community.get_meta_message(u"dispersy-revoke")
        message = meta.impl(authentication=((community.master_member if sign_with_master else community.my_member),),
                            distribution=(community.claim_global_time(), self._claim_master_member_sequence_number(community, meta) if sign_with_master else meta.distribution.claim_sequence_number()),
                            payload=(permission_triplets,))

        self.store_update_forward([message], store, update, forward)
        return message

    def on_revoke(self, messages):
        """
        Process a dispersy-revoke message.

        This method is called to process a dispersy-revoke message.  This message is either received
        from an external source or locally generated.

        When the message is locally generated the address will be set to ('', -1).

        @param address: The address from where we received this message.
        @type address: (string, int)

        @param message: The received message.
        @type message: Message.Implementation
        @raise DropMessage: When unable to verify that this message is valid.
        @todo: We should raise a DelayMessageByProof to ensure that we request the proof for this
         message immediately.
        """
        for message in messages:
            message.community._timeline.revoke(message.authentication.member, message.distribution.global_time, message.payload.permission_triplets, message)

    def create_undo(self, community, message, sign_with_master=False, store=True, update=True, forward=True):
        if __debug__:
            from community import Community
            assert isinstance(community, Community)
            assert isinstance(message, Message.Implementation)
            assert isinstance(sign_with_master, bool)
            assert sign_with_master is False, "Must be False for now.  We can enable this feature once the undo message is able to undo messages created by others"
            assert isinstance(store, bool)
            assert isinstance(update, bool)
            assert isinstance(forward, bool)
            assert community.my_member == message.authentication.member, "For now we can only undo our own messages"

        # creating a second dispersy-undo for the same message is malicious behavior (it can cause
        # infinate data traffic).  nodes that notice this behavior must blacklist the offending
        # node.  hence we ensure that we did not send an undo before
        try:
            undone, = self._database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                             (community.database_id, community.my_member.database_id, message.distribution.global_time)).next()

        except StopIteration:
            assert False, "The message that we want to undo does not exist.  Programming error"
            return None

        else:
            if undone:
                if __debug__: dprint("you are attempting to undo the same message twice.  this should never be attempted as it is considered malicious behavior", level="error")

                # already undone.  refuse to undo again but return the previous undo message
                undo_meta = community.get_meta_message(u"dispersy-undo")
                for packet_id, packet in self._database.execute(u"SELECT id, packet FROM sync WHERE community = ? AND member = ? AND meta_message = ?",
                                                      (community.database_id, community.my_member.database_id, undo_meta.database_id)):
                    msg = Packet(undo_meta, str(packet), packet_id).load_message()
                    if message.distribution.global_time == msg.payload.global_time:
                        return msg

                # could not find the undo message that caused the sync.undone to be True, this would
                # indicate a database inconsistency
                assert False, "Database inconsistency: sync.undone is True while we could not find the dispersy-undo message"
                return None

            else:
                # create the undo message
                meta = community.get_meta_message(u"dispersy-undo")
                msg = meta.impl(authentication=((community.master_member if sign_with_master else community.my_member),),
                                distribution=(community.claim_global_time(), self._claim_master_member_sequence_number(community, meta) if sign_with_master else meta.distribution.claim_sequence_number()),
                                payload=(message.authentication.member, message.distribution.global_time, message))

                assert msg.distribution.global_time > message.distribution.global_time

                self.store_update_forward([msg], store, update, forward)
                return msg

    def check_undo(self, messages):
        for message in messages:
            # ensure that the message in the payload allows undo
            if not message.payload.packet.meta.undo_callback:
                yield DropMessage(message, "message does not allow undo")
                continue

            try:
                undone, = self._database.execute(u"SELECT undone FROM sync WHERE id = ?", (message.payload.packet.packet_id,)).next()
            except StopIteration:
                assert False, "Should never occur"
                undone = 0

            if undone:
                # it is possible to create a malicious message that will be propagated
                # indefinately... two undo messages at a different global time applying to the same
                # message.  If this occurs the member can be assumed to be malicious!  the proof of
                # malicious behaviour are the two dispersy-undo messages.

                if __debug__: dprint("detected malicious behavior", level="warning")

                # search for the second offending dispersy-undo message
                community = message.community
                member = message.authentication.member
                undo_meta = community.get_meta_message(u"dispersy-undo")
                for packet_id, packet in self._database.execute(u"SELECT id, packet FROM sync WHERE community = ? AND member = ? AND meta_message = ?",
                                                      (community.database_id, member.database_id, undo_meta.database_id)):
                    msg = Packet(undo_meta, str(packet), packet_id).load_message()
                    if message.payload.global_time == msg.payload.global_time:
                        self.declare_malicious_member(member, [msg, message])

                        # the sender apparently does not have the offending dispersy-undo message, lets give
                        self._send([message.address], [msg.packet])

                        break

                if member == community.my_member:
                    if __debug__: dprint("fatal error.  apparently we are malicious", level="error")
                    pass

                yield DropMessage(message, "trying to undo a message that has already been undone")
                continue

            # check the timeline
            allowed, _ = message.community._timeline.check(message)
            if not allowed:
                yield DelayMessageByProof(message)
                continue

            yield message

    def on_undo(self, messages):
        """
        Undo a single message.
        """
        self._database.executemany(u"UPDATE sync SET undone = 1 WHERE community = ? AND member = ? AND global_time = ?",
                                   ((message.community.database_id, message.payload.member.database_id, message.payload.global_time) for message in messages))
        for meta, iterator in groupby(messages, key=lambda x: x.payload.packet.meta):
            meta.undo_callback([(message.payload.member, message.payload.global_time, message.payload.packet) for message in iterator])

    def create_destroy_community(self, community, degree, sign_with_master=False, store=True, update=True, forward=True):
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(degree, unicode)
        assert degree in (u"soft-kill", u"hard-kill")

        meta = community.get_meta_message(u"dispersy-destroy-community")
        message = meta.impl(authentication=((community.master_member if sign_with_master else community.my_member),),
                            distribution=(community.claim_global_time(),),
                            payload=(degree,))

        # in this special case we need to forward the message before processing it locally.
        # otherwise the candidate table will have been cleaned and we won't have any destination
        # addresses.
        self.store_update_forward([message], False, False, forward)

        # now store and update without forwarding.  forwarding now will result in new entries in our
        # candidate table that we just cleane.
        self.store_update_forward([message], store, update, False)
        return message

    def on_destroy_community(self, messages):
        if __debug__:
            from community import Community

        for message in messages:
            assert message.name == u"dispersy-destroy-community"
            if __debug__: dprint(message)

            community = message.community

            # let the community code cleanup first.
            new_classification = community.dispersy_cleanup_community(message)
            assert issubclass(new_classification, Community)

            # community cleanup is done.  Now we will cleanup the dispersy database.

            if message.payload.is_soft_kill:
                # soft-kill: The community is frozen.  Dispersy will retain the data it has obtained.
                # However, no messages beyond the global-time of the dispersy-destroy-community message
                # will be accepted.  Responses to dispersy-sync messages will be send like normal.
                raise NotImplementedError()

            elif message.payload.is_hard_kill:
                # hard-kill: The community is destroyed.  Dispersy will throw away everything except the
                # dispersy-destroy-community message and the authorize chain that is required to verify
                # this message.  The community should also remove all its data and cleanup as much as
                # possible.

                # delete everything except (a) all dispersy-destroy-community messages (these both
                # authorize and revoke the usage of this message) and (b) the associated
                # dispersy-identity messages to verify the dispersy-destroy-community messages.

                # todo: this should be made more efficient.  not all dispersy-destroy-community messages
                # need to be kept.  Just the ones in the chain to authorize the message that has just
                # been received.

                authorize_message_id = community.get_meta_message(u"dispersy-authorize").database_id
                destroy_message_id = community.get_meta_message(u"dispersy-destroy-community").database_id
                identity_message_id = community.get_meta_message(u"dispersy-identity").database_id

                # TODO we should only remove the 'path' of authorize and identity messages
                # leading to the destroy message

                # 1. remove all except the dispersy-authorize, dispersy-destroy-community, and
                # dispersy-identity messages
                self._database.execute(u"DELETE FROM sync WHERE community = ? AND NOT (meta_message = ? OR meta_message = ? OR meta_message = ?)", (community.database_id, authorize_message_id, destroy_message_id, identity_message_id))

                # 2. cleanup the reference_member_sync table.  however, we should keep the ones
                # that are still referenced
                self._database.execute(u"DELETE FROM reference_member_sync WHERE NOT EXISTS (SELECT * FROM sync WHERE community = ? AND sync.id = reference_member_sync.sync)", (community.database_id,))

                # 3. cleanup the candidate table.  we need nothing here anymore
                self._database.execute(u"DELETE FROM candidate WHERE community = ?", (community.database_id,))

                # 4. cleanup the malicious_proof table.  we need nothing here anymore
                self._database.execute(u"DELETE FROM malicious_proof WHERE community = ?", (community.database_id,))

            self.reclassify_community(community, new_classification)

    def create_dynamic_settings(self, community, policies, sign_with_master=False, store=True, update=True, forward=True):
        meta = community.get_meta_message(u"dispersy-dynamic-settings")
        message = meta.impl(authentication=((community.master_member if sign_with_master else community.my_member),),
                            distribution=(community.claim_global_time(), self._claim_master_member_sequence_number(community, meta) if sign_with_master else meta.distribution.claim_sequence_number()),
                            payload=(policies,))
        self.store_update_forward([message], store, update, forward)
        return message

    def on_dynamic_settings(self, messages):
        community = messages[0].community
        timeline = community._timeline
        global_time = community.global_time
        changes = {}

        for message in messages:
            if __debug__: dprint("received ", len(message.payload.policies), " policy changes")
            for meta, policy in message.payload.policies:
                # TODO currently choosing the range that changed in a naive way, only using the
                # lowest global time value
                if meta in changes:
                    range_ = changes[meta]
                else:
                    range_ = [global_time, global_time]
                    changes[meta] = range_
                range_[0] = min(message.distribution.global_time + 1, range_[0])

                # apply new policy setting
                timeline.change_resolution_policy(meta, message.distribution.global_time, policy, message)

        if __debug__: dprint("updating ", len(changes), " ranges")
        execute = self._database.execute
        executemany = self._database.executemany
        for meta, range_ in changes.iteritems():
            if __debug__: dprint(meta.name, " [", range_[0], ":", "]")
            undo = []
            redo = []

            for packet_id, packet, undone in list(execute(u"SELECT id, packet, undone FROM sync WHERE meta_message = ? AND global_time BETWEEN ? AND ?",
                                                          (meta.database_id, range_[0], range_[1]))):
                message = self.convert_packet_to_message(str(packet), community)
                if message:
                    message.packet_id = packet_id
                    allowed, _ = timeline.check(message)
                    if allowed and undone:
                        if __debug__: dprint("redo message ", message.name, " at time ", message.distribution.global_time)
                        redo.append(message)

                    elif not (allowed or undone):
                        if __debug__: dprint("undo message ", message.name, " at time ", message.distribution.global_time)
                        undo.append(message)

                    elif __debug__:
                        if __debug__: dprint("no change for message ", message.name, " at time ", message.distribution.global_time)

            if undo:
                executemany(u"UPDATE sync SET undone = 1 WHERE id = ?", ((message.packet_id,) for message in undo))
                assert self._database.changes == len(undo), (self._database.changes, len(undo))
                meta.undo_callback([(message.authentication.member, message.distribution.global_time, message) for message in undo])

            if redo:
                executemany(u"UPDATE sync SET undone = 0 WHERE id = ?", ((message.packet_id,) for message in redo))
                assert self._database.changes == len(redo), (self._database.changes, len(redo))
                meta.handle_callback(redo)

    def _generic_timeline_check(self, messages):
        meta = messages[0].meta
        if isinstance(meta.authentication, NoAuthentication):
            # we can not timeline.check this message because it uses the NoAuthentication policy
            for message in messages:
                yield message

        else:
            for message in messages:
                allowed, proofs = meta.community._timeline.check(message)
                if allowed:
                    yield message
                else:
                    yield DelayMessageByProof(message)

    def _claim_master_member_sequence_number(self, community, meta):
        """
        Tries to guess the most recent sequence number used by the master member for META in
        COMMUNITY.

        This is a risky method because sequence numbers must be unique, however, we can not
        guarantee that two peers do not claim a sequence number for the master member at around the
        same time.  Unfortunately we can not overcome this problem in a distributed fashion.

        Also note that calling this method twice will give identital values.  Ensure that the
        message is updated locally before claiming another value to ensure different sequence
        numbers are used.
        """
        assert not isinstance(meta.distribution, LastSyncDistribution), "to obtain the sequence number for a LastSyncDistribution policy we need to decode the last packet, not simply count the number of msgs in the database"
        sequence_number, = self._database.execute(u"SELECT COUNT(1) FROM sync WHERE member = ? AND sync.meta_message = ?",
                                                  (community.master_member.database_id, meta.database_id)).next()
        return sequence_number + 1

    def _periodically_create_sync(self, community):
        """
        Periodically disperse the latest bloom filters for this community.

        Every N seconds one or more dispersy-sync message will be send for community.  This may
        result in members detecting that we are missing messages and them sending them to us.

        Note that there are several magic numbers involved:

         1. The frequency of calling _periodically_create_sync.  This is determined by
            self.dispersy_sync_interval.  This defaults to 20.0 (currently).

         2. Each interval up to L bloom filters are selected and sent in seperate dispersy-sync
            messages.  This is determined by the self.dispersy_sync_bloom_count.  This defaults to 2
            (currently).

         3. Each interval each dispersy-sync message is sent to up to C different members.  This is
            determined by the self.dispersy_sync_member_count.  This defaults to 10 (currently).

         4. How many bytes -at most- are sent back in response to a received dispersy-sync message.
            This is determined by the self.dispersy_sync_response_limit.  This defaults to 5KB.
        """
        try:
            meta = community.get_meta_message(u"dispersy-sync")

        except:
            pass

        else:
            while community.dispersy_sync_initial_delay > 0.0 and community.dispersy_sync_interval > 0.0:
                messages = [meta.impl(authentication=(community.my_member,),
                                      distribution=(community.global_time,),
                                      payload=(time_low, time_high, bloom_filter))
                            for time_low, time_high, bloom_filter
                            in community.dispersy_sync_bloom_filters]
                if __debug__:
                    for message in messages:
                        dprint("requesting sync in range [", message.payload.time_low, ":", message.payload.time_high if message.payload.time_high else "inf", "] (", community.get_classification(), ")")
                self.store_update_forward(messages, False, False, True)
                yield community.dispersy_sync_interval

    def _periodically_create_candidate_request(self, community):
        try:
            meta = community.get_meta_message(u"dispersy-candidate-request")

        except:
            pass

        else:
            while community.dispersy_candidate_request_initial_delay > 0.0 and community.dispersy_candidate_request_interval > 0.0:
                minimal_age, maximal_age = community.dispersy_candidate_online_range
                limit = community.dispersy_candidate_limit
                sql = u"""SELECT host, port, STRFTIME('%s', DATETIME('now')) - STRFTIME('%s', incoming_time) AS age
                    FROM candidate
                    WHERE community = ? AND age BETWEEN ? AND ?
                    ORDER BY age
                    LIMIT ?"""
                candidates = [((str(host), port), float(age)) for host, port, age in self._database.execute(sql, (community.database_id, minimal_age, maximal_age, limit))]

                authentication_impl = meta.authentication.implement(community.my_member)
                resolution_impl = meta.resolution.implement()
                distribution_impl = meta.distribution.implement(community.global_time)
                conversion_version = community.get_conversion().version
                requests = [meta.implement(authentication_impl, resolution_impl, distribution_impl, meta.destination.implement(candidate.address), meta.payload.implement(self._my_external_address, candidate.address, conversion_version, candidates))
                            for candidate
                            in self.yield_mixed_candidates(community, community.dispersy_candidate_request_member_count)]
                if requests:
                    self.store_update_forward(requests, False, False, True)
                yield community.dispersy_candidate_request_interval

    # def _periodically_connectability(self):
    #     # unknown
    #     # public
    #     # full cone
    #     # restricted cone
    #     # port restricted cone
    #     # symetric
    #     my_internal_address = self._socket.get_address()
    #     while True:
    #         dprint("internal: ", my_internal_address, "; external: ", self._my_external_address, box=1)

    #         for i, _ in enumerate(self._database.execute(u"SELECT STRFTIME('%s', DATETIME('now')) - STRFTIME('%s', incoming_time) AS incoming_age, STRFTIME('%s', DATETIME('now')) - STRFTIME('%s', outgoing_time) AS outgoing_age FROM candidate WHERE incoming_age < 300 AND incoming_age > outgoing_age")):
    #             dprint("incoming before outgoing")
    #             break

    #         yield 5.0

    def _periodically_cleanup_database(self):
        # cleannup candidate tables
        while True:
            yield 120.0

            for community in self._communities.itervalues():
                self._database.execute(u"DELETE FROM candidate WHERE community = ? AND STRFTIME('%s', DATETIME('now')) - STRFTIME('%s', incoming_time) > ?",
                                       (community.database_id, community.dispersy_candidate_cleanup_age_threshold))

    def _watchdog(self):
        """
        Periodically called to flush changes to disk, most importantly, it will catch the
        GeneratorExit exception when it is thrown to properly shutdown the database.
        """
        while True:
            try:
                yield 300.0
                # flush changes to disk every 5 minutes
                self._database.commit()
            except GeneratorExit:
                if __debug__: dprint("shutdown")
                self._database.commit()
                break

    def info(self, statistics=True, transfers=True, attributes=True, sync_ranges=True, database_sync=True, candidate=True):
        """
        Returns a dictionary with runtime statistical information.

        The dictionary should only contain simple data types such as dictionaries, lists, tuples,
        strings, integers, etc.  Just no objects, methods, and the like.

        Depending on __debug__ more or less information may be available.  Note that Release
        versions do NOT run __debug__ mode and will hence return less information.
        """
        # when something is removed or changed, the major version number is incremented.  when
        # somethind is added, the minor version number is incremented.

        # 1.1: added info["statistics"]
        # 1.2: bugfix in Community.free_sync_range, should free more ranges; changed
        #      dispersy_candidate_request_member_count to 3 down from 10
        # 1.3: bugfix in dispersy.py where messages with identicat payload (fully binary unique)
        #      could be generated with a different signature (a signature contains random elements)
        #      making the two unique messages different from a bloom filter perspective.  we now
        #      replace one message with the other thoughout the system.
        # 1.4: added info["statistics"]["outgoing"] containing all calls to _send(...)
        # 1.5: replaced some dispersy_candidaye_... attributes and added a dump of the candidates

        info = {"version":1.5, "class":"Dispersy"}

        if statistics:
            info["statistics"] = self._statistics.reset()
            # if __debug__: dprint(info["statistics"], pprint=1)

        info["communities"] = []
        for community in self._communities.itervalues():
            community_info = {"classification":community.get_classification(), "hex_cid":community.cid.encode("HEX"), "global_time":community.global_time}
            info["communities"].append(community_info)

            if attributes:
                community_info["attributes"] = dict((attr, getattr(community, attr))
                                                    for attr
                                                    in ("dispersy_candidate_request_initial_delay",
                                                        "dispersy_candidate_request_interval",
                                                        "dispersy_candidate_request_member_count",
                                                        "dispersy_candidate_cleanup_age_threshold",
                                                        "dispersy_candidate_limit",
                                                        "dispersy_candidate_online_range",
                                                        "dispersy_candidate_online_scores",
                                                        "dispersy_candidate_direct_observation_score",
                                                        "dispersy_candidate_indirect_observation_score",
                                                        "dispersy_candidate_subjective_set_score",
                                                        "dispersy_candidate_probabilistic_factor",
                                                        "dispersy_sync_initial_delay",
                                                        "dispersy_sync_interval",
                                                        "dispersy_sync_bloom_filter_error_rate",
                                                        "dispersy_sync_bloom_filter_bits",
                                                        "dispersy_sync_member_count",
                                                        "dispersy_sync_response_limit",
                                                        "dispersy_missing_sequence_response_limit"))

            if sync_ranges:
                community_info["sync_ranges"] = [{"time_low":range.time_low, "space_freed":range.space_freed, "space_remaining":range.space_remaining, "capacity":range.capacity}
                                                 for range
                                                 in community._sync_ranges]

            if database_sync:
                community_info["database_sync"] = dict(self._database.execute(u"SELECT meta_message.name, COUNT(sync.id) FROM sync JOIN meta_message ON meta_message.id = sync.meta_message WHERE sync.community = ? GROUP BY sync.meta_message", (community.database_id,)))

            if candidate:
                incoming_time_low, incoming_time_high = community.dispersy_candidate_online_range
                sql = u"""
SELECT host, port, STRFTIME('%s', 'now') - STRFTIME('%s', incoming_time) AS age, STRFTIME('%s', 'now') - STRFTIME('%s', outgoing_time), STRFTIME('%%s', 'now') - STRFTIME('%s', external_time)
FROM candidate
WHERE community = ? AND age BETWEEN ? AND ?
"""

                online = [(str(host), port, incoming_age, outgoing_age, external_age)
                          for host, port, incoming_age, outgoing_age, external_age
                          in self._database.execute(sql, (community.database_id, incoming_time_low, incoming_time_high))]
                total, = self._database.execute(u"SELECT COUNT(1) FROM candidate WHERE community = ?", (community.database_id,)).next()
                community_info["candidates"] = {"online":online, "total":total}

        if __debug__: dprint(info, pprint=True)
        return info
