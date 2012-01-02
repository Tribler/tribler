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
connect-ability problems since UDP packets are much easier to pass though NAT's and firewalls.

Earlier we hinted that messages can have different policies.  A message has the following four
different policies, and each policy defines how a specific part of the message should be handled.

 - Authentication defines if the message is signed, and if so, by how many members.

 - Resolution defines how the permission system should resolve conflicts between messages.

 - Distribution defines if the message is send once or if it should be gossiped around.  In the
   latter case, it can also define how many messages should be kept in the network.

 - Destination defines to whom the message should be send or gossiped.

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

from hashlib import sha1
from itertools import groupby, islice, count
from os.path import abspath
from random import random, choice, shuffle
from socket import inet_aton, error as socket_error
from time import time

from decorator import runtime_duration_warning
from authentication import NoAuthentication, MemberAuthentication, MultiMemberAuthentication
from bloomfilter import BloomFilter
from bootstrap import get_bootstrap_addresses
from callback import Callback, Idle, Return
from candidate import BootstrapCandidate, Candidate, LocalhostCandidate
from destination import CommunityDestination, CandidateDestination, MemberDestination, SubjectiveDestination
from dispersydatabase import DispersyDatabase
from distribution import SyncDistribution, FullSyncDistribution, LastSyncDistribution, DirectDistribution
from member import Member
from message import DropMessage, DelayMessage, DelayMessageByProof, DelayMessageBySequence, DelayMessageBySubjectiveSet
from message import DropPacket, DelayPacket
from message import BatchConfiguration, Packet, Message
from payload import AuthorizePayload, RevokePayload, UndoPayload
from payload import DestroyCommunityPayload
from payload import DynamicSettingsPayload
from payload import IdentityPayload, MissingIdentityPayload
from payload import IntroductionRequestPayload, IntroductionResponsePayload, PunctureRequestPayload, PuncturePayload
from payload import MissingMessagePayload
from payload import MissingSequencePayload, MissingProofPayload
from payload import SignatureRequestPayload, SignatureResponsePayload
from payload import SubjectiveSetPayload, MissingSubjectiveSetPayload
from resolution import PublicResolution, LinearResolution
from singleton import Singleton
from trigger import TriggerCallback, TriggerPacket, TriggerMessage

from Tribler.Core.NATFirewall.guessip import get_my_wan_ip

if __debug__:
    from dprint import dprint

# callback priorities.  note that a lower value is less priority
WATCHDOG_PRIORITY = -1
CANDIDATE_WALKER_PRIORITY = -1
TRIGGER_CHECK_PRIORITY = -1
TRIGGER_TIMEOUT_PRIORITY = -2
assert isinstance(WATCHDOG_PRIORITY, int)
assert isinstance(CANDIDATE_WALKER_PRIORITY, int)
assert isinstance(TRIGGER_CHECK_PRIORITY, int)
assert isinstance(TRIGGER_TIMEOUT_PRIORITY, int)
assert TRIGGER_TIMEOUT_PRIORITY < TRIGGER_CHECK_PRIORITY, "an existing trigger should not timeout before being checked"

# the callback identifier for the task that periodically takes a step
CANDIDATE_WALKER_CALLBACK_ID = "dispersy-candidate-walker"

class DummySocket(object):
    """
    A dummy socket class.

    When Dispersy starts it does not yet have a socket object, however, it may (under certain
    conditions) start sending packets anyway.

    To avoid problems we initialize the Dispersy socket to this dummy object that will do nothing
    but throw away all packets it is supposed to sent.
    """
    def get_address(self):
        return 0

    def send(self, address, data):
        if __debug__: dprint("Thrown away ", len(data), " bytes worth of outgoing data to ", address[0], ":", address[1], level="warning")

class Statistics(object):
    def __init__(self):
        self._start = time()
        self._drop = {}
        self._delay = {}
        self._success = {}
        self._outgoing = {}
        self._sequence_number = 0
        self._total_up = 0, 0
        self._total_down = 0, 0
        self._busy_time = 0.0

    @property
    def total_up(self):
        return self._total_up

    @property
    def total_down(self):
        return self._total_down

    def info(self):
        """
        Returns all statistics.
        """
        return {"drop":self._drop,
                "delay":self._delay,
                "success":self._success,
                "outgoing":self._outgoing,
                "sequence_number":self._sequence_number,
                "total_up":self._total_up,
                "total_down":self._total_down,
                "busy_time":self._busy_time,
                "start":self._start,
                "runtime":time() - self._start}

    def summary(self):
        """
        Returns a summary of the statistics.

        Essentially it removes all address specific information.
        """
        info = self.info()
        outgoing = {}
        for subdict in info["outgoing"].itervalues():
            for key, (amount, byte_count) in subdict.iteritems():
                a, b = outgoing.get(key, (0, 0))
                outgoing[key] = (a+amount, b+byte_count)
        info["outgoing"] = outgoing
        return info

    def reset(self):
        """
        Returns, and subsequently removes, all statistics.
        """
        try:
            return self.info()

        finally:
            self._drop = {}
            self._delay = {}
            self._success = {}
            self._outgoing = {}
            self._sequence_number += 1
            self._total_up = 0, 0
            self._total_down = 0, 0

    def drop(self, key, byte_count, amount=1):
        """
        Called when an incoming packet or message failed a check and was dropped.
        """
        assert isinstance(key, (str, unicode))
        assert isinstance(byte_count, (int, long))
        assert isinstance(amount, (int, long))
        a, b = self._drop.get(key, (0, 0))
        self._drop[key] = (a+amount, b+byte_count)

    def delay(self, key, byte_count, amount=1):
        """
        Called when an incoming packet or message was delayed.
        """
        assert isinstance(key, (str, unicode))
        assert isinstance(byte_count, (int, long))
        assert isinstance(amount, (int, long))
        a, b = self._delay.get(key, (0, 0))
        self._delay[key] = (a+amount, b+byte_count)

    def success(self, key, byte_count, amount=1):
        """
        Called when an incoming message was accepted.
        """
        assert isinstance(key, (str, unicode))
        assert isinstance(byte_count, (int, long))
        assert isinstance(amount, (int, long))
        a, b = self._success.get(key, (0, 0))
        self._success[key] = (a+amount, b+byte_count)

    def outgoing(self, address, key, byte_count, amount=1):
        """
        Called when a message send using the _send(...) method
        """
        assert isinstance(address, tuple)
        assert len(address) == 2
        assert isinstance(address[0], str)
        assert isinstance(address[1], int)
        assert isinstance(key, (str, unicode))
        assert isinstance(byte_count, (int, long))
        assert isinstance(amount, (int, long))
        subdict = self._outgoing.setdefault(address, {})
        a, b = subdict.get(key, (0, 0))
        subdict[key] = (a+amount, b+byte_count)

    def increment_total_up(self, byte_count, amount):
        assert isinstance(byte_count, (int, long))
        assert isinstance(amount, (int, long))
        a, b = self._total_up
        self._total_up = (a+amount, b+byte_count)

    def increment_total_down(self, byte_count, amount):
        assert isinstance(byte_count, (int, long))
        a, b = self._total_down
        self._total_down = (a+amount, b+byte_count)

    def increment_busy_time(self, busy_time):
        assert isinstance(busy_time, float)
        self._busy_time += busy_time

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

        super(Dispersy, self).__init__()

        # the raw server
        self._callback = callback

        # batch caching incoming packets
        self._batch_cache = {}

        # where we store all data
        self._working_directory = abspath(working_directory)

        # our data storage
        self._database = DispersyDatabase.get_instance(working_directory)

        # peer selection candidates.  address:Candidate pairs (where
        # address is obtained from socket.recv_from)
        self._candidates = {}

        # random numbers in the range [0:2**16) that are used to match outgoing
        # introduction-request, incoming introduction-response, and incoming puncture.
        # identifier:introduced-candidate pairs, where introduced-candidate is None until either the
        # introduction-response of the puncture is received
        self._walk_identifiers = {}

        # indicates what our connection type is.  currently it can be u"unknown", u"public", or
        # u"symmetric-NAT"
        self._connection_type = u"unknown"

        # our LAN and WAN addresses
        self._lan_address = (get_my_wan_ip() or "0.0.0.0", 0)

        try:
            host, = self._database.execute(u"SELECT value FROM option WHERE key = 'my_wan_ip' LIMIT 1").next()
            host = str(host)
        except StopIteration:
            host = self._lan_address[0]

        try:
            port, = self._database.execute(u"SELECT value FROM option WHERE key = 'my_wan_port' LIMIT 1").next()
        except StopIteration:
            port = self._lan_address[1]

        self._wan_address = (host, port)
        self._wan_address_votes = {self._wan_address:set()}
        self.wan_address_vote(self._wan_address, ("", -1))
        if __debug__:
            dprint("my lan address is ", self._lan_address[0], ":", self._lan_address[1], force=True)
            dprint("my wan address is ", self._wan_address[0], ":", self._wan_address[1], force=True)

        # bootstrap peers
        bootstrap_addresses = get_bootstrap_addresses()
        self._bootstrap_candidates = dict((address, BootstrapCandidate(address)) for address in bootstrap_addresses if address)
        assert isinstance(self._bootstrap_candidates, dict)
        if not all(bootstrap_addresses):
            self._callback.register(self._retry_bootstrap_candidates)

        # communities that can be auto loaded.  classification:(cls, args, kargs) pairs.
        self._auto_load_communities = {}

        # loaded communities.  cid:Community pairs.
        self._communities = {}
        self._walker_commmunities = []

        # outgoing communication
        self._socket = DummySocket()

        # triggers for incoming messages
        self._triggers = []
        self._untriggered_messages = []

        self._check_distribution_batch_map = {DirectDistribution:self._check_direct_distribution_batch,
                                              FullSyncDistribution:self._check_full_sync_distribution_batch,
                                              LastSyncDistribution:self._check_last_sync_distribution_batch}

        # commit changes to the database periodically
        self._callback.register(self._watchdog, priority=WATCHDOG_PRIORITY)

        # statistics...
        self._statistics = Statistics()

        if __debug__:
            self._callback.register(self._stats_candidates)
            self._callback.register(self._stats_conversion)
            self._callback.register(self._stats_triggers)
            self._callback.register(self._stats_info)

    def _retry_bootstrap_candidates(self):
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
                self._bootstrap_candidates = dict((address, BootstrapCandidate(address)) for address in addresses if address)
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

        host, port = socket.get_address()
        if __debug__: dprint("update lan address ", self._lan_address[0], ":", self._lan_address[1], " -> ", self._lan_address[0], ":", port, force=True)
        self._lan_address = (self._lan_address[0], port)

        if not self._is_valid_lan_address(self._lan_address, check_my_lan_address=False):
            if __debug__: dprint("update lan address ", self._lan_address[0], ":", self._lan_address[1], " -> ", host, ":", self._lan_address[1], force=True)
            self._lan_address = (host, self._lan_address[1])

        if not self._is_valid_lan_address(self._lan_address, check_my_lan_address=False):
            if __debug__: dprint("update lan address ", self._lan_address[0], ":", self._lan_address[1], " -> ", self._wan_address[0], ":", self._lan_address[1], force=True)
            self._lan_address = (self._wan_address[0], self._lan_address[1])

        # our address may not be a bootstrap address
        if self._lan_address in self._bootstrap_candidates:
            del self._bootstrap_candidates[self._lan_address]

        # our address may not be a candidate
        if self._lan_address in self._candidates:
            del self._candidates[self._lan_address]

        self.wan_address_vote(self._lan_address, ("", -1))
    # .setter was introduced in Python 2.6
    socket = property(__get_socket, __set_socket)

    @property
    def lan_address(self):
        """
        The LAN address where we believe people who are inside our LAN can find us.

        Our LAN address is determined by the default gateway of our
        system and our port.

        @rtype: (str, int)
        """
        return self._lan_address

    @property
    def wan_address(self):
        """
        The wan address where we believe that we can be found from outside our LAN.

        Our wan address is determined by majority voting.  Each time when we receive a message
        that contains an opinion about our wan address, we take this into account.  The
        address with the most votes wins.

        Votes can be added by calling the wan_address_vote(...) method.

        Usually these votes are received through dispersy-introduction-request and
        dispersy-introduction-response messages.

        @rtype: (str, int)
        """
        return self._wan_address

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
            # pylint: disable-msg=W0404
            from community import Community
        assert isinstance(community, Community)
        messages = [Message(community, u"dispersy-identity", MemberAuthentication(encoding="bin"), PublicResolution(), LastSyncDistribution(synchronization_direction=u"ASC", priority=16, history_size=1), CommunityDestination(node_count=0), IdentityPayload(), self._generic_timeline_check, self.on_identity, batch=BatchConfiguration(max_window=1.0, priority=512)),
                    Message(community, u"dispersy-signature-request", NoAuthentication(), PublicResolution(), DirectDistribution(), MemberDestination(), SignatureRequestPayload(), self.check_signature_request, self.on_signature_request),
                    Message(community, u"dispersy-signature-response", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), SignatureResponsePayload(), self._generic_timeline_check, self.on_signature_response),
                    Message(community, u"dispersy-authorize", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=10), AuthorizePayload(), self._generic_timeline_check, self.on_authorize, batch=BatchConfiguration(max_window=1.0, priority=504)),
                    Message(community, u"dispersy-revoke", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=10), RevokePayload(), self._generic_timeline_check, self.on_revoke, batch=BatchConfiguration(max_window=1.0, priority=504)),
                    Message(community, u"dispersy-undo-own", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=10), UndoPayload(), self.check_undo, self.on_undo, batch=BatchConfiguration(max_window=1.0, priority=500)),
                    Message(community, u"dispersy-undo-other", MemberAuthentication(), LinearResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=10), UndoPayload(), self.check_undo, self.on_undo, batch=BatchConfiguration(max_window=1.0, priority=500)),
                    Message(community, u"dispersy-destroy-community", MemberAuthentication(), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=192), CommunityDestination(node_count=50), DestroyCommunityPayload(), self._generic_timeline_check, self.on_destroy_community),
                    Message(community, u"dispersy-subjective-set", MemberAuthentication(), PublicResolution(), LastSyncDistribution(synchronization_direction=u"ASC", priority=16, history_size=1), CommunityDestination(node_count=0), SubjectiveSetPayload(), self._generic_timeline_check, self.on_subjective_set, batch=BatchConfiguration(max_window=1.0)),
                    Message(community, u"dispersy-dynamic-settings", MemberAuthentication(), LinearResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"DESC", priority=191), CommunityDestination(node_count=10), DynamicSettingsPayload(), self._generic_timeline_check, community.dispersy_on_dynamic_settings),

                    #
                    # when something is missing, a dispersy-missing-... message can be used to request
                    # it from another peer
                    #

                    # when we have a member id (20 byte sha1 of the public key) but not the public key
                    Message(community, u"dispersy-missing-identity", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), MissingIdentityPayload(), self._generic_timeline_check, self.on_missing_identity),

                    # when we are missing one or more SyncDistribution messages in a certain sequence
                    Message(community, u"dispersy-missing-sequence", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), MissingSequencePayload(), self._generic_timeline_check, self.on_missing_sequence),

                    # when we have a reference to a message that we do not have.  a reference consists
                    # of the community identifier, the member identifier, and the global time
                    Message(community, u"dispersy-missing-message", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), MissingMessagePayload(), self._generic_timeline_check, self.on_missing_message),

                    # when we are missing the subjective set, with a specific cluster, from a member
                    Message(community, u"dispersy-missing-subjective-set", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), MissingSubjectiveSetPayload(), self._generic_timeline_check, self.on_missing_subjective_set),

                    # when we might be missing a dispersy-authorize message
                    Message(community, u"dispersy-missing-proof", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), MissingProofPayload(), self._generic_timeline_check, self.on_missing_proof),

                    # when we are missing one or more LastSyncDistribution messages from a single member
                    # ... so far we do not need a generic missing-last message.  unfortunately all
                    # ... messages that it could replace contain payload specific things that make it
                    # ... difficult, if not impossible, to replace
                    # Message(community, u"dispersy-missing-last", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), MissingLastPayload(), self.check_missing_last, self.on_missing_last, delay=0.0),
                    ]

        if community.dispersy_enable_candidate_walker_responses:
            messages.extend([Message(community, u"dispersy-introduction-request", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), IntroductionRequestPayload(), self.check_sync, self.on_introduction_request, batch=BatchConfiguration(max_window=0.1, max_age=5.0)),
                             Message(community, u"dispersy-introduction-response", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), IntroductionResponsePayload(), self.check_introduction_response, self.on_introduction_response, batch=BatchConfiguration(max_window=0.1, max_age=5.0)),
                             Message(community, u"dispersy-puncture-request", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PunctureRequestPayload(), self._generic_timeline_check, self.on_puncture_request, batch=BatchConfiguration(max_window=0.1, max_age=4.0)),
                             Message(community, u"dispersy-puncture", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PuncturePayload(), self.check_puncture, self.on_puncture, batch=BatchConfiguration(max_window=0.1, max_age=5.0))])

        return messages

    def define_auto_load(self, community, args=(), kargs=None):
        """
        Tell Dispersy how to load COMMUNITY is needed.

        COMMUNITY is the community class that is defined.

        ARGS an KARGS are optional arguments and keyword arguments used when a community is loaded
        using COMMUNITY.load_community(master, *ARGS, **KARGS).
        """
        if __debug__:
            # pylint: disable-msg=W0404
            from community import Community
        assert issubclass(community, Community)
        assert isinstance(args, tuple)
        assert kargs is None or isinstance(kargs, dict)
        assert not community.get_classification() in self._auto_load_communities
        self._auto_load_communities[community.get_classification()] = (community, args, kargs if kargs else {})

    def undefine_auto_load(self, community):
        """
        Tell Dispersy to no longer load COMMUNITY.

        COMMUNITY is the community class that is defined.
        """
        if __debug__:
            # pylint: disable-msg=W0404
            from community import Community
        assert issubclass(community, Community)
        assert community.get_classification() in self._auto_load_communities
        del self._auto_load_communities[community.get_classification()]

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
            # pylint: disable-msg=W0404
            from community import Community
        assert isinstance(community, Community)
        if __debug__: dprint(community.cid.encode("HEX"), " ", community.get_classification())
        assert not community.cid in self._communities
        assert not community in self._walker_commmunities
        self._communities[community.cid] = community

        if community.dispersy_enable_candidate_walker:
            self._walker_commmunities.insert(0, community)
            # restart walker scheduler
            self._callback.replace_register(CANDIDATE_WALKER_CALLBACK_ID, self._candidate_walker, priority=CANDIDATE_WALKER_PRIORITY)

        # schedule the sanity check... it also checks that the dispersy-identity is available and
        # when this is a create or join this message is created only after the attach_community
        if __debug__:
            def sanity_check_callback(result):
                assert result == True, [community.database_id, str(result)]
                try:
                    community._pending_callbacks.remove(callback_id)
                except ValueError:
                    pass
            callback_id = self._callback.register(self.sanity_check_generator, (community,), priority=-128, callback=sanity_check_callback)
            community._pending_callbacks.append(callback_id)

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
            # pylint: disable-msg=W0404
            from community import Community
        assert isinstance(community, Community)
        if __debug__: dprint(community.cid.encode("HEX"), " ", community.get_classification())
        assert community.cid in self._communities
        assert self._communities[community.cid] == community
        assert not community.dispersy_enable_candidate_walker or community in self._walker_commmunities, [community.dispersy_enable_candidate_walker, community in self._walker_commmunities]
        del self._communities[community.cid]

        if community.dispersy_enable_candidate_walker:
            self._walker_commmunities.remove(community)
            # restart walker scheduler
            self._callback.replace_register(CANDIDATE_WALKER_CALLBACK_ID, self._candidate_walker, priority=CANDIDATE_WALKER_PRIORITY)

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
            # pylint: disable-msg=W0404
            from community import Community
        assert isinstance(source, (Community, Member))
        assert issubclass(destination, Community)

        destination_classification = destination.get_classification()

        if isinstance(source, Member):
            if __debug__: dprint("reclassify ??? -> ", destination_classification)
            master = source

        else:
            if __debug__: dprint("reclassify ", source.get_classification(), " -> ", destination_classification)
            assert source.cid in self._communities
            assert self._communities[source.cid] == source
            master = source.master_member
            source.unload_community()

        self._database.execute(u"UPDATE community SET classification = ? WHERE master = ?",
                               (destination_classification, master.database_id))
        assert self._database.changes == 1

        if destination_classification in self._auto_load_communities:
            cls, args, kargs = self._auto_load_communities[destination_classification]
            assert cls == destination, [cls, destination]
        else:
            args = ()
            kargs = {}

        return destination.load_community(master, *args, **kargs)

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

                    if classification in self._auto_load_communities:
                        # master_public_key may be None
                        if master_public_key:
                            master_public_key = str(master_public_key)
                            master = Member.get_instance(str(master_public_key))
                        else:
                            master = Member.get_instance(cid, public_key_available=False)

                        cls, args, kargs = self._auto_load_communities[classification]
                        cls.load_community(master, *args, **kargs)
                        assert master.mid in self._communities

                    else:
                        if __debug__: dprint("unable to auto load, '", classification, "' is an undefined classification", level="error")

                else:
                    if __debug__: dprint("not allowed to load '", classification, "'")

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
            return community.get_conversion(packet[:22]).decode_message(LocalhostCandidate(self), packet)

    def get_candidate(self, address):
        """
        Returns a candidate for address
        """
        candidate = self._candidates.get(address)
        return candidate if candidate else Candidate(address, address, address)

    def wan_address_vote(self, address, voter_address):
        """
        Add one vote and possibly re-determine our wan address.

        Our wan address is determined by majority voting.  Each time when we receive a message
        that contains anothers opinion about our wan address, we take this into account.  The
        address with the most votes wins.

        Usually these votes are received through dispersy-candidate-request and
        dispersy-candidate-response messages.

        @param address: The wan address that the voter believes us to have.
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
        if self._is_valid_wan_address(address, check_my_wan_address=False):
            if not address in self._wan_address_votes:
                self._wan_address_votes[address] = set()
            self._wan_address_votes[address].add(voter_address)

            # change when new vote count equal or higher than old address vote count
            if self._wan_address != address and len(self._wan_address_votes[address]) >= len(self._wan_address_votes[self._wan_address]):
                if len(self._wan_address_votes[address]) == 1 and len(self._wan_address_votes[self._wan_address]) == 1:
                    if __debug__: dprint("not updating WAN address, suspect symmetric NAT")
                    self._connection_type = u"symmetric-NAT"
                    return

                if __debug__:
                    dprint("update WAN address ", self._wan_address[0], ":", self._wan_address[1], " -> ", address[0], ":", address[1], force=True)
                    dprint([(x, len(votes)) for x, votes in self._wan_address_votes.iteritems()], lines=True)

                self._wan_address = address
                self._database.execute(u"REPLACE INTO option (key, value) VALUES ('my_wan_ip', ?)", (unicode(address[0]),))
                self._database.execute(u"REPLACE INTO option (key, value) VALUES ('my_wan_port', ?)", (address[1],))

                if not self._is_valid_lan_address(self._lan_address, check_my_lan_address=False):
                    if __debug__: dprint("update lan address ", self._lan_address[0], ":", self._lan_address[1], " -> ", self._wan_address[0], ":", self._lan_address[1], force=True)
                    self._lan_address = (self._wan_address[0], self._lan_address[1])

                # our address may not be a bootstrap address
                if self._wan_address in self._bootstrap_candidates:
                    del self._bootstrap_candidates[self._wan_address]

                # our address may not be a candidate
                if self._wan_address in self._candidates:
                    del self._candidates[self._wan_address]

            if __debug__: dprint("got invalid external vote from ", voter_address[0],":",voter_address[1], " received ", address[0], ":", address[1])

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
            packet, = self._database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                             (message.community.database_id, message.authentication.member.database_id, message.distribution.global_time)).next()
        except StopIteration:
            # we are checking two messages just received in the same batch
            # process the message
            return False

        else:
            packet = str(packet)
            if packet == message.packet:
                # exact duplicates, do NOT process the message
                if __debug__: dprint("received identical message [member:", message.authentication.member.database_id, "; @", message.distribution.global_time, "]", level="warning")
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

                        # notify that global times have changed
                        # message.community.update_sync_range(message.meta, [message.distribution.global_time])

                else:
                    if __debug__: dprint("received message with duplicate community/member/global-time triplet.  possibly malicious behavior", level="warning")

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
        assert all(isinstance(message, Message.Implementation) for message in messages)
        assert all(message.community == messages[0].community for message in messages)
        assert all(message.meta == messages[0].meta for message in messages)

        # a message is considered unique when (creator, global-time), i.r. (authentication.member,
        # distribution.global_time), is unique.
        unique = set()
        execute = self._database.execute
        enable_sequence_number = messages[0].meta.distribution.enable_sequence_number

        # sort the messages by their (1) global_time and (2) binary packet
        messages = sorted(messages, lambda a, b: cmp(a.distribution.global_time, b.distribution.global_time) or cmp(a.packet, b.packet))

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
                        yield DropMessage(message, "duplicate message by sequence_number (we have %d, message has %d)"%(seq, message.distribution.sequence_number))

                    elif seq + 1 == message.distribution.sequence_number:
                        # we have the previous message, check for duplicates based on community,
                        # member, and global_time
                        if self._check_identical_payload_with_different_signature(message):
                            # we have the previous message (drop)
                            yield DropMessage(message, "duplicate message by global_time (1)")
                        else:
                            # we accept this message
                            highest[message.authentication.member] += 1
                            yield message

                        # try:
                        #     execute(u"SELECT 1 FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                        #             (message.community.database_id, message.authentication.member.database_id, message.distribution.global_time)).next()

                        # except StopIteration:
                        #     # we accept this message
                        #     highest[message.authentication.member] += 1
                        #     yield message

                        # else:
                        #     # we have the previous message (drop)
                        #     if self._check_identical_payload_with_different_signature(message):
                        #         yield DropMessage(message, "duplicate message by global_time (1)")

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
                    if self._check_identical_payload_with_different_signature(message):
                        # we have the previous message (drop)
                        yield DropMessage(message, "duplicate message by global_time (2)")
                    else:
                        # we accept this message
                        yield message

                    # # check for duplicates based on community, member, and global_time
                    # try:
                    #     execute(u"SELECT 1 FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                    #             (message.community.database_id, message.authentication.member.database_id, message.distribution.global_time)).next()

                    # except StopIteration:
                    #     # we accept this message
                    #     yield message

                    # else:
                    #     # we have the previous message (drop)
                    #     if self._check_identical_payload_with_different_signature(message):
                    #         yield DropMessage(message, "duplicate message by global_time (2)")

    def _check_last_sync_distribution_batch(self, messages):
        """
        Check that the messages do not violate any database consistency rules.

        This method is called when a batch of messages with the LastSyncDistribution policy is
        received.  An iterator will be returned where each element is either: DropMessage (for
        duplicate and old messages), DelayMessage (for messages that requires something before they
        can be processed), or Message.Implementation when the message does not violate any rules.

        The rules:

         - The combination community, member, global_time must be unique.

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

        @return: A generator with Message.Implementation or DropMessage instances
        @rtype: [Message.Implementation|DropMessage]
        """
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert all(isinstance(message, Message.Implementation) for message in messages)
        assert all(message.community == messages[0].community for message in messages)
        assert all(message.meta == messages[0].meta for message in messages)
        assert all(isinstance(message.authentication, (MemberAuthentication.Implementation, MultiMemberAuthentication.Implementation)) for message in messages)

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

                if not message.authentication.member in times:
                    times[message.authentication.member] = [global_time for global_time, in self._database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?",
                                                                                                                   (message.community.database_id, message.authentication.member.database_id, message.database_id))]
                    assert len(times[message.authentication.member]) <= message.distribution.history_size, [message.packet_id, message.distribution.history_size, times[message.authentication.member]]
                tim = times[message.authentication.member]

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
                            self._send([message.candidate], [str(packet)], u"-sequence-")

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

                    if self._check_identical_payload_with_different_signature(message):
                        # we have the previous message (drop)
                        return DropMessage(message, "duplicate message by member^global_time (4)")

                    # # ensure that the community / member / global_time is always unique
                    # try:
                    #     self._database.execute(u"SELECT 1 FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                    #                            (message.community.database_id, message.authentication.member.database_id, message.distribution.global_time)).next()
                    # except StopIteration:
                    #     pass
                    # else:
                    #     # we have the previous message (drop)
                    #     if self._check_identical_payload_with_different_signature(message):
                    #         return DropMessage(message, "duplicate message by member^global_time (4)")

                    if not members in times:
                        # the next query obtains a list with all global times that we have in the
                        # database for all message.meta messages that were signed by
                        # message.authentication.members where the order of signing is not taken
                        # into account.
                        times[members] = [global_time
                                          for count_, global_time
                                          in self._database.execute(u"""
                                                SELECT COUNT(*), sync.global_time
                                                FROM sync
                                                JOIN reference_member_sync ON reference_member_sync.sync = sync.id
                                                WHERE sync.community = ? AND sync.meta_message = ? AND reference_member_sync.member IN (%s)
                                                GROUP BY sync.id
                                                """ % ", ".join("?" for _ in xrange(len(members))),
                                                                    (message.community.database_id, message.database_id) + members)
                                          if count_ == message.authentication.count]
                        assert len(times[members]) <= message.distribution.history_size
                    tim = times[members]

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
                                       for count_, packet
                                       in self._database.execute(u"""
                                       SELECT COUNT(*), sync.packet
                                       FROM sync
                                       JOIN reference_member_sync ON reference_member_sync.sync = sync.id
                                       WHERE sync.community = ? AND sync.global_time = ? AND sync.meta_message = ? AND reference_member_sync.member IN (%s)
                                       GROUP BY sync.id
                                       """ % ", ".join("?" for _ in xrange(len(members))),
                                                                 (message.community.database_id, tim[0], message.database_id) + members)
                                       if count_ == message.authentication.count]

                            if packets:
                                assert len(packets) == 1
                                self._send([message.candidate], [str(packet) for packet in packets], u"-sequence-")

                            else:
                                # TODO can still fail when packet is in one of the received messages
                                # from this batch.
                                pass

                        return DropMessage(message, "old message by members^global_time")

                    else:
                        # we accept this message
                        tim.append(message.distribution.global_time)
                        return message

        # meta message
        meta = messages[0].meta

        # sort the messages by their (1) global_time and (2) binary packet
        messages = sorted(messages, lambda a, b: cmp(a.distribution.global_time, b.distribution.global_time) or cmp(a.packet, b.packet))

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
        return sorted(messages, lambda a, b: cmp(a.distribution.global_time, b.distribution.global_time) or cmp(a.packet, b.packet))

    def data_came_in(self, packets):
        """
        UDP packets were received from the Tribler rawserver.

        This must be called on the Triber rawserver thread.  It will add the packets to the Dispersy
        Callback thread for processing.
        """
        assert isinstance(packets, list), packets
        assert all(isinstance(tup, tuple) for tup in packets), packets
        assert all(len(tup) == 2 for tup in packets), packets
        assert all(isinstance(tup[0], tuple) for tup in packets), packets
        assert all(isinstance(tup[1], str) for tup in packets), packets
        candidates = {}
        for address, _ in packets:
            if not address in candidates:
                candidates[address] = self._candidates[address] if address in self._candidates else Candidate(address, address, address)
        self._callback.register(self.on_incoming_packets, ([(candidates[address], packet) for address, packet in packets],), {"timestamp":time()})

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
            message = conversion.decode_message(LocalhostCandidate(self), packet)

        except (DropPacket, DelayPacket), exception:
            if __debug__: dprint("unable to convert a ", len(packet), " byte packet (", exception, ")", exception=True, level="warning")
            return None

        message.packet_id = packet_id
        return message

    def convert_packet_to_message(self, packet, community=None, load=True, auto_load=True):
        """
        Returns the Message representing the packet or None when no conversion is possible.
        """
        if __debug__:
            # pylint: disable-msg=W0404
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
            return conversion.decode_message(LocalhostCandidate(self), packet)

        except (DropPacket, DelayPacket), exception:
            if __debug__: dprint("unable to convert a ", len(packet), " byte packet (", exception, ")", exception=True, level="warning")
            return None

    def convert_packets_to_messages(self, packets, community=None, load=True, auto_load=True):
        """
        Returns a list with messages representing each packet or None when no conversion is
        possible.
        """
        return [self.convert_packet_to_message(packet, community, load, auto_load) for packet in packets]

    def on_incoming_packets(self, packets, cache=True, timestamp=0.0):
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
        meta.batch.max_window and meta.batch.priority.  Finally, the candidate table is updated in
        regards to the incoming source addresses.

        @param packets: The sequence of packets.
        @type packets: [(address, packet)]
        """
        assert isinstance(packets, (tuple, list)), packets
        assert len(packets) > 0, packets
        assert all(isinstance(packet, tuple) for packet in packets), packets
        assert all(len(packet) == 2 for packet in packets), packets
        assert all(isinstance(packet[0], Candidate) for packet in packets), packets
        assert all(isinstance(packet[1], str) for packet in packets), packets
        assert isinstance(cache, bool), cache
        assert isinstance(timestamp, float), timestamp

        self._statistics.increment_total_down(sum(len(packet) for _, packet in packets), len(packets))

        sort_key = lambda tup: (tup[0].batch.priority, tup[0]) # meta, address, packet, conversion
        groupby_key = lambda tup: tup[0] # meta, address, packet, conversion
        for meta, iterator in groupby(sorted(self._convert_packets_into_batch(packets), key=sort_key), key=groupby_key):
            batch = [(candidate, packet, conversion) for _, candidate, packet, conversion in iterator]

            # schedule batch processing (taking into account the message priority)
            if meta.batch.enabled and cache:
                if meta in self._batch_cache:
                    task_identifier, current_timestamp, current_batch = self._batch_cache[meta]
                    current_batch.extend(batch)
                    if __debug__: dprint("adding ", len(batch), " ", meta.name, " messages to existing cache")

                else:
                    current_timestamp = timestamp
                    current_batch = batch
                    task_identifier = self._callback.register(self._on_batch_cache_timeout, (meta, current_timestamp, current_batch), delay=meta.batch.max_window, priority=meta.batch.priority)
                    self._batch_cache[meta] = (task_identifier, current_timestamp, current_batch)
                    if __debug__: dprint("new cache with ", len(batch), " ", meta.name, " messages (batch window: ", meta.batch.max_window, ")")

                while len(current_batch) > meta.batch.max_size:
                    # batch exceeds maximum size, process first max_size immediately
                    batch, current_batch = current_batch[:meta.batch.max_size], current_batch[meta.batch.max_size:]
                    if __debug__: dprint("schedule processing ", len(batch), " ", meta.name, " messages immediately (exceeded batch size)")
                    self._callback.register(self._on_batch_cache_timeout, (meta, current_timestamp, batch), priority=meta.batch.priority)

                    task_identifier = self._callback.replace_register(task_identifier, self._on_batch_cache_timeout, (meta, timestamp, current_batch), delay=meta.batch.max_window, priority=meta.batch.priority)
                    self._batch_cache[meta] = (task_identifier, timestamp, current_batch)

            else:
                # ignore cache, process batch immediately
                if __debug__: dprint("processing ", len(batch), " ", meta.name, " messages immediately")
                self._on_batch_cache(meta, batch)

    def _on_batch_cache_timeout(self, meta, timestamp, batch):
        """
        Start processing a batch of messages once the cache timeout occurs.

        This method is called meta.batch.max_window seconds after the first message in this batch
        arrived.  All messages in this batch have been 'cached' together in self._batch_cache[meta].
        Hopefully the delay caused the batch to collect as many messages as possible.
        """
        assert isinstance(meta, Message)
        assert meta in self._batch_cache
        assert isinstance(timestamp, float)
        assert isinstance(batch, list)
        assert len(batch) > 0
        if __debug__:
            dprint("processing  ", len(batch), "x ", meta.name, " batched messages")

        if id(self._batch_cache[meta][2]) == id(batch):
            self._batch_cache.pop(meta)

        if not self._communities.get(meta.community.cid, None) == meta.community:
            if __debug__: dprint("dropped ", len(batch), "x ", meta.name, " packets (community no longer loaded)", level="warning")
            return 0

        if meta.batch.enabled and timestamp > 0.0 and meta.batch.max_age + timestamp <= time():
            if __debug__: dprint("dropped ", len(batch), "x ", meta.name, " packets (can not process these messages on time)", level="warning")
            return 0

        return self._on_batch_cache(meta, batch)

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
            for candidate, packet, conversion in batch:
                assert isinstance(packet, str)
                if packet in unique:
                    if __debug__: dprint("drop a ", len(packet), " byte packet (duplicate in batch) from ", candidate, level="warning")
                    self._statistics.drop("_convert_packets_into_batch:duplicate in batch", len(packet))
                else:
                    unique.add(packet)
                    yield candidate, packet, conversion

        # remove duplicated
        # todo: make _convert_batch_into_messages accept iterator instead of list to avoid conversion
        batch = list(unique(batch))

        # convert binary packets into Message.Implementation instances
        messages = list(self._convert_batch_into_messages(batch))
        assert all(isinstance(message, Message.Implementation) for message in messages), "_convert_batch_into_messages must return only Message.Implementation instances"
        assert all(message.meta == meta for message in messages), "All Message.Implementation instances must be in the same batch"
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
        assert all(isinstance(message, Message.Implementation) for message in messages)
        assert all(message.community == messages[0].community for message in messages)
        assert all(message.meta == messages[0].meta for message in messages)

        def _filter_fail(message):
            if isinstance(message, DelayMessage):
                self._statistics.delay("on_message_batch:%s" % message, len(message.delayed.packet))
                if __debug__: dprint("delay a ", len(message.delayed.packet), " byte ", message.delayed.name, " (", message, ") from ", message.delayed.candidate)
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
                    self._callback.register(trigger.on_timeout, delay=10.0, priority=TRIGGER_TIMEOUT_PRIORITY)
                    self._send([message.delayed.candidate], [message.request.packet], message.request.name)
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
            debug_begin = time()

        # drop all duplicate or old messages
        assert type(meta.distribution) in self._check_distribution_batch_map
        messages = list(self._check_distribution_batch_map[type(meta.distribution)](messages))
        assert len(messages) > 0 # should return at least one item for each message
        assert all(isinstance(message, (Message.Implementation, DropMessage, DelayMessage)) for message in messages)

        # handle/remove DropMessage and DelayMessage instances
        messages = [message for message in messages if _filter_fail(message)]
        if not messages:
            return 0

        # check all remaining messages on the community side.  may yield Message.Implementation,
        # DropMessage, and DelayMessage instances
        messages = list(meta.check_callback(messages))
        assert len(messages) >= 0 # may return zero messages
        assert all(isinstance(message, (Message.Implementation, DropMessage, DelayMessage)) for message in messages)

        if __debug__:
            if len(messages) == 0:
                dprint(meta.check_callback, " yielded zero messages, drop, or delays.  This is allowed but likely to be an error.", level="warning")

        # handle/remove DropMessage and DelayMessage instances
        messages = [message for message in messages if _filter_fail(message)]
        if not messages:
            return 0

        # store to disk and update locally
        if __debug__: dprint("in... ", len(messages), " ", meta.name, " messages from ", ", ".join(str(candidate) for candidate in set(message.candidate for message in messages)))
        self._statistics.success(meta.name, sum(len(message.packet) for message in messages), len(messages))
        self.store_update_forward(messages, True, True, False)

        # check if there are triggers
        if messages and self._triggers:
            if not self._untriggered_messages:
                self._callback.register(self._check_triggers, priority=TRIGGER_CHECK_PRIORITY)
            self._untriggered_messages.extend(messages)

        # tell what happened
        if __debug__:
            debug_end = time()
            level = "warning" if (debug_end - debug_begin) > 1.0 else "normal"
            dprint("handled ", len(messages), "/", debug_count, " %.2fs" % (debug_end - debug_begin), " ", meta.name, " messages (with ", meta.batch.max_window, "s cache window)", level=level)

        # return the number of messages that were correctly handled (non delay, duplictes, etc)
        return len(messages)

    def _convert_packets_into_batch(self, packets):
        """
        Convert a list with one or more (candidate, data) tuples into a list with zero or more
        (Message, (candidate, packet, conversion)) tuples using a generator.

        # 22/06/11 boudewijn: no longer checks for duplicates.  duplicate checking is pointless
        # because new duplicates may be introduced because of the caching mechanism.
        #
        # Duplicate packets are removed.  This will result in drops when two we receive the exact same
        # binary packet from multiple nodes.  While this is usually not a problem, packets are usually
        # signed and hence unique, in rare cases this may result in invalid drops.

        Packets from invalid sources are removed.  The is_valid_destination_address is used to
        determine if the address that the candidate points to is valid.

        Packets associated with an unknown community are removed.  Packets from a known community
        encoded in an unknown conversion, are also removed.

        The results can be used to easily create a dictionary batch using
         > batch = dict(_convert_packets_into_batch(packets))
        """
        assert isinstance(packets, (tuple, list))
        assert len(packets) > 0
        assert all(isinstance(packet, tuple) for packet in packets)
        assert all(len(packet) == 2 for packet in packets)
        assert all(isinstance(packet[0], Candidate) for packet in packets)
        assert all(isinstance(packet[1], str) for packet in packets)

        for candidate, packet in packets:
            # is it from a remote source
            if not self.is_valid_remote_address(candidate.address):
                if __debug__: dprint("drop a ", len(packet), " byte packet (received from an invalid source) from ", candidate, level="warning")
                self._statistics.drop("_convert_packets_into_batch:invalid source", len(packet))
                continue

            # find associated community
            try:
                community = self.get_community(packet[2:22])
            except KeyError:
                if __debug__: dprint("drop a ", len(packet), " byte packet (received packet for unknown community) from ", candidate, level="warning")
                self._statistics.drop("_convert_packets_into_batch:unknown community", len(packet))
                continue

            # find associated conversion
            try:
                conversion = community.get_conversion(packet[:22])
            except KeyError:
                if __debug__: dprint("drop a ", len(packet), " byte packet (received packet for unknown conversion) from ", candidate, level="warning")
                self._statistics.drop("_convert_packets_into_batch:unknown conversion", len(packet))
                continue

            try:
                # convert binary data into the meta message
                yield conversion.decode_meta_message(packet), candidate, packet, conversion

            except DropPacket, exception:
                if __debug__: dprint("drop a ", len(packet), " byte packet (", exception,") from ", candidate, exception=True, level="warning")
                self._statistics.drop("_convert_packets_into_batch:decode_meta_message:%s" % exception, len(packet))

    def _convert_batch_into_messages(self, batch):
        if __debug__:
            # pylint: disable-msg=W0404
            from conversion import Conversion
        assert isinstance(batch, (list, set))
        assert len(batch) > 0
        assert all(isinstance(x, tuple) for x in batch)
        assert all(len(x) == 3 for x in batch)

        if __debug__:
            debug_begin = time()
            begin_stats = Conversion.debug_stats.copy()

        for candidate, packet, conversion in batch:
            assert isinstance(candidate, Candidate)
            assert isinstance(packet, str)
            assert isinstance(conversion, Conversion)

            try:
                # convert binary data to internal Message
                yield conversion.decode_message(candidate, packet)

            except DropPacket, exception:
                if __debug__: dprint("drop a ", len(packet), " byte packet (", exception, ") from ", candidate, exception=True, level="warning")
                self._statistics.drop("_convert_batch_into_messages:%s" % exception, len(packet))

            except DelayPacket, delay:
                if __debug__: dprint("delay a ", len(packet), " byte packet (", delay, ") from ", candidate)
                self._statistics.delay("_convert_batch_into_messages:%s" % delay, len(packet))
                # try to extend an existing Trigger with the same pattern
                for trigger in self._triggers:
                    if isinstance(trigger, TriggerPacket) and trigger.extend(delay.pattern, [(candidate, packet)]):
                        if __debug__: dprint("extended an existing TriggerPacket")
                        break
                else:
                    # create a new Trigger with this pattern
                    trigger = TriggerPacket(delay.pattern, self.on_incoming_packets, [(candidate, packet)])
                    if __debug__: dprint("created a new TriggerPacket")
                    self._triggers.append(trigger)
                    self._callback.register(trigger.on_timeout, delay=10.0, priority=TRIGGER_TIMEOUT_PRIORITY)
                    self._send([candidate], [delay.request_packet], u"-delay-packet-")

        if __debug__:
            debug_end = time()
            level = "warning" if (debug_end - debug_begin) > 1.0 else "normal"
            for key, value in sorted(Conversion.debug_stats.iteritems()):
                if value - begin_stats[key] > 0.0:
                    dprint("[", value - begin_stats[key], " cnv] ", len(batch), "x ", key, level=level)

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
        assert all(isinstance(message, Message.Implementation) for message in messages)
        assert all(message.community == messages[0].community for message in messages)
        assert all(message.meta == messages[0].meta for message in messages)
        assert all(isinstance(message.distribution, SyncDistribution.Implementation) for message in messages)
        # ensure no duplicate messages are present, this MUST HAVE been checked before calling this
        # method!
        assert len(messages) == len(set((message.authentication.member.database_id, message.distribution.global_time) for message in messages)), messages[0].name

        meta = messages[0].meta
        if __debug__: dprint("attempting to store ", len(messages), " ", meta.name, " messages")
        is_subjective_destination = isinstance(meta.destination, SubjectiveDestination)
        is_multi_member_authentication = isinstance(meta.authentication, MultiMemberAuthentication)

        # update_sync_range = set()
        for message in messages:
            # the signature must be set
            assert isinstance(message.authentication, (MemberAuthentication.Implementation, MultiMemberAuthentication.Implementation)), message.authentication
            assert message.authentication.is_signed
            assert not message.packet[-10:] == "\x00" * 10, message.packet[-10:].encode("HEX")
            # we must have the identity message as well
            assert message.name == u"dispersy-identity" or message.authentication.member.has_identity(message.community), [message, message.community, message.authentication.member.database_id]

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
            # update_sync_range.add(message.distribution.global_time)

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
                    self._database.executemany(u"DELETE FROM reference_member_sync WHERE sync = ?", [(id_,) for id_, _, _ in items])
                    assert len(items) * meta.authentication.count == self._database.changes

                # update_sync_range.update(global_time for _, _, global_time in items)

            # 12/10/11 Boudewijn: verify that we do not have to many packets in the database
            if __debug__:
                if not is_multi_member_authentication:
                    for message in messages:
                        history_size, = self._database.execute(u"SELECT COUNT(1) FROM sync WHERE meta_message = ? AND member = ?", (message.database_id, message.authentication.member.database_id)).next()
                        assert history_size <= message.distribution.history_size, [count, message.distribution.history_size, message.authentication.member.database_id]

        # if update_sync_range:
        #     # notify that global times have changed
        #     meta.community.update_sync_range(meta, update_sync_range)

    def yield_all_candidates(self, community, blacklist=()):
        """
        Yields all candidates that are part of COMMUNITY and not in BLACKLIST.

        BLACKLIST is a list with Candidate instances.
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(blacklist, (tuple, list))
        assert all(isinstance(candidate, Candidate) for candidate in blacklist)
        assert all(isinstance(candidate, Candidate) for candidate in self._candidates.itervalues())
        assert not self._lan_address in [candidate.address for candidate in self._candidates.itervalues()], "our address may not be a candidate"
        assert not self._wan_address in [candidate.address for candidate in self._candidates.itervalues()], "our address may not be a candidate"
        assert not self._lan_address in [candidate.address for candidate in self._bootstrap_candidates.itervalues()], "our address may not be a bootstrap candidate"
        assert not self._wan_address in [candidate.address for candidate in self._bootstrap_candidates.itervalues()], "our address may not be a bootstrap candidate"
        assert all(not candidate in self._bootstrap_candidates for candidate in self._candidates.itervalues()), "non of the candidates may be a bootstrap address"
        assert all(sock_address == candidate.address for sock_address, candidate in self._candidates.iteritems())

        # remove old candidates
        unverified_threshold = time() - 25.0
        verified_threshold = time() - 55.0
        for sock_address in [sock_address for sock_address, candidate in self._candidates.iteritems()
                             if candidate.timestamp_incoming <= (verified_threshold if candidate.is_walk or candidate.is_stumble else unverified_threshold)]:
            if __debug__: dprint("removing old candidate at ", sock_address[0], ":", sock_address[1])
            del self._candidates[sock_address]

        if __debug__:
            for counter, (sock_address, candidate) in enumerate(self._candidates.iteritems()):
                dprint(counter + 1, "/", len(self._candidates), " in_community? ", candidate.in_community(community), " ", candidate)

        # get all viable candidates
        return (candidate
                for candidate
                in self._candidates.itervalues()
                if candidate.in_community(community) and not candidate in blacklist)

    def yield_subjective_candidates(self, community, limit, cluster, blacklist=()):
        """
        Yields LIMIT random candidates that are part of COMMUNITY, not in BLACKLIST, with whom we
        have interacted before, and who have us in their subjective set CLUSTER.
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(blacklist, (tuple, list))
        assert all(isinstance(candidate, Candidate) for candidate in blacklist)

        def in_subjective_set(candidate):
            for member in candidate.members:
                subjective_set = community.get_subjective_set(member, cluster)
                # TODO when we do not have a subjective_set from member, we should request it to
                # ensure that we make a valid decision next time
                if subjective_set and community.my_member.public_key in subjective_set:
                    return True
            return False

        candidates = [candidate
                      for candidate
                      in self.yield_all_candidates(community, blacklist)
                      if (candidate.is_walk or candidate.is_stumble) and in_subjective_set(candidate)]
        shuffle(candidates)
        return islice(candidates, limit)

    def yield_random_candidates(self, community, limit, blacklist=(), connection_type_blacklist=()):
        """
        Yields LIMIT random candidates that are part of COMMUNITY, not in BLACKLIST, and with whom
        we have interacted before.
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(limit, int)
        assert isinstance(blacklist, (tuple, list))
        assert all(isinstance(candidate, Candidate) for candidate in blacklist)
        assert isinstance(connection_type_blacklist, (tuple, list))
        assert isinstance(self._bootstrap_candidates, dict), type(self._bootstrap_candidates)
        assert all(not sock_address in self._candidates for sock_address in self._bootstrap_candidates.iterkeys()), "none of the bootstrap candidates may be in self._candidates"

        candidates = [candidate for candidate in self.yield_all_candidates(community, blacklist)
                      if (candidate.is_walk or candidate.is_stumble) and not candidate.connection_type in connection_type_blacklist]
        walks = set(candidate for candidate in candidates if candidate.is_walk)
        stumbles = set(candidate for candidate in candidates if candidate.is_stumble)

        if walks or stumbles:
            W = list(walks)
            S = list(stumbles.difference(walks))

            for _ in xrange(limit):
                if W and S:
                    yield W.pop(int(random() * len(W))) if random() <= .5 else S.pop(int(random() * len(S)))

                elif W:
                    yield W.pop(int(random() * len(W)))

                elif S:
                    yield S.pop(int(random() * len(S)))

                else:
                    # exhausted candidates
                    break

    def yield_walk_candidates(self, community, blacklist=()):
        """
        Yields a mixture of all candidates that we could get our hands on that are part of COMMUNITY
        and not in BLACKLIST.
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(blacklist, (tuple, list))
        assert all(isinstance(candidate, Candidate) for candidate in blacklist)

        threshold = time() - 30.0

        # SECURE 5 WAY SELECTION POOL
        bootstrap_candidates = [candidate for candidate in self._bootstrap_candidates.itervalues() if candidate.timestamp_last_step_in_community(community) <= threshold and not candidate in blacklist]
        candidates = [candidate for candidate in self.yield_all_candidates(community, blacklist) if candidate.timestamp_last_step_in_community(community) <= threshold]
        walks = set(candidate for candidate in candidates if candidate.is_walk)
        stumbles = set(candidate for candidate in candidates if candidate.is_stumble)
        introduction = set(candidate for candidate in candidates if candidate.is_introduction)
        sort_key = lambda candidate: candidate.timestamp_last_step_in_community(community)

        if walks or stumbles or introduction:
            B = sorted(walks, key=sort_key)
            C = sorted(introduction.difference(walks).difference(stumbles), key=sort_key)
            D = sorted(stumbles.difference(walks).difference(introduction), key=sort_key)
            E = sorted(stumbles.intersection(introduction).difference(walks), key=sort_key)

            if __debug__: dprint(len(candidates), " candidates. B", len(B), " C", len(C), " D", len(D), " E", len(E))
            assert any([walks, stumbles, introduction])
            assert any([B, C, D, E]), "at least one of the categories must have one or more candidates"
            assert all(candidate.is_walk for candidate in B)
            assert all(not candidate.is_walk and not candidate.is_stumble and candidate.is_introduction for candidate in C)
            assert all(not candidate.is_walk and candidate.is_stumble and not candidate.is_introduction for candidate in D)
            assert all(not candidate.is_walk and candidate.is_stumble and candidate.is_introduction for candidate in E)

            while True:
                r = random()

                if r <= .495: # 50%
                    if B:
                        candidate = B.pop(0)
                        yield candidate
                        B.append(candidate)

                elif r <= .99: # 50%

                    if C or D or E:
                        while True:
                            r = random()

                            if r <= .3333:
                                if C:
                                    candidate = C.pop(0)
                                    yield candidate
                                    C.append(candidate)
                                    break

                            elif r <= .6666:
                                if D:
                                    candidate = D.pop(0)
                                    yield candidate
                                    D.append(candidate)
                                    break

                            elif r <= .9999:
                                if E:
                                    candidate = E.pop(0)
                                    yield candidate
                                    E.append(candidate)
                                    break

                elif bootstrap_candidates: # ~1%
                    candidate = choice(bootstrap_candidates)
                    yield candidate

        elif bootstrap_candidates:
            if __debug__: dprint("no candidates available.  yielding bootstrap candidate")
            while True:
                candidate = choice(bootstrap_candidates)
                yield candidate

        else:
            if __debug__: dprint("no candidates or bootstrap candidates available")

    def take_step(self, community):
        if community.cid in self._communities:
            try:
                candidate = self.yield_walk_candidates(community).next()

            except StopIteration:
                if __debug__: dprint(community.cid.encode("HEX"), " ", community.get_classification(), " no candidate to take step")
                return False

            else:
                assert community.my_member.private_key
                if __debug__: dprint(community.cid.encode("HEX"), " ", community.get_classification(), " taking step towards ", candidate)
                candidate.out_introduction_request(community)
                self.create_introduction_request(community, candidate)
                return True

    def create_introduction_request(self, community, destination):
        assert isinstance(destination, Candidate), [type(destination), destination]

        # claim unique walk identifier
        while True:
            identifier = int(random() * 2**16)
            if not identifier in self._walk_identifiers:
                self._walk_identifiers[identifier] = None
                break

        # decide if the requested node should introduce us to someone else
        # advice = random() < 0.5 or len(self._candidates) <= 5
        advice = True

        # obtain sync range
        if destination.address in self._bootstrap_candidates:
            # do not request a sync when we connecting to a bootstrap candidate
            sync = None
        else:
            sync = community.dispersy_claim_sync_bloom_filter(identifier)
            if __debug__:
                assert isinstance(sync, tuple), sync
                assert len(sync) == 5, sync
                time_low, time_high, modulo, offset, bloom_filter = sync
                assert isinstance(time_low, (int, long))
                assert isinstance(time_high, (int, long))
                assert isinstance(modulo, int)
                assert isinstance(offset, int)
                assert isinstance(bloom_filter, BloomFilter)

                # verify that the bloom filter is correct
                binary = bloom_filter.bytes
                bloom_filter.clear()
                counter = 0
                for packet, in self._database.execute(u"SELECT sync.packet FROM sync JOIN meta_message ON meta_message.id = sync.meta_message WHERE sync.community = ? AND meta_message.priority > 32 AND sync.undone == 0 AND global_time BETWEEN ? AND ?",
                                                      (community.database_id, time_low, community.global_time if time_high == 0 else time_high)):
                    bloom_filter.add(str(packet))
                    counter += 1
                assert binary == bloom_filter.bytes, "The returned bloom filter does not match the given range [%d:%d] packets:%d" % (time_low, time_high, counter)

        meta_request = community.get_meta_message(u"dispersy-introduction-request")
        request = meta_request.impl(authentication=(community.my_member,),
                                    distribution=(community.global_time,),
                                    destination=(destination,),
                                    payload=(destination.address, self._lan_address, self._wan_address, advice, self._connection_type, sync, identifier))

        # wait for introduction-response
        meta_response = community.get_meta_message(u"dispersy-introduction-response")
        footprint = meta_response.generate_footprint(payload=(identifier,))
        # we walk every 5.0 seconds, ensure that this candidate is dropped (if unresponsive) before the next walk
        timeout = 4.5
        assert meta_request.batch.max_window + meta_response.batch.max_window < timeout
        self.await_message(footprint, self.introduction_response_or_timeout, response_args=(community, destination,), timeout=timeout)

        # release walk identifier some seconds after timeout expires
        self._callback.register(self._walk_identifiers.pop, (identifier,), delay=timeout+10.0)

        if __debug__:
            if sync:
                dprint(community.cid.encode("HEX"), " sending introduction request to ", destination, " [", sync[0], ":", sync[1], "] %", sync[2], "+", sync[3])
            else:
                dprint(community.cid.encode("HEX"), " sending introduction request to ", destination)
        self.store_update_forward([request], False, False, True)
        return request

    def _estimate_lan_and_wan_addresses(self, sock_addr, lan_address, wan_address):
        """
        We received a message from SOCK_ADDR claiming to have LAN_ADDRESS and WAN_ADDRESS, returns
        the estimated LAN and WAN address for this node.

        The returned LAN and WAN addresses have passed the _is_valid_lan_address and
        _is_valid_wan_address, respectively.
        """
        if not self._is_valid_lan_address(lan_address):
            if __debug__:
                if lan_address != sock_addr:
                    dprint("estimate a different LAN address ", lan_address[0], ":", lan_address[1], " -> ", sock_addr[0], ":", sock_addr[1])
            lan_address = sock_addr
        if not self._is_valid_wan_address(wan_address):
            if __debug__:
                if wan_address != sock_addr:
                    dprint("estimate a different WAN address ", wan_address[0], ":", wan_address[1], " -> ", sock_addr[0], ":", sock_addr[1])
            wan_address = sock_addr

        if sock_addr[0] == self._wan_address[0]:
            # we have the same WAN address, we are probably behind the same NAT
            if __debug__:
                if lan_address != sock_addr:
                    dprint("estimate a different LAN address ", lan_address[0], ":", lan_address[1], " -> ", sock_addr[0], ":", sock_addr[1])
            return sock_addr, wan_address

        elif self._is_valid_wan_address(sock_addr):
            # we have a different WAN address and the sock address is WAN, we are probably behind a different NAT
            if __debug__:
                if wan_address != sock_addr:
                    dprint("estimate a different WAN address ", wan_address[0], ":", wan_address[1], " -> ", sock_addr[0], ":", sock_addr[1])
            return lan_address, sock_addr

        else:
            # we have a different WAN address and the sock address is not WAN, we are probably on the same computer
            return lan_address, wan_address

    def on_introduction_request(self, messages):
        community = messages[0].community
        meta_introduction_response = community.get_meta_message(u"dispersy-introduction-response")
        meta_puncture_request = community.get_meta_message(u"dispersy-puncture-request")
        responses = []
        requests = []

        # modify either the senders LAN or WAN address based on how we perceive that node
        estimates = [self._estimate_lan_and_wan_addresses(message.candidate.address, message.payload.source_lan_address, message.payload.source_wan_address) + (message,)
                     for message
                     in messages]

        for source_lan_address, source_wan_address, message in estimates:
            # apply vote to determine our WAN address
            self.wan_address_vote(message.payload.destination_address, message.candidate.address)

            # add source to candidate pool and mark as a node that stumbled upon us
            if not (message.candidate.address in self._candidates or message.candidate.address in self._bootstrap_candidates or message.candidate.address == self._lan_address or message.candidate.address == self._wan_address):
                self._candidates[message.candidate.address] = message.candidate
            else:
                if __debug__: dprint("unable to add stumble node ", message.candidate)
            message.candidate.inc_introduction_requests(message.authentication.member, community, source_lan_address, source_wan_address, message.payload.connection_type)

        for source_lan_address, source_wan_address, message in estimates:
            if message.payload.advice:
                try:
                    candidate = self.yield_random_candidates(community, 1, (message.candidate,), (u"symmetric-NAT" if message.payload.connection_type == u"symmetric-NAT" else u"",)).next()
                except StopIteration:
                    candidate = None
            else:
                if __debug__: dprint("no candidates available to introduce")
                candidate = None

            if candidate:
                if __debug__: dprint("telling ", message.candidate, " that ", candidate, " exists")

                # create introduction response
                responses.append(meta_introduction_response.impl(authentication=(community.my_member,), distribution=(community.global_time,), destination=(message.candidate,), payload=(message.candidate.address, self._lan_address, self._wan_address, candidate.lan_address, candidate.wan_address, self._connection_type, message.payload.identifier)))

                # create puncture request
                requests.append(meta_puncture_request.impl(distribution=(community.global_time,), destination=(candidate,), payload=(source_lan_address, source_wan_address, message.payload.identifier)))

            else:
                if __debug__: dprint("responding to ", message.candidate, " without an introduction")

                none = ("0.0.0.0", 0)
                responses.append(meta_introduction_response.impl(authentication=(community.my_member,), distribution=(community.global_time,), destination=(message.candidate,), payload=(message.candidate.address, self._lan_address, self._wan_address, none, none, self._connection_type, message.payload.identifier)))

        if responses:
            self._forward(responses)
        if requests:
            self._forward(requests)

    def check_introduction_response(self, messages):
        for message in messages:
            if not message.payload.identifier in self._walk_identifiers:
                yield DropMessage(message, "invalid response identifier")

            elif message.payload.wan_introduction_address == ("0.0.0.0", 0) or message.payload.lan_introduction_address == ("0.0.0.0", 0):
                # sender has no clue what her own address is, allow the message.  no introduction
                # will be given but a response will be sent to allow the sender to figure out her
                # addresses
                yield message

            elif message.payload.wan_introduction_address == message.candidate.address:
                yield DropMessage(message, "invalid WAN introduction address [introducing herself]")

            elif message.payload.lan_introduction_address == message.candidate.address:
                yield DropMessage(message, "invalid LAN introduction address [introducing herself]")

            elif message.payload.wan_introduction_address == self._wan_address:
                yield DropMessage(message, "invalid WAN introduction address [introducing myself]")

            elif message.payload.lan_introduction_address == self._lan_address and message.payload.wan_introduction_address[0] == self._wan_address[0]:
                yield DropMessage(message, "invalid LAN introduction address [introducing myself]")

            else:
                yield message

    def on_introduction_response(self, messages):
        community = messages[0].community

        for message in messages:
            # apply vote to determine our WAN address
            self.wan_address_vote(message.payload.destination_address, message.candidate.address)

            # modify either the senders LAN or WAN address based on how we perceive that node
            source_lan_address, source_wan_address = self._estimate_lan_and_wan_addresses(message.candidate.address, message.payload.source_lan_address, message.payload.source_wan_address)
            if __debug__: dprint("received introduction response from ", message.candidate)

            # add source to the candidate pool and mark as a node that is part of our walk
            message.candidate.inc_introduction_response(source_lan_address, source_wan_address, message.payload.connection_type)
            if not (message.candidate.address in self._candidates or message.candidate.address in self._bootstrap_candidates or message.candidate.address == self._lan_address or message.candidate.address == self._wan_address):
                self._candidates[message.candidate.address] = message.candidate
            else:
                if __debug__: dprint("unable to add walker node ", message.candidate)

            lan_introduction_address = message.payload.lan_introduction_address
            wan_introduction_address = message.payload.wan_introduction_address
            if __debug__: dprint("received introduction to ", "LAN: ", lan_introduction_address[0], ":", lan_introduction_address[1], " WAN: ", wan_introduction_address[0], ":", wan_introduction_address[1])

            # add introduced node to the candidate pool and mark as an introduced node
            if self._is_valid_lan_address(lan_introduction_address) and self._is_valid_wan_address(wan_introduction_address):
                sock_address = lan_introduction_address if wan_introduction_address[0] == self._wan_address[0] else wan_introduction_address

                candidate = self._candidates.get(sock_address)
                if candidate:
                    self._walk_identifiers[message.payload.identifier] = candidate
                    candidate.inc_introduced(message.authentication.member, community)

                else:
                    candidate = self._walk_identifiers.get(message.payload.identifier)
                    if candidate and candidate.address == sock_address:
                        if not (sock_address in self._candidates or sock_address in self._bootstrap_candidates or sock_address == self._lan_address or sock_address == self._wan_address):
                            self._candidates[sock_address] = candidate
                        else:
                            if __debug__: dprint("unable to add walker node ", message.candidate)
                        candidate.inc_introduced(message.authentication.member, community)

                    elif not (sock_address in self._bootstrap_candidates or sock_address == self._lan_address or sock_address == self._wan_address):
                        candidate = Candidate(sock_address, lan_introduction_address, wan_introduction_address, community=community, is_introduction=True)
                        self._walk_identifiers[message.payload.identifier] = candidate
                        if not (sock_address in self._candidates or sock_address in self._bootstrap_candidates or sock_address == self._lan_address or sock_address == self._wan_address):
                            self._candidates[sock_address] = candidate
                        else:
                            if __debug__: dprint("unable to add walker node ", message.candidate)

                # 13/10/11 Boudewijn: when we had no candidates and we received this response
                # from a bootstrap node, we will immediately take an additional step towards the
                # introduced node
                #
                # small note:  we check if self._candidates contains only one node, this is the
                # node that was just introduced and added to self._candidates a few lines up
                if len(self._candidates) == 1 and message.candidate.address in self._bootstrap_candidates and candidate:
                    if __debug__: dprint("we have no candidates, immediately contact the introduced node")
                    self.create_introduction_request(community, candidate)

            else:
                if __debug__:
                    level = "normal" if lan_introduction_address == ("0.0.0.0", 0) and wan_introduction_address == ("0.0.0.0", 0) else "warning"
                    dprint("unable to add introduced node. LAN: ", lan_introduction_address[0], ":", lan_introduction_address[1], " (", ("valid" if self._is_valid_lan_address(lan_introduction_address) else "invalid"), ")  WAN: ", wan_introduction_address[0], ":", wan_introduction_address[1], " (", ("valid" if self._is_valid_wan_address(wan_introduction_address) else "invalid"), ")", level=level)

    def introduction_response_or_timeout(self, message, community, intermediary_candidate):
        if message is None:
            # intermediary_candidate is no longer online
            if intermediary_candidate.address in self._candidates:
                if __debug__: dprint("removing candidate ", intermediary_candidate, " (timeout)")
                if not self._candidates[intermediary_candidate.address].timeout(community):
                    del self._candidates[intermediary_candidate.address]

    def on_puncture_request(self, messages):
        community = messages[0].community
        meta_puncture = community.get_meta_message(u"dispersy-puncture")
        punctures = []
        for message in messages:
            message.candidate.inc_puncture_request()

            # determine if we are in the same LAN as the walker node
            destination = self.get_candidate(message.payload.lan_walker_address if message.payload.wan_walker_address[0] == self._wan_address[0] else message.payload.wan_walker_address)
            punctures.append(meta_puncture.impl(authentication=(community.my_member,), distribution=(community.global_time,), destination=(destination,), payload=(self._lan_address, self._wan_address, message.payload.identifier)))
            if __debug__: dprint(message.candidate, " asked us to send a puncture to ", destination)

        self.store_update_forward(punctures, False, False, True)

    def check_puncture(self, messages):
        for message in messages:
            if not message.payload.identifier in self._walk_identifiers:
                yield DropMessage(message, "invalid response identifier")

            else:
                yield message

    def on_puncture(self, messages):
        for message in messages:
            # when the sender is behind a symmetric NAT and we are not, we will not be able to get
            # through using the port that the intermediary node gave us (symmetric NAT will give a
            # different port for each destination address).

            # we can match this source address (message.candidate.address) to the candidate and
            # modify the LAN or WAN address that has been proposed.
            assert message.payload.identifier in self._walk_identifiers, "must be checked in check_puncture"

            candidate = self._walk_identifiers.get(message.payload.identifier)
            if candidate:
                if not candidate.address == message.candidate.address:
                    self._candidates.pop(candidate.address, None)
                lan_address, wan_address = self._estimate_lan_and_wan_addresses(message.candidate.address, candidate.lan_address, candidate.wan_address)
                candidate.inc_puncture(message.authentication.member, message.community, message.candidate.address, lan_address, wan_address)
                if not (candidate.address in self._bootstrap_candidates or candidate.address == self._lan_address or candidate.address == self._wan_address):
                    self._candidates[candidate.address] = candidate

            else:
                lan_address, wan_address = self._estimate_lan_and_wan_addresses(message.candidate.address, message.payload.source_lan_address, message.payload.source_wan_address)
                message.candidate.inc_puncture(message.authentication.member, message.community, message.candidate.address, lan_address, wan_address)
                self._walk_identifiers[message.payload.identifier] = message.candidate

                if not (message.candidate.address in self._bootstrap_candidates or message.candidate.address == self._lan_address or message.candidate.address == self._wan_address):
                    self._candidates[message.candidate.address] = message.candidate

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
        that no remote nodes will obtain data that we have not safely synced ourselves.

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
        assert all(isinstance(message, Message.Implementation) for message in messages)
        assert all(message.community == messages[0].community for message in messages)
        assert all(message.meta == messages[0].meta for message in messages)
        assert isinstance(store, bool)
        assert isinstance(update, bool)
        assert isinstance(forward, bool)

        if __debug__: dprint(len(messages), " ", messages[0].name, " messages (", store, " ", update, " ", forward, ")")

        store = store and isinstance(messages[0].meta.distribution, SyncDistribution)
        if store:
            self._store(messages)

        if update:
            # TODO in theory we do not need to update_global_time when we store...
            messages[0].community.update_global_time(max(message.distribution.global_time for message in messages))
            if __debug__:
                begin = time()
            messages[0].handle_callback(messages)
            if __debug__:
                end = time()
                level = "warning" if (end - begin) > 1.0 else "normal"
                dprint("handler for ", messages[0].name, " took ", end - begin, " seconds", level=level)

        # 07/10/11 Boudewijn: we will only commit if it the message was create by our self.
        # Otherwise we can safely skip the commit overhead, since, if a crash occurs, we will be
        # able to regain the data eventually
        if store and any(message.authentication.member == message.community.my_member for message in messages):
            if __debug__: dprint("commit user generated message")
            self._database.commit()

        if forward:
            self._forward(messages)

    def _forward(self, messages):
        """
        Queue a sequence of messages to be sent to other members.

        First all messages that use the SyncDistribution policy are stored to the database to allow
        them to propagate when a dispersy-sync message is received.

        Second all messages are sent depending on their destination policy:

         - CandidateDestination causes a message to be sent to the addresses in
           message.destination.candidates.

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
        assert all(isinstance(message, Message.Implementation) for message in messages)
        assert all(message.community == messages[0].community for message in messages)
        assert all(message.meta == messages[0].meta for message in messages)

        meta = messages[0].meta
        if isinstance(meta.destination, CommunityDestination):
            # CommunityDestination.node_count is allowed to be zero
            if meta.destination.node_count > 0:
                for message in messages:
                    self._send(list(self.yield_random_candidates(meta.community, meta.destination.node_count)), [message.packet], meta.name)

        elif isinstance(meta.destination, SubjectiveDestination):
            # SubjectiveDestination.node_count is allowed to be zero
            if meta.destination.node_count > 0:
                for message in messages:
                    self._send(list(self.yield_subjective_candidates(meta.community, meta.destination.node_count, meta.destination.cluster)), [message.packet], meta.name)

        elif isinstance(meta.destination, CandidateDestination):
            for message in messages:
                self._send(message.destination.candidates, [message.packet], meta.name)

        elif isinstance(meta.destination, MemberDestination):
            for message in messages:
                self._send([candidate
                            for candidate
                            in self.yield_all_candidates(meta.community)
                            if any(member in message.destination.members for member in candidate.members_in_community(meta.community))],
                           [message.packet],
                           meta.name)

        else:
            raise NotImplementedError(meta.destination)

    def _send(self, candidates, packets, key=u"unspecified"):
        """
        Send one or more packets to one or more addresses.

        To clarify: every packet is sent to every address.

        @param candidates: A sequence with zero or more candidates.
        @type candidates: [Candidate]

        @param packets: A sequence with one or more packets.
        @type packets: string

        @param key: A unicode string purely used for statistics.  Indicating the type of data send.
        @type key: unicode
        """
        assert isinstance(candidates, (tuple, list, set)), type(candidates)
        assert all(isinstance(candidate, Candidate) for candidate in candidates)
        assert isinstance(packets, (tuple, list, set)), type(packets)
        assert all(isinstance(packet, str) for packet in packets)
        assert all(len(packet) > 0 for packet in packets)
        assert isinstance(key, unicode), type(key)

        self._statistics.increment_total_up(sum(len(packet) for packet in packets) * len(candidates), len(packets) * len(candidates))

        if __debug__:
            if not packets:
                # this is a programming bug.
                dprint("no packets given (wanted to send to ", len(candidates), " addresses)", level="error", stack=True)

        # send packets
        for candidate in candidates:
            if not self.is_valid_remote_address(candidate.address):
                # this is a programming bug.  apparently an invalid address is being used
                if __debug__: dprint("aborted sending ", len(packets), "x ", key, " (", sum(len(packet) for packet in packets), " bytes) to ", candidate, " (invalid remote address)", level="error")
                continue

            for packet in packets:
                self._socket.send(candidate.address, packet)
            self._statistics.outgoing(candidate.address, key, sum(len(packet) for packet in packets), len(packets))
            if __debug__: dprint("out... ", len(packets), " ", key, " (", sum(len(packet) for packet in packets), " bytes) to ", candidate)

    def _check_triggers(self):
        assert self._untriggered_messages, "should not check if there are no messages"
        untriggered_messages = self._untriggered_messages
        self._untriggered_messages = []

        for trigger in self._triggers[:]:
            if not trigger.on_messages(untriggered_messages):
                try:
                    self._triggers.remove(trigger)
                except ValueError:
                    # apparently this trigger was already removed
                    pass

    def await_message(self, footprint, response_func, response_args=(), timeout=10.0, max_responses=1):
        """
        Register a callback to occur when a message with a specific FOOTPRINT is received, or after
        a certain timeout occurs.

        When the FOOTPRINT of an incoming message matches the regular expression FOOTPRINT it is
        passed to both the RESPONSE_FUNC (or several if the message matches multiple footprints) and
        its regular message handler.  First the regular message handler is called, followed by
        RESPONSE_FUNC.

        The RESPONSE_FUNC is called each time when a message is received that matches the expression
        FOOTPRINT or after TIMEOUT seconds when fewer than MAX_RESPONSES incoming messages have
        matched FOOTPRINT.  The first argument is the incoming message, following this are any
        optional arguments in RESPONSE_ARGS.

        When the TIMEOUT expires and less than MAX_RESPONSES messages have matched the expression
        FOOTPRINT, the RESPONSE_FUNC is called one last time.  The first parameter will be sent to
        None and RESPONSE_ARGS will be appended as normal.  Once a callback has timed out it will
        give no further callbacks.

        The Trigger that is created will be removed either on TIMEOUT or when MAX_RESPONSES messages
        have matched the expression FOOTPRINT.

        The footprint matching is done as follows: for each incoming message a message footprint is
        made.  This footprint is a string that contains a summary of all the message properties.
        Such as 'MemberAuthentication:ABCDE' and 'FullSyncDistribution:102'.
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
        self._callback.register(trigger.on_timeout, delay=timeout, priority=TRIGGER_TIMEOUT_PRIORITY)

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
            assert isinstance(member, Member)
            assert not member.must_blacklist, "must not already be blacklisted"
            assert isinstance(packets, list)
            assert len(packets) > 0
            assert all(isinstance(packet, Packet) for packet in packets)
            assert all(packet.meta == packets[0].meta for packet in packets)

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

    def send_malicious_proof(self, community, member, candidate):
        """
        If we have proof that MEMBER is malicious in COMMUNITY, usually in the form of one or more
        signed messages, then send this proof to CANDIDATE.

        @param community: The community where member was malicious.
        @type community: Community

        @param member: The malicious member.
        @type member: Member

        @param candidate: The address where we want the proof to be send.
        @type candidate: Candidate
        """
        if __debug__:
            # pylint: disable-msg=W0404
            from community import Community
            assert isinstance(community, Community)
            assert isinstance(member, Member)
            assert member.must_blacklist, "must be blacklisted"
            assert isinstance(candidate, Candidate)

        packets = [str(packet) for packet, in self._database.execute(u"SELECT packet FROM malicious_proof WHERE community = ? AND member = ?",
                                                                     (community.database_id, member.database_id))]
        if packets:
            self._send([candidate], packets, u"-malicious-proof-")

    def create_missing_message(self, community, candidate, member, global_time, response_func=None, response_args=(), timeout=10.0, forward=True):
        """
        Create a dispersy-missing-message message.

        Each sync message in dispersy can be uniquely identified using the community identifier,
        member identifier, and global time.  This message requests a unique dispersy message from
        another peer.

        If the peer at CANDIDATE.address (1) receives the request, (2) has the requested message,
        and (3) is willing to upload, the optional RESPONSE_FUNC will be called.  Note that if there
        is a callback for the requested message, that will always be called regardless of
        RESPONSE_FUNC.

        If RESPONSE_FUNC is given and there is no response withing TIMEOUT seconds, the
        RESPONSE_FUNC will be called but the message parameter will be None.
        """
        if __debug__:
            # pylint: disable-msg=W0404
            from community import Community
            assert isinstance(community, Community)
            assert isinstance(candidate, Candidate)
            assert isinstance(member, Member)
            assert isinstance(global_time, (int, long))
            assert callable(response_func)
            assert isinstance(response_args, tuple)
            assert isinstance(timeout, float)
            assert timeout > 0.0
            assert isinstance(forward, bool)

        meta = community.get_meta_message(u"dispersy-missing-message")
        request = meta.impl(distribution=(meta.community.global_time,), destination=(candidate,), payload=(member, global_time))

        if response_func:
            # generate footprint
            footprint = "".join(("Community:", community.cid.encode("HEX"),
                                 "\s", "(MemberAuthentication:", member.mid.encode("HEX"), "|MultiMemberAuthentication:[^\s]*", member.mid.encode("HEX"), "[^\s]*)",
                                 "\s", "((Relay|Direct|)Distribution:", str(global_time), "|FullSyncDistribution:", str(global_time), ",[0-9]+)"))
            self.await_message(footprint, response_func, response_args, timeout, 1)

        self.store_update_forward([request], False, False, forward)
        return request

    def on_missing_message(self, messages):
        responses = [] # (candidate, packet) tuples
        for message in messages:
            candidate = message.candidate
            community_database_id = message.community.database_id
            member_database_id = message.payload.member.database_id
            for global_time in message.payload.global_times:
                try:
                    packet, = self._database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                     (community_database_id, member_database_id, global_time)).next()
                except StopIteration:
                    pass
                else:
                    responses.append((candidate, packet))

        for candidate, responses in groupby(responses, key=lambda tup: tup[0]):
            self._send([candidate], [str(packet) for _, packet in responses], u"-missing-message-")

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

    def _is_valid_lan_address(self, address, check_my_lan_address=True):
        """
        TODO we should rename _is_valid_lan_address to _is_valid_address as the way it is used now
        things will fail if it only accepted LAN domain addresses (10.xxx.yyy.zzz, etc.)
        """
        if address[0] == "":
            return False

        if address[1] <= 0:
            return False

        try:
            binary = inet_aton(address[0])
        except socket_error:
            return False

        # ending with .0
        if binary[3] == "\x00":
            return False

        # ending with .255
        if binary[3] == "\xff":
            return False

        # a LAN address may also be a WAN address as some nodes will be connected to the Internet
        # directly
        # # range 10.0.0.0 - 10.255.255.255
        # if binary[0] == "\x0a":
        #     pass
        # # range 172.16.0.0 - 172.31.255.255
        # # TODO fill in range
        # elif binary[0] == "\x7f":
        #     pass
        # # range 192.168.0.0 - 192.168.255.255
        # elif binary[0] == "\xc0" and binary[1] == "\xa8":
        #     pass
        # else:
        #     # not in a valid LAN range
        #     return False

        if check_my_lan_address and address == self._lan_address:
            return False

        if address == ("127.0.0.1", self._lan_address[1]):
            return False

        return True

    def _is_valid_wan_address(self, address, check_my_wan_address=True):
        if address[0] == "":
            return False

        if address[1] <= 0:
            return False

        try:
            binary = inet_aton(address[0])
        except socket_error:
            return False

        # ending with .0
        if binary[3] == "\x00":
            return False

        # ending with .255
        if binary[3] == "\xff":
            return False

        # range 10.0.0.0 - 10.255.255.255
        if binary[0] == "\x0a":
            return False

        # range 172.16.0.0 - 172.31.255.255
        # TODO fill in range
        if binary[0] == "\x7f":
            return False

        # range 192.168.0.0 - 192.168.255.255
        if binary[0] == "\xc0" and binary[1] == "\xa8":
            return False

        if check_my_wan_address and address == self._wan_address:
            return False

        if address == ("127.0.0.1", self._wan_address[1]):
            return False

        return True

    def is_valid_remote_address(self, address):
        return self._is_valid_lan_address(address) or self._is_valid_wan_address(address)

    def create_identity(self, community, store=True, update=True):
        """
        Create a dispersy-identity message for self.my_member.

        The dispersy-identity message contains the public key of a community member.  In the future
        other data can be included in this message, however, it must consist of data that does not
        change over time as this message is only transferred on demand, and not during the sync
        phase.

        @param community: The community for wich the dispersy-identity message will be created.
        @type community: Community

        @param store: When True the messages are stored (as defined by their message distribution
         policy) in the local dispersy database.  This parameter should (almost always) be True, its
         inclusion is mostly to allow certain debugging scenarios.
        @type store: bool
        """
        if __debug__:
            # pylint: disable-msg=W0404
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(store, bool)
        meta = community.get_meta_message(u"dispersy-identity")
        message = meta.impl(authentication=(community.my_member,), distribution=(community.claim_global_time(),))
        self.store_update_forward([message], store, update, False)
        return message

    def on_identity(self, messages):
        """
        We received a dispersy-identity message.
        """
        for message in messages:
            assert message.name == u"dispersy-identity"
            if __debug__: dprint(message)
            # update the in-memory member instance
            message.authentication.member.update()
            assert self._database.execute(u"SELECT COUNT(1) FROM sync WHERE packet = ?", (buffer(message.packet),)).next()[0] == 1
            assert message.authentication.member.has_identity(message.community)

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
                self._send([message.candidate], packets, u"dispersy-identity")
            else:
                assert not message.payload.mid == message.community.my_member.mid, "we should always have our own dispersy-identity"
                if __debug__: dprint("could not find any missing members.  no response is sent", level="warning")

    def create_subjective_set(self, community, cluster, members, reset=True, store=True, update=True, forward=True):
        if __debug__:
            # pylint: disable-msg=W0404
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(cluster, int)
        assert isinstance(members, (tuple, list))
        assert all(isinstance(member, Member) for member in members)
        assert isinstance(reset, bool)
        assert isinstance(store, bool)
        assert isinstance(update, bool)
        assert isinstance(forward, bool)

        # modify the subjective set (bloom filter)
        # 12/10/11 Boudewijn: create_my_subjective_set_on_demand must be False to prevent infinite recursion
        subjective_set = community.get_subjective_set(community.my_member, cluster, create_my_subjective_set_on_demand=False)
        if not subjective_set:
            subjective_set = BloomFilter(community.dispersy_subjective_set_bits, community.dispersy_subjective_set_error_rate)
        if reset:
            subjective_set.clear()
        for member in members:
            subjective_set.add(member.public_key)

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

        for message in messages:
            packets = []
            for member in message.payload.members:
                cache = community.get_subjective_set_cache(member, message.payload.cluster)
                if cache:
                    packets.append(cache.packet)

            if packets:
                self._send([message.candidate], packets, u"dispersy-subjective-set")

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

        Each dispersy-signed-response message will result in one call to response_func.  The first
        parameter for this call is the sub-message.  When all signatures are available the property
        sub-message.authentication.is_signed will be True.

        If not all members sent a reply withing timeout seconds, one final call to response_func is
        made with the first parameter set to None.

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
            # pylint: disable-msg=W0404
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

        @param messages: The dispersy-signature-request messages.
        @type messages: [Message.Implementation]
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
                                               destination=(message.candidate,),
                                               payload=(identifier, signature)))

        self.store_update_forward(responses, False, False, True)

    def on_signature_response(self, messages):
        pass

    def _on_signature_response(self, response, request, response_func, response_args):
        """
        A Trigger matched a received dispersy-signature-response message.

        We sent out a dispersy-signature-request, though the create_signature_request method, and
        have now received a dispersy-signature-response in reply.  If the signature is valid, we
        will call response_func with sub-message, where sub-message is the message parameter given
        to the create_signature_request method.

        When a timeout occurs the response_func will also be called, although now the address and
        sub-message parameters will be set None.

        Note that response_func is also called when the sub-message does not yet contain all the
        signatures.  This can be checked using sub-message.authentication.is_signed.

        @see: create_signature_request

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

                if __debug__: dprint("Syncing ", len(packet), " bytes from sync_full to " , message.candidate)
                packets.append(packet)

                byte_limit -= len(packet)
                if byte_limit > 0:
                    if __debug__: dprint("Bandwidth throttle")
                    break

            if packets:
                self._send([message.candidate], packets, u"-sequence-")

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
                msg = community.get_conversion(packet[:22]).decode_message(LocalhostCandidate(self), packet)
                allowed, proofs = community._timeline.check(msg)
                if allowed and proofs:
                    if __debug__: dprint("found the proof someone was missing (", len(proofs), " packets)")
                    self._send([message.candidate], [proof.packet for proof in proofs], u"-proof-")

                else:
                    if __debug__: dprint("unable to give missing proof.  allowed:", allowed, ".  proofs:", len(proofs), " packets")

    @runtime_duration_warning(0.1)
    def check_sync(self, messages):
        """
        We received a dispersy-sync message.

        The message contains a bloom-filter that needs to be checked.  If we find any messages that
        are not in the bloom-filter, we will sent those to the sender.

        To limit the amount of bandwidth used we will not sent back more data after a certain amount
        has been sent.  This magic number is subject to change.

        @param messages: The dispersy-sync messages.
        @type messages: [Message.Implementation]

        @todo: we should look into optimizing this method, currently it just sends back data.
         Therefore, if multiple nodes receive this dispersy-sync message they will probably all send
         the same messages back.  So we need to make things smarter!

        @todo: we need to optimise this to include a bandwidth throttle.  Otherwise a node can
         easilly force us to send arbitrary large amounts of data.
        """
        sql = u"""SELECT sync.packet, sync.meta_message, member.public_key
                  FROM sync
                  JOIN member ON member.id = sync.member
                  JOIN meta_message ON meta_message.id = sync.meta_message
                  WHERE sync.community = ? AND meta_message.priority > 32 AND sync.undone = 0 AND sync.global_time BETWEEN ? AND ? AND (sync.global_time + ?) % ? = 0
                  ORDER BY meta_message.priority DESC, sync.global_time * meta_message.direction"""

        community = messages[0].community

        # obtain all available messages for this community
        meta_messages = dict((meta_message.database_id, meta_message) for meta_message in community.get_meta_messages())

        for message in messages:
            assert message.name == u"dispersy-introduction-request", "this method is called in batches, i.e. community and meta message grouped together"
            assert message.community == community, "this method is called in batches, i.e. community and meta message grouped together"

            if message.payload.sync:
                # obtain all subjective sets for the sender of the dispersy-sync message
                assert isinstance(message.authentication, MemberAuthentication.Implementation)
                subjective_sets = community.get_subjective_sets(message.authentication.member)

                # we limit the response by byte_limit bytes
                byte_limit = community.dispersy_sync_response_limit

                bloom_filter = message.payload.bloom_filter
                time_low = message.payload.time_low
                time_high = message.payload.time_high if message.payload.has_time_high else community.global_time
                modulo = message.payload.modulo
                offset = message.payload.offset
                packets = []

                if __debug__:
                    begin = time()
                    for _ in self._database.execute(sql, (community.database_id, time_low, time_high, offset, modulo)):
                        pass
                    end = time()
                    select = end - begin
                    dprint("select: %.3f" % select, " [", time_low, ":", time_high, "] %", modulo, "+", offset)

                for packet, meta_message_id, packet_public_key in self._database.execute(sql, (community.database_id, time_low, time_high, offset, modulo)):
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

                        if __debug__:dprint("found missing ", packet_meta.name, " (", len(packet), " bytes) ", sha1(packet).digest().encode("HEX"))

                        packets.append(packet)
                        byte_limit -= len(packet)
                        if byte_limit <= 0:
                            if __debug__:
                                dprint("bandwidth throttle")
                            break

                if packets:
                    if __debug__: dprint("syncing ", len(packets), " packets (", sum(len(packet) for packet in packets), " bytes) over [", time_low, ":", time_high, "] selecting (%", modulo, "+", offset, ") to " , message.candidate)
                    self._send([message.candidate], packets, u"-sync-")

                else:
                    if __debug__: dprint("did not find anything to sync, ignoring dispersy-sync message")

            else:
                if __debug__: dprint("sync disabled (from ", message.candidate, ")")

            # let the message be processed, although that will not actually result in any processing
            # since we choose to already do everything...
            yield message

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
            # pylint: disable-msg=W0404
            from community import Community
            assert isinstance(community, Community)
            assert isinstance(permission_triplets, (tuple, list))
            for triplet in permission_triplets:
                assert isinstance(triplet, tuple)
                assert len(triplet) == 3
                assert isinstance(triplet[0], Member)
                assert isinstance(triplet[1], Message)
                assert isinstance(triplet[2], unicode)
                assert triplet[2] in (u"permit", u"authorize", u"revoke", u"undo")

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

    def on_authorize(self, messages, initializing=False):
        """
        Process a dispersy-authorize message.

        This method is called to process a dispersy-authorize message.  This message is either
        received from a remote source or locally generated.

        @param messages: The received messages.
        @type messages: [Message.Implementation]

        @raise DropMessage: When unable to verify that this message is valid.
        @todo: We should raise a DelayMessageByProof to ensure that we request the proof for this
         message immediately.
        """
        for message in messages:
            if __debug__: dprint(message)
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
            # pylint: disable-msg=W0404
            from community import Community
            assert isinstance(community, Community)
            assert isinstance(permission_triplets, (tuple, list))
            for triplet in permission_triplets:
                assert isinstance(triplet, tuple)
                assert len(triplet) == 3
                assert isinstance(triplet[0], Member)
                assert isinstance(triplet[1], Message)
                assert isinstance(triplet[2], unicode)
                assert triplet[2] in (u"permit", u"authorize", u"revoke", u"undo")

        meta = community.get_meta_message(u"dispersy-revoke")
        message = meta.impl(authentication=((community.master_member if sign_with_master else community.my_member),),
                            distribution=(community.claim_global_time(), self._claim_master_member_sequence_number(community, meta) if sign_with_master else meta.distribution.claim_sequence_number()),
                            payload=(permission_triplets,))

        self.store_update_forward([message], store, update, forward)
        return message

    def on_revoke(self, messages, initializing=False):
        """
        Process a dispersy-revoke message.

        This method is called to process a dispersy-revoke message.  This message is either received
        from an external source or locally generated.

        @param messages: The received messages.
        @type messages: [Message.Implementation]

        @raise DropMessage: When unable to verify that this message is valid.
        @todo: We should raise a DelayMessageByProof to ensure that we request the proof for this
         message immediately.
        """
        for message in messages:
            message.community._timeline.revoke(message.authentication.member, message.distribution.global_time, message.payload.permission_triplets, message)

    def create_undo(self, community, message, sign_with_master=False, store=True, update=True, forward=True):
        """
        Create a dispersy-undo-own or dispersy-undo-other message to undo MESSAGE.

        A dispersy-undo-own message is created when MESSAGE.authentication.member is
        COMMUNITY.my_member and SIGN_WITH_MASTER is False.  Otherwise a dispersy-undo-other message
        is created.

        As a safeguard, when MESSAGE is already marked as undone in the database, the associated
        dispersy-undo-own or dispersy-undo-other message is returned instead of creating a new one.
        None is returned when MESSAGE is already marked as undone and neither of these messages can
        be found.
        """
        if __debug__:
            # pylint: disable-msg=W0404
            from community import Community
            assert isinstance(community, Community)
            assert isinstance(message, Message.Implementation)
            assert isinstance(sign_with_master, bool)
            assert isinstance(store, bool)
            assert isinstance(update, bool)
            assert isinstance(forward, bool)
            assert message.undo_callback, "message does not allow undo"
            assert not message.name in (u"dispersy-undo-own", u"dispersy-undo-other", u"dispersy-authorize", u"dispersy-revoke"), "Currently we do NOT support undoing any of these, as it has consequences for other messages"

        # creating a second dispersy-undo for the same message is malicious behavior (it can cause
        # infinate data traffic).  nodes that notice this behavior must blacklist the offending
        # node.  hence we ensure that we did not send an undo before
        try:
            undone, = self._database.execute(u"SELECT undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                             (community.database_id, message.authentication.member.database_id, message.distribution.global_time)).next()

        except StopIteration:
            assert False, "The message that we want to undo does not exist.  Programming error"
            return None

        else:
            if undone:
                if __debug__: dprint("you are attempting to undo the same message twice.  this should never be attempted as it is considered malicious behavior", level="error")

                # already undone.  refuse to undo again but return the previous undo message
                undo_own_meta = community.get_meta_message(u"dispersy-undo-own")
                undo_other_meta = community.get_meta_message(u"dispersy-undo-other")
                for packet_id, message_id, packet in self._database.execute(u"SELECT id, meta_message, packet FROM sync WHERE community = ? AND member = ? AND meta_message IN (?, ?)",
                                                                            (community.database_id, message.authentication.member.database_id, undo_own_meta.database_id, undo_other_meta.database_id)):
                    msg = Packet(undo_own_meta if undo_own_meta.database_id == message_id else undo_other_meta, str(packet), packet_id).load_message()
                    if message.distribution.global_time == msg.payload.global_time:
                        return msg

                # could not find the undo message that caused the sync.undone to be True.  the
                # undone was probably caused by changing permissions
                return None

            else:
                # create the undo message
                meta = community.get_meta_message(u"dispersy-undo-own" if community.my_member == message.authentication.member and not sign_with_master else u"dispersy-undo-other")
                msg = meta.impl(authentication=((community.master_member if sign_with_master else community.my_member),),
                                distribution=(community.claim_global_time(), self._claim_master_member_sequence_number(community, meta) if sign_with_master else meta.distribution.claim_sequence_number()),
                                payload=(message.authentication.member, message.distribution.global_time, message))

                assert msg.distribution.global_time > message.distribution.global_time

                self.store_update_forward([msg], store, update, forward)
                return msg

    def check_undo(self, messages):
        assert all(message.name in (u"dispersy-undo-own", u"dispersy-undo-other") for message in messages)

        for message in messages:
            # ensure that the message in the payload allows undo
            if not message.payload.packet.meta.undo_callback:
                yield DropMessage(message, "message does not allow undo")
                continue

            # check the timeline
            allowed, _ = message.community._timeline.check(message)
            if not allowed:
                yield DelayMessageByProof(message)
                continue

            try:
                undone, = self._database.execute(u"SELECT undone FROM sync WHERE id = ?", (message.payload.packet.packet_id,)).next()
            except StopIteration:
                assert False, "The conversion ensures that the packet exists in the DB.  Hence this should never occur"
                undone = 0

            if undone and message.name == u"dispersy-undo-own":
                # the dispersy-undo-own message is a curious beast.  Anyone is allowed to create one
                # (regardless of the community settings) and everyone is responsible to propagate
                # these messages.  A malicious member could create an infinite number of
                # dispersy-undo-own messages and thereby take down a community.
                #
                # to prevent this, we allow only one dispersy-undo-own message per message.  When we
                # detect a second message, the member is declared to be malicious and blacklisted.
                # The proof of being malicious is forwarded to other nodes.  The malicious node is
                # now limited to creating only one dispersy-undo-own message per message that she
                # creates.  And that can be limited by revoking her right to create messages.

                # search for the second offending dispersy-undo message
                community = message.community
                member = message.authentication.member
                undo_own_meta = community.get_meta_message(u"dispersy-undo-own")
                for packet_id, packet in self._database.execute(u"SELECT id, packet FROM sync WHERE community = ? AND member = ? AND meta_message = ?",
                                                                            (community.database_id, member.database_id, undo_own_meta.database_id)):
                    msg = Packet(undo_own_meta, str(packet), packet_id).load_message()
                    if message.payload.global_time == msg.payload.global_time:
                        if __debug__: dprint("detected malicious behavior", level="warning")
                        self.declare_malicious_member(member, [msg, message])

                        # the sender apparently does not have the offending dispersy-undo message, lets give
                        self._send([message.candidate], [msg.packet], msg.name)

                        if member == community.my_member:
                            if __debug__: dprint("fatal error.  apparently we are malicious", level="error")

                        yield DropMessage(message, "the message proves that the member is malicious")
                        break

                else:
                    # did not break, hence, the message is not malicious.  more than one members
                    # undid this message
                    yield message

                # continue.  either the message was malicious or it has already been yielded
                continue

            yield message

    def on_undo(self, messages):
        """
        Undo a single message.
        """
        assert all(message.name in (u"dispersy-undo-own", u"dispersy-undo-other") for message in messages)

        self._database.executemany(u"UPDATE sync SET undone = 1 WHERE community = ? AND member = ? AND global_time = ?",
                                   ((message.community.database_id, message.payload.member.database_id, message.payload.global_time) for message in messages))
        for meta, iterator in groupby(messages, key=lambda x: x.payload.packet.meta):
            sub_messages = list(iterator)
            meta.undo_callback([(message.payload.member, message.payload.global_time, message.payload.packet) for message in sub_messages])

            # notify that global times have changed
            # meta.community.update_sync_range(meta, [message.payload.global_time for message in sub_messages])

    def create_destroy_community(self, community, degree, sign_with_master=False, store=True, update=True, forward=True):
        if __debug__:
            # pylint: disable-msg=W0404
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
            # pylint: disable-msg=W0404
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

                # 3. cleanup the malicious_proof table.  we need nothing here anymore
                self._database.execute(u"DELETE FROM malicious_proof WHERE community = ?", (community.database_id,))

            self.reclassify_community(community, new_classification)

    def create_dynamic_settings(self, community, policies, sign_with_master=False, store=True, update=True, forward=True):
        meta = community.get_meta_message(u"dispersy-dynamic-settings")
        message = meta.impl(authentication=((community.master_member if sign_with_master else community.my_member),),
                            distribution=(community.claim_global_time(), self._claim_master_member_sequence_number(community, meta) if sign_with_master else meta.distribution.claim_sequence_number()),
                            payload=(policies,))
        self.store_update_forward([message], store, update, forward)
        return message

    def on_dynamic_settings(self, community, messages, initializing=False):
        assert all(community == message.community for message in messages)
        assert isinstance(initializing, bool)
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

        if not initializing:
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

                    # notify that global times have changed
                    # meta.community.update_sync_range(meta, [message.distribution.global_time for message in undo])

                if redo:
                    executemany(u"UPDATE sync SET undone = 0 WHERE id = ?", ((message.packet_id,) for message in redo))
                    assert self._database.changes == len(redo), (self._database.changes, len(redo))
                    meta.handle_callback(redo)

                    # notify that global times have changed
                    # meta.community.update_sync_range(meta, [message.distribution.global_time for message in redo])

    def sanity_check_generator(self, community):
        """
        Check everything we can about a community.

        Note that messages that are disabled, i.e. not included in community.get_meta_messages(),
        will NOT be checked.

        - the dispersy-identity for my member must be in the database
        - the dispersy-identity must be in the database for each member that has one or more messages in the database
        - all packets in the database must be valid
        - check sequence numbers for FullSyncDistribution
        - check history size for LastSyncDistribution
        """
        def select(sql, bindings):
            assert isinstance(sql, unicode)
            assert isinstance(bindings, tuple)
            limit = 100
            for offset in (i * limit for i in count()):
                rows = list(self._database.execute(sql, bindings + (limit, offset)))
                if rows:
                    for row in rows:
                        yield row
                else:
                    break

        if __debug__: dprint(community.cid.encode("HEX"), " start sanity check")
        enabled_messages = set(meta.database_id for meta in community.get_meta_messages())

        try:
            meta_identity = community.get_meta_message(u"dispersy-identity")
        except KeyError:
            # identity is not enabled
            pass
        else:
            #
            # ensure that the dispersy-identity for my member must be in the database
            #
            try:
                member_id, = self._database.execute(u"SELECT id FROM member WHERE mid = ?", (buffer(community.my_member.mid),)).next()
            except StopIteration:
                raise ValueError("unable to find the public key for my member")

            try:
                self._database.execute(u"SELECT 1 FROM private_key WHERE member = ?", (member_id,)).next()
            except StopIteration:
                raise ValueError("unable to find the private key for my member")

            try:
                self._database.execute(u"SELECT 1 FROM sync WHERE member = ? AND meta_message = ?", (member_id, meta_identity.database_id)).next()
            except StopIteration:
                raise ValueError("unable to find the dispersy-identity message for my member")

            # back-off because the sanity check is very expensive
            if __debug__: dprint("my identity is OK")
            yield Idle()

            #
            # the dispersy-identity must be in the database for each member that has one or more
            # messages in the database
            #
            A = set(id_ for id_, in self._database.execute(u"SELECT member FROM sync WHERE community = ? GROUP BY member", (community.database_id,)))
            B = set(id_ for id_, in self._database.execute(u"SELECT member FROM sync WHERE meta_message = ?", (meta_identity.database_id,)))
            if not len(A) == len(B):
                raise ValueError("inconsistent dispersy-identity messages.", A.difference(B))

            yield Idle()

        #
        # ensure all packets in the database are valid and that the binary packets are consistent
        # with the information stored in the database
        #
        for packet_id, member_id, global_time, meta_message_id, packet in select(u"SELECT id, member, global_time, meta_message, packet FROM sync WHERE community = ? ORDER BY id LIMIT ? OFFSET ?", (community.database_id,)):
            if meta_message_id in enabled_messages:
                packet = str(packet)
                message = self.convert_packet_to_message(packet, community)

                if not message:
                    raise ValueError("unable to convert packet ", packet_id, "@", global_time, " to message")

                if not member_id == message.authentication.member.database_id:
                    raise ValueError("inconsistent member in packet ", packet_id, "@", global_time)

                if not message.authentication.member.public_key:
                    raise ValueError("missing public key for member ", member_id, " in packet ", packet_id, "@", global_time)

                if not global_time == message.distribution.global_time:
                    raise ValueError("inconsistent global time in packet ", packet_id, "@", global_time)

                if not meta_message_id == message.database_id:
                    raise ValueError("inconsistent meta message in packet ", packet_id, "@", global_time)

                if not packet == message.packet:
                    raise ValueError("inconsistent binary in packet ", packet_id, "@", global_time)

                # back-off because the sanity check is very expensive
                if __debug__: dprint("packet ", packet_id, "@", global_time, " is OK")
                yield Idle()

        for meta in community.get_meta_messages():
            #
            # ensure that we have all sequence numbers for FullSyncDistribution packets
            #
            if isinstance(meta.distribution, FullSyncDistribution) and meta.distribution.enable_sequence_number:
                counter = 0
                counter_member_id = 0
                for packet_id, member_id, packet in select(u"SELECT id, member, packet FROM sync WHERE meta_message = ? ORDER BY member, global_time LIMIT ? OFFSET ?", (meta.database_id,)):
                    message = self.convert_packet_to_message(str(packet), community)
                    assert message

                    if member_id != counter_member_id:
                        counter_member_id = member_id
                        counter = 1

                    if not counter == message.distribution.sequence_number:
                        raise ValueError("inconsistent sequence numbers in packet ", packet_id)

                    counter += 1

                    # back-off because the sanity check is very expensive
                    if __debug__: dprint("FullSyncDistribution for '", meta.name, "' is OK")
                    yield Idle()

            #
            # ensure that we have only history-size messages per member
            #
            if isinstance(meta.distribution, LastSyncDistribution):
                if isinstance(meta.authentication, MemberAuthentication):
                    counter = 0
                    counter_member_id = 0
                    for packet_id, member_id, packet in select(u"SELECT id, member, packet FROM sync WHERE meta_message = ? ORDER BY member ASC, global_time DESC LIMIT ? OFFSET ?", (meta.database_id,)):
                        message = self.convert_packet_to_message(str(packet), community)
                        assert message

                        if member_id == counter_member_id:
                            counter += 1
                        else:
                            counter_member_id = member_id
                            counter = 1

                        if counter > meta.distribution.history_size:
                            raise ValueError("decayed packet ", packet_id, " still in database")

                        # back-off because the sanity check is very expensive
                        if __debug__: dprint("LastSyncDistribution for '", meta.name, "' is OK")
                        yield Idle()

                else:
                    assert isinstance(meta.authentication, MultiMemberAuthentication)
                    counters = {}
                    for packet_id, member_id, packet in select(u"SELECT id, member, packet FROM sync WHERE meta_message = ? ORDER BY member ASC, global_time DESC LIMIT ? OFFSET ?", (meta.database_id,)):
                        message = self.convert_packet_to_message(str(packet), community)
                        assert message

                        members = list(self._database.execute(u"SELECT member FROM reference_member_sync WHERE sync = ? ORDER BY member", (packet_id,)))
                        if members in counters:
                            counters[members] += 1
                        else:
                            counters[members] = 1

                        # 1. there are meta.authentication.count entries in reference_member_sync per entry in sync
                        if not len(members) == meta.authentication.count:
                            raise ValueError("inconsistent references in packet ", packet_id)

                        # 2. there are meta.distribution.history_size or less (member 1, member 2, ..., member N)
                        if counters[members] > meta.distribution.history_size:
                            raise ValueError("decayed packet ", packet_id, " still in database")

                        # back-off because the sanity check is very expensive
                        if __debug__: dprint("LastSyncDistribution for '", meta.name, "' is OK")
                        yield Idle()

        if __debug__: dprint(community.cid.encode("HEX"), " success")
        yield Return(True)

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
        assert isinstance(meta.distribution, FullSyncDistribution), "currently only FullSyncDistribution allows sequence numbers"
        sequence_number, = self._database.execute(u"SELECT COUNT(1) FROM sync WHERE member = ? AND sync.meta_message = ?",
                                                  (community.master_member.database_id, meta.database_id)).next()
        return sequence_number + 1

    def _watchdog(self):
        """
        Periodically called to flush changes to disk, most importantly, it will catch the
        GeneratorExit exception when it is thrown to properly shutdown the database.
        """
        while True:
            try:
                desync = (yield 60.0)
                if desync > 0.1:
                    self._statistics.increment_busy_time(desync)
                    yield desync

                # flush changes to disk every 1 minutes
                self._database.commit()
            except GeneratorExit:
                if __debug__: dprint("shutdown")
                self._database.commit()
                break

    def _candidate_walker(self):
        """
        Periodically select a candidate and take a step in the network.
        """
        walker_communities = self._walker_commmunities

        while walker_communities:
            community = walker_communities.pop(0)
            walker_communities.append(community)

            # walk
            assert community.dispersy_enable_candidate_walker
            assert community.dispersy_enable_candidate_walker_responses
            community.dispersy_take_step()

            # delay will never be less than 0.05, hence we can accommodate 100 communities
            # before the interval between each step becomes larger than 5.0 seconds
            delay = max(0.05, 5.0 / len(walker_communities))
            if __debug__: dprint("there are ", len(walker_communities), " walker enabled communities.  pausing ", delay, "s between each step")

            desync = (yield delay)
            if desync > 0.1:
                self._statistics.increment_busy_time(desync)
                yield desync

    if __debug__:
        def _stats_candidates(self):
            while True:
                yield 10.0
                dprint("---")
                for community in sorted(self._communities.itervalues(), key=lambda community: community.cid):
                    candidates = list(self.yield_all_candidates(community))
                    dprint(" ", community.cid.encode("HEX"), " ", "%20s" % community.get_classification(), " with ", len(candidates), " candidates[:5] ", ", ".join("%s:%d" % candidate.address for candidate in candidates[:5]))

        def _stats_conversion(self):
            # pylint: disable-msg=W0404
            from conversion import Conversion

            while True:
                yield 10.0
                stats = Conversion.debug_stats
                total = stats["encode-message"]
                dprint("=== encoding ", stats["-encode-count"], " messages took ", "%.2fs" % total)
                for key, value in sorted(stats.iteritems()):
                    if key.startswith("encode") and not key == "encode-message" and total:
                        dprint("%7.2fs" % value, " ~%5.1f%%" % (100.0 * value / total), " ", key)

                total = stats["decode-message"]
                dprint("=== decoding ", stats["-decode-count"], " messages took ", "%.2fs" % total)
                for key, value in sorted(stats.iteritems()):
                    if key.startswith("decode") and not key == "decode-message" and total:
                        dprint("%7.2fs" % value, " ~%5.1f%%" % (100.0 * value / total), " ", key)

        def _stats_triggers(self):
            while True:
                yield 10.0
                for counter, trigger in enumerate(self._triggers):
                    dprint("%3d " % (counter + 1), trigger)

        def _stats_info(self):
            while True:
                yield 10.0
                dprint(self._statistics.summary(), pprint=True)

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
        # 1.5: replaced some dispersy_candidate_... attributes and added a dump of the candidates
        # 1.6: new random walk candidates and my LAN and WAN addresses
        # 1.7: removed several community attributes, no longer calling reset on self._statistics
        # 1.8: added busy_time to the statistics (delay caused by overloaded cpu/disk)
        # 1.9: removed sync_ranges
        # 2.0: changed the statistics.  total_up and total_down are now both (amount, byte_count) tuples
        # 2.1: community["candidates"] is now be None when the candidate walker is disabled, new
        #      "dispersy_enable_candidate_walker" attribute
        # 2.2: community["candidates"] is again always a list, new
        #      "dispersy_enable_candidate_walker_responses" attribute

        info = {"version":2.2, "class":"Dispersy", "lan_address":self._lan_address, "wan_address":self._wan_address}

        if statistics:
            info["statistics"] = self._statistics.info()

        info["communities"] = []
        for community in self._communities.itervalues():
            community_info = {"classification":community.get_classification(), "hex_cid":community.cid.encode("HEX"), "global_time":community.global_time}
            info["communities"].append(community_info)

            if attributes:
                community_info["attributes"] = dict((attr, getattr(community, attr))
                                                    for attr
                                                    in ("dispersy_sync_bloom_filter_error_rate",
                                                        "dispersy_sync_bloom_filter_bits",
                                                        "dispersy_sync_response_limit",
                                                        "dispersy_missing_sequence_response_limit",
                                                        "dispersy_enable_candidate_walker",
                                                        "dispersy_enable_candidate_walker_responses"))

            # if sync_ranges:
            #     community_info["sync_ranges"] = [{"time_low":range_.time_low, "space_freed":range_.space_freed, "space_remaining":range_.space_remaining, "capacity":range_.capacity}
            #                                      for range_
            #                                      in community._sync_ranges]

            if database_sync:
                community_info["database_sync"] = dict(self._database.execute(u"SELECT meta_message.name, COUNT(sync.id) FROM sync JOIN meta_message ON meta_message.id = sync.meta_message WHERE sync.community = ? GROUP BY sync.meta_message", (community.database_id,)))

            if candidate:
                community_info["candidates"] = [(candidate.lan_address, candidate.wan_address) for candidate in self._candidates.itervalues() if candidate.in_community(community)]
                if __debug__: dprint(community_info["classification"], " has ", len(community_info["candidates"]), " candidates")

        if __debug__: dprint(info, pprint=True)
        return info
