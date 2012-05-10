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

import os
import sys

from hashlib import sha1
from itertools import groupby, islice, count
from random import random, shuffle
from socket import inet_aton, error as socket_error
from time import time

from authentication import NoAuthentication, MemberAuthentication, MultiMemberAuthentication
from bloomfilter import BloomFilter
from bootstrap import get_bootstrap_candidates
from callback import Callback
from candidate import BootstrapCandidate, LoopbackCandidate, WalkCandidate, Candidate
from destination import CommunityDestination, CandidateDestination, MemberDestination, SubjectiveDestination
from dispersydatabase import DispersyDatabase
from distribution import SyncDistribution, FullSyncDistribution, LastSyncDistribution, DirectDistribution
from dprint import dprint
from endpoint import DummyEndpoint
from member import DummyMember, Member, MemberFromId, MemberWithoutCheck
from message import BatchConfiguration, Packet, Message
from message import DropMessage, DelayMessage, DelayMessageByProof, DelayMessageBySequence, DelayMessageBySubjectiveSet
from message import DropPacket, DelayPacket, DelayPacketUsingIdentifier
from payload import AuthorizePayload, RevokePayload, UndoPayload
from payload import DestroyCommunityPayload
from payload import DynamicSettingsPayload
from payload import IdentityPayload, MissingIdentityPayload
from payload import IntroductionRequestPayload, IntroductionResponsePayload, PunctureRequestPayload, PuncturePayload
from payload import MissingMessagePayload, MissingLastMessagePayload
from payload import MissingSequencePayload, MissingProofPayload
from payload import SignatureRequestPayload, SignatureResponsePayload
from payload import SubjectiveSetPayload, MissingSubjectiveSetPayload
from requestcache import Cache, RequestCache
from resolution import PublicResolution, LinearResolution
from singleton import Singleton
from trigger import TriggerCallback, TriggerPacket, TriggerMessage

from Tribler.Core.NATFirewall.guessip import get_my_wan_ip

if __debug__:
    from candidate import Candidate

# callback priorities.  note that a lower value is less priority
TRIGGER_CHECK_PRIORITY = -1
TRIGGER_TIMEOUT_PRIORITY = -2
assert isinstance(TRIGGER_CHECK_PRIORITY, int)
assert isinstance(TRIGGER_TIMEOUT_PRIORITY, int)
assert TRIGGER_TIMEOUT_PRIORITY < TRIGGER_CHECK_PRIORITY, "an existing trigger should not timeout before being checked"

# the callback identifier for the task that periodically takes a step
CANDIDATE_WALKER_CALLBACK_ID = "dispersy-candidate-walker"

class SignatureRequestCache(Cache):
    cleanup_delay = 0.0

    def __init__(self, members, response_func, response_args, timeout):
        self.request = None
        self.members = members
        self.response_func = response_func
        self.response_args = response_args
        self.timeout_delay = timeout

    def on_timeout(self):
        self.response_func(self.request.payload.message, None, True, *self.response_args)

class IntroductionRequestCache(Cache):
    # we will accept the response at most 10.5 seconds after our request
    timeout_delay = 10.5
    # the cache remains available at most 4.5 after receiving the response.  this gives some time to
    # receive the puncture message
    if __debug__:
        cleanup_delay = 304.5
    else:
        cleanup_delay = 4.5

    def __init__(self, community, helper_candidate):
        self.community = community
        self.helper_candidate = helper_candidate
        self.response_candidate = None
        self.puncture_candidate = None
        if __debug__:
            self.request_time = time()
            self.timeout_occurred = False

    def on_timeout(self):
        # helper_candidate did not respond to a request message in this community.  after some time
        # inactive candidates become obsolete and will be removed by
        # _periodically_cleanup_candidates
        if __debug__:
            dprint("timeout for ", self.helper_candidate)
            self.community.dispersy._statistics.walk_fail(self.helper_candidate.sock_addr)
            self.timeout_occurred = True

        # we choose to set the entire helper to inactive instead of just the community where the
        # timeout occurred.  this will allow us to quickly respond to nodes going offline, while the
        # downside is that one dropped packet will cause us to invalidly inactivate all communities
        # of the candidate.
        now = time()
        self.helper_candidate.obsolete(self.community, now)
        self.helper_candidate.all_inactive(now)

class DelayedPacketCache(Cache):
    cleanup_delay = 0.0

    def __init__(self, timeout):
        self.timeout_delay = timeout
        self.callbacks = []

    def on_timeout(self):
        if __debug__: dprint(len(self.callbacks), " callbacks")
        for func, args in self.callbacks:
            func(None, *args)

    @staticmethod
    def properties_to_identifier(*args):
        raise NotImplementedError()

    @staticmethod
    def message_to_identifier(message):
        raise NotImplementedError()

class MissingMemberCache(DelayedPacketCache):
    @staticmethod
    def properties_to_identifier(community, member):
        return "-missing-member-%s-%s-" % (community.cid, member.mid)

    @staticmethod
    def message_to_identifier(message):
        return "-missing-member-%s-%s-" % (message.community.cid, message.authentication.member.mid)

class MissingMessageCache(DelayedPacketCache):
    @staticmethod
    def properties_to_identifier(community, member, global_time):
        return "-missing-message-%s-%s-%d-" % (community.cid, member.mid, global_time)

    @staticmethod
    def message_to_identifier(message):
        return "-missing-message-%s-%s-%d-" % (message.community.cid, message.authentication.member.mid, message.distribution.global_time)

class MissingLastMessageCache(DelayedPacketCache):
    @staticmethod
    def properties_to_identifier(community, member, message):
        return "-missing-last-message-%s-%s-%s-" % (community.cid, member.mid, message.name.encode("UTF-8"))

    @staticmethod
    def message_to_identifier(message):
        return "-missing-last-message-%s-%s-%s-" % (message.community.cid, message.authentication.member.mid, message.name.encode("UTF-8"))

class Statistics(object):
    def __init__(self):
        self._start = time()
        self._sequence_number = 0
        self._walk_attempt = 0
        self._walk_success = 0
        self._walk_reset = 0
        if __debug__:
            self._drop = {}
            self._delay = {}
            self._success = {}
            self._outgoing = {}
            self._walk_fail = {}

    def info(self):
        """
        Returns all statistics.
        """
        if __debug__:
            return {"drop":self._drop,
                    "delay":self._delay,
                    "success":self._success,
                    "outgoing":self._outgoing,
                    "sequence_number":self._sequence_number,
                    "start":self._start,
                    "runtime":time() - self._start,
                    "walk_attempt":self._walk_attempt,
                    "walk_success":self._walk_success,
                    "walk_reset":self._walk_reset,
                    "walk_fail":self._walk_fail}

        else:
            return {"sequence_number":self._sequence_number,
                    "start":self._start,
                    "runtime":time() - self._start,
                    "walk_attempt":self._walk_attempt,
                    "walk_success":self._walk_success,
                    "walk_reset":self._walk_reset}

    def reset(self):
        """
        Returns, and subsequently removes, all statistics.
        """
        try:
            return self.info()

        finally:
            self._sequence_number += 1
            self._walk_attempt = 0
            self._walk_success = 0
            self._walk_reset = 0
            if __debug__:
                self._drop = {}
                self._delay = {}
                self._success = {}
                self._outgoing = {}
                self._walk_fail = {}

    if __debug__:
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

        def outgoing(self, key, byte_count, amount=1):
            """
            Called when a message send using the _send(...) method
            """
            assert isinstance(key, (str, unicode))
            assert isinstance(byte_count, (int, long))
            assert isinstance(amount, (int, long))
            a, b = self._outgoing.get(key, (0, 0))
            self._outgoing[key] = (a+amount, b+byte_count)

        def walk_fail(self, sock_addr):
            if sock_addr in self._walk_fail:
                self._walk_fail[sock_addr] += 1
            else:
                self._walk_fail[sock_addr] = 1

    def increment_walk_attempt(self):
        self._walk_attempt += 1

    def increment_walk_success(self):
        self._walk_success += 1

    def increment_walk_reset(self):
        self._walk_reset += 1

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
        self._working_directory = os.path.abspath(working_directory)

        # our data storage
        sqlite_directory = os.path.join(self._working_directory, u"sqlite")
        if not os.path.isdir(sqlite_directory):
            os.makedirs(sqlite_directory)
        self._database = DispersyDatabase.get_instance(sqlite_directory)

        # peer selection candidates.  address:Candidate pairs (where
        # address is obtained from socket.recv_from)
        self._candidates = {}
        self._callback.register(self._periodically_cleanup_candidates)

        # assigns temporary cache objects to unique identifiers
        self._request_cache = RequestCache(self._callback)

        # indicates what our connection type is.  currently it can be u"unknown", u"public", or
        # u"symmetric-NAT"
        self._connection_type = u"unknown"

        # our LAN and WAN addresses
        self._lan_address = (get_my_wan_ip() or "0.0.0.0", 0)
        self._wan_address = ("0.0.0.0", 0)
        self._wan_address_votes = {}
        if __debug__:
            dprint("my LAN address is ", self._lan_address[0], ":", self._lan_address[1], force=True)
            dprint("my WAN address is ", self._wan_address[0], ":", self._wan_address[1], force=True)

        # bootstrap peers
        bootstrap_candidates = get_bootstrap_candidates(self)
        if not all(bootstrap_candidates):
            self._callback.register(self._retry_bootstrap_candidates)
        self._bootstrap_candidates = dict((candidate.sock_addr, candidate) for candidate in bootstrap_candidates if candidate)

        # communities that can be auto loaded.  classification:(cls, args, kargs) pairs.
        self._auto_load_communities = {}

        # loaded communities.  cid:Community pairs.
        self._communities = {}
        self._walker_commmunities = []

        # communication endpoint
        self._endpoint = DummyEndpoint()

        # triggers for incoming messages
        self._triggers = []
        self._untriggered_messages = []

        self._check_distribution_batch_map = {DirectDistribution:self._check_direct_distribution_batch,
                                              FullSyncDistribution:self._check_full_sync_distribution_batch,
                                              LastSyncDistribution:self._check_last_sync_distribution_batch}

        # progress handlers (used to notify the user when something will take a long time)
        self._progress_handlers = []

        # commit changes to the database periodically
        self._callback.register(self._watchdog)

        # statistics...
        self._statistics = Statistics()

        if __debug__:
            self._callback.register(self._stats_candidates)
            self._callback.register(self._stats_detailed_candidates)
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
            candidates = get_bootstrap_candidates(self)
            for candidate in candidates:
                if candidate is None:
                    break
            else:
                if __debug__: dprint("resolved all bootstrap addresses")
                self._bootstrap_candidates = dict((candidate.sock_addr, candidate) for candidate in candidates if candidate)
                break

    @property
    def working_directory(self):
        """
        The full directory path where all dispersy related files are stored.
        @rtype: unicode
        """
        return self._working_directory

    # @property
    def __get_endpoint(self):
        """
        The endpoint object used to send packets.
        @rtype: Object with a send(address, data) method
        """
        return self._endpoint
    # @endpoint.setter
    def __set_endpoint(self, endpoint):
        """
        Set a endpoint object.
        @param endpoint: The endpoint object.
        @type endpoint: Object with a send(address, data) method
        """
        self._endpoint = endpoint

        host, port = endpoint.get_address()
        if __debug__: dprint("update LAN address ", self._lan_address[0], ":", self._lan_address[1], " -> ", self._lan_address[0], ":", port, force=True)
        self._lan_address = (self._lan_address[0], port)

        # at this point we do not yet have a WAN address, set it to the LAN address to ensure we
        # have something
        assert self._wan_address == ("0.0.0.0", 0)
        if __debug__: dprint("update WAN address ", self._wan_address[0], ":", self._wan_address[1], " -> ", self._lan_address[0], ":", self._lan_address[1], force=True)
        self._wan_address = self._lan_address

        if not self._is_valid_lan_address(self._lan_address, check_my_lan_address=False):
            if __debug__: dprint("update LAN address ", self._lan_address[0], ":", self._lan_address[1], " -> ", host, ":", self._lan_address[1], force=True)
            self._lan_address = (host, self._lan_address[1])

            if not self._is_valid_lan_address(self._lan_address, check_my_lan_address=False):
                if __debug__: dprint("update LAN address ", self._lan_address[0], ":", self._lan_address[1], " -> ", self._wan_address[0], ":", self._lan_address[1], force=True)
                self._lan_address = (self._wan_address[0], self._lan_address[1])

        # our address may not be a bootstrap address
        if self._lan_address in self._bootstrap_candidates:
            del self._bootstrap_candidates[self._lan_address]

        # our address may not be a candidate
        if self._lan_address in self._candidates:
            del self._candidates[self._lan_address]
    # .setter was introduced in Python 2.6
    endpoint = property(__get_endpoint, __set_endpoint)

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
    def connection_type(self):
        """
        The connection type that we believe we have.

        Currently the following types are recognized:
        - u'unknown': the default value until the actual type can be recognized.
        - u'public': when the LAN and WAN addresses are determined to be the same.
        - u'symmetric-NAT': when each remote peer reports different external port numbers.

        @rtype: unicode
        """
        return self._connection_type

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

    @property
    def request_cache(self):
        """
        The request cache instance responsible for maintaining identifiers and timeouts for
        outstanding requests.
        @rtype: RequestCache
        """
        return self._request_cache

    @property
    def statistics(self):
        """
        The Statistics instance.
        """
        return self._statistics

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
        messages = [Message(community, u"dispersy-identity", MemberAuthentication(encoding="bin"), PublicResolution(), LastSyncDistribution(synchronization_direction=u"ASC", priority=16, history_size=1), CommunityDestination(node_count=0), IdentityPayload(), self._generic_timeline_check, self.on_identity),
                    Message(community, u"dispersy-signature-request", NoAuthentication(), PublicResolution(), DirectDistribution(), MemberDestination(), SignatureRequestPayload(), self.check_signature_request, self.on_signature_request),
                    Message(community, u"dispersy-signature-response", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), SignatureResponsePayload(), self.check_signature_response, self.on_signature_response),
                    Message(community, u"dispersy-authorize", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=10), AuthorizePayload(), self._generic_timeline_check, self.on_authorize),
                    Message(community, u"dispersy-revoke", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=10), RevokePayload(), self._generic_timeline_check, self.on_revoke),
                    Message(community, u"dispersy-undo-own", MemberAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=10), UndoPayload(), self.check_undo, self.on_undo),
                    Message(community, u"dispersy-undo-other", MemberAuthentication(), LinearResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=10), UndoPayload(), self.check_undo, self.on_undo),
                    Message(community, u"dispersy-destroy-community", MemberAuthentication(), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=192), CommunityDestination(node_count=50), DestroyCommunityPayload(), self._generic_timeline_check, self.on_destroy_community),
                    Message(community, u"dispersy-subjective-set", MemberAuthentication(), PublicResolution(), LastSyncDistribution(synchronization_direction=u"ASC", priority=16, history_size=1), CommunityDestination(node_count=0), SubjectiveSetPayload(), self._generic_timeline_check, self.on_subjective_set),
                    Message(community, u"dispersy-dynamic-settings", MemberAuthentication(), LinearResolution(), FullSyncDistribution(enable_sequence_number=True, synchronization_direction=u"DESC", priority=191), CommunityDestination(node_count=10), DynamicSettingsPayload(), self._generic_timeline_check, community.dispersy_on_dynamic_settings),

                    #
                    # when something is missing, a dispersy-missing-... message can be used to request
                    # it from another peer
                    #

                    # when we have a member id (20 byte sha1 of the public key) but not the public key
                    Message(community, u"dispersy-missing-identity", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), MissingIdentityPayload(), self._generic_timeline_check, self.on_missing_identity),

                    # when we are missing one or more SyncDistribution messages in a certain sequence
                    Message(community, u"dispersy-missing-sequence", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), MissingSequencePayload(), self._generic_timeline_check, self.on_missing_sequence, batch=BatchConfiguration(max_window=0.1)),

                    # when we have a reference to a message that we do not have.  a reference consists
                    # of the community identifier, the member identifier, and the global time
                    Message(community, u"dispersy-missing-message", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), MissingMessagePayload(), self._generic_timeline_check, self.on_missing_message),

                    # when we are missing the subjective set, with a specific cluster, from a member
                    Message(community, u"dispersy-missing-subjective-set", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), MissingSubjectiveSetPayload(), self._generic_timeline_check, self.on_missing_subjective_set),

                    # when we might be missing a dispersy-authorize message
                    Message(community, u"dispersy-missing-proof", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), MissingProofPayload(), self._generic_timeline_check, self.on_missing_proof),

                    # when we have a reference to a LastSyncDistribution that we do not have.  a
                    # reference consists of the community identifier and the member identifier
                    Message(community, u"dispersy-missing-last-message", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), MissingLastMessagePayload(), self._generic_timeline_check, self.on_missing_last_message),
                    ]

        if community.dispersy_enable_candidate_walker_responses:
            messages.extend([Message(community, u"dispersy-introduction-request", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), IntroductionRequestPayload(), self.check_introduction_request, self.on_introduction_request),
                             Message(community, u"dispersy-introduction-response", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), IntroductionResponsePayload(), self.check_introduction_response, self.on_introduction_response),
                             Message(community, u"dispersy-puncture-request", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PunctureRequestPayload(), self.check_puncture_request, self.on_puncture_request),
                             Message(community, u"dispersy-puncture", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PuncturePayload(), self.check_puncture, self.on_puncture)])

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

    def attach_progress_handler(self, func):
        assert callable(func), "handler must be callable"
        self._progress_handlers.append(func)

    def detach_progress_handler(self, func):
        assert callable(func), "handler must be callable"
        assert func in self._progress_handlers, "handler is not attached"
        self._progress_handlers.remove(func)

    def get_progress_handlers(self):
        return self._progress_handlers

    def get_member(self, public_key, private_key=""):
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
        assert isinstance(private_key, str)
        return Member(public_key, private_key)

    def get_members_from_id(self, mid, cache=True):
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
        if cache:
            try:
                return [MemberFromId(mid)]
            except LookupError:
                pass

        # note that this allows a security attack where someone might obtain a crypographic key that
        # has the same sha1 as the master member, however unlikely.  the only way to prevent this,
        # as far as we know, is to increase the size of the community identifier, for instance by
        # using sha256 instead of sha1.
        return [MemberWithoutCheck(str(public_key))
                for public_key,
                in list(self._database.execute(u"SELECT public_key FROM member WHERE mid = ?", (buffer(mid),)))
                if public_key]

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
        community.dispersy_check_database()

        if community.dispersy_enable_candidate_walker:
            self._walker_commmunities.insert(0, community)
            # restart walker scheduler
            self._callback.replace_register(CANDIDATE_WALKER_CALLBACK_ID, self._candidate_walker)

        # schedule the sanity check... it also checks that the dispersy-identity is available and
        # when this is a create or join this message is created only after the attach_community
        if __debug__:
            if "--sanity-check" in sys.argv:
                try:
                    self.sanity_check_generator(community)
                except ValueError:
                    dprint(exception=True, level="error")
                    assert False

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
            self._callback.replace_register(CANDIDATE_WALKER_CALLBACK_ID, self._candidate_walker)

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
        @type cid: string, of any size

        @param load: When True, will load the community when available and not yet loaded.
        @type load: bool

        @param auto_load: When True, will load the community when available, the auto_load flag is
         True, and, not yet loaded.
        @type load: bool

        @warning: It is possible, however unlikely, that multiple communities will have the same
         cid.  This is currently not handled.
        """
        assert isinstance(cid, str)
        assert isinstance(load, bool)
        assert isinstance(auto_load, bool)

        if len(cid) == 20:
            if not cid in self._communities:
                try:
                    # have we joined this community
                    classification, auto_load_flag, master_public_key = self._database.execute(u"SELECT community.classification, community.auto_load, member.public_key FROM community JOIN member ON member.id = community.master WHERE mid = ?",
                                                                                               (buffer(cid),)).next()

                except StopIteration:
                    pass

                else:
                    if load or (auto_load and auto_load_flag):

                        if classification in self._auto_load_communities:
                            master = Member(str(master_public_key)) if master_public_key else DummyMember(cid)
                            cls, args, kargs = self._auto_load_communities[classification]
                            cls.load_community(master, *args, **kargs)
                            assert master.mid in self._communities

                        else:
                            if __debug__: dprint("unable to auto load, '", classification, "' is an undefined classification [", cid.encode("HEX"), "]", level="error")

                    else:
                        if __debug__: dprint("not allowed to load '", classification, "'")

            return self._communities[cid]

        raise KeyError(cid)

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
        if __debug__:
            # pylint: disable-msg=W0404
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(member, Member)
        assert isinstance(global_time, (int, long))
        try:
            packet, = self._database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                             (community.database_id, member.database_id, global_time)).next()
        except StopIteration:
            return None
        else:
            return self.convert_packet_to_message(str(packet), community)

    def get_last_message(self, community, member, meta):
        if __debug__:
            # pylint: disable-msg=W0404
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(member, Member)
        assert isinstance(meta, Message)
        try:
            packet, = self._database.execute(u"SELECT packet FROM sync WHERE member = ? AND meta_message = ? ORDER BY global_time DESC LIMIT 1",
                                             (member.database_id, meta.database_id)).next()
        except StopIteration:
            return None
        else:
            return self.convert_packet_to_message(str(packet), community)

    def wan_address_unvote(self, voter):
        """
        Removes and returns one vote made by VOTER.
        """
        assert isinstance(voter, Candidate)
        for vote, voters in self._wan_address_votes.iteritems():
            if voter.sock_addr in voters:
                if __debug__: dprint("removing vote for ", vote, " made by ", voter)
                voters.remove(voter.sock_addr)
                if len(voters) == 0:
                    del self._wan_address_votes[vote]
                return vote

    def wan_address_vote(self, address, voter):
        """
        Add one vote and possibly re-determine our wan address.

        Our wan address is determined by majority voting.  Each time when we receive a message
        that contains anothers opinion about our wan address, we take this into account.  The
        address with the most votes wins.

        Usually these votes are received through dispersy-candidate-request and
        dispersy-candidate-response messages.

        @param address: The wan address that the voter believes us to have.
        @type address: (str, int)

        @param voter: The voter candidate.
        @type voter: Candidate
        """
        assert isinstance(address, tuple)
        assert len(address) == 2
        assert isinstance(address[0], str)
        assert isinstance(address[1], int)
        assert isinstance(voter, Candidate)
        if self._wan_address[0] in (voter.wan_address[0], voter.sock_addr[0]):
            if __debug__: dprint("ignoring vote from candidate on the same LAN")
            return

        if not self._is_valid_wan_address(address, check_my_wan_address=False):
            if __debug__: dprint("got invalid external vote from ", voter, " received ", address[0], ":", address[1])
            return

        # undo previous vote
        self.wan_address_unvote(voter)

        # do vote
        votes = self._wan_address_votes
        if not address in votes:
            votes[address] = set()
        votes[address].add(voter.sock_addr)

        if __debug__: dprint(["%5d %15s:%-d [%s]" % (len(voters), vote[0], vote[1], ", ".join("%s:%d" % key for key in voters)) for vote, voters in votes.iteritems()], lines=True)

        # change when new vote count equal or higher than old address vote count
        if self._wan_address != address and len(votes[address]) >= len(votes.get(self._wan_address, ())):
            if len(votes) > 1:
                if __debug__: dprint("not updating WAN address, suspect symmetric NAT")
                self._connection_type = u"symmetric-NAT"
                return

            # it is possible that, for some time after the WAN address changes, we will believe
            # that the connection type is symmetric NAT.  once votes decay we may find that we
            # are no longer behind a symmetric-NAT
            if self._connection_type == u"symmetric-NAT":
                self._connection_type = u"unknown"

            if __debug__: dprint("update WAN address ", self._wan_address[0], ":", self._wan_address[1], " -> ", address[0], ":", address[1], force=True)
            self._wan_address = address

            if not self._is_valid_lan_address(self._lan_address, check_my_lan_address=False):
                if __debug__: dprint("update LAN address ", self._lan_address[0], ":", self._lan_address[1], " -> ", self._wan_address[0], ":", self._lan_address[1], force=True)
                self._lan_address = (self._wan_address[0], self._lan_address[1])

            # our address may not be a bootstrap address
            if self._wan_address in self._bootstrap_candidates:
                del self._bootstrap_candidates[self._wan_address]

            # our address may not be a candidate
            if self._wan_address in self._candidates:
                del self._candidates[self._wan_address]

        if self._connection_type == u"unknown" and self._lan_address == self._wan_address:
            self._connection_type = u"public"

    def _is_duplicate_sync_message(self, message):
        """
        Returns True when this message is a duplicate, otherwise the message must be processed.

        === Problem: duplicate message ===

        The simplest reason to reject an incoming message is when we already have it.  No further
        action is performed.


        === Problem: duplicate message, but that message is undone ===

        When a message is undone it should no longer be synced.  Hence, someone who syncs an undone
        message must not be aware of the undo message yet.  We will drop this message, but we will
        also send the appropriate undo message as a response.


        === Problem: same payload, different signature ===

        There is a possibility that a message is created that contains exactly the same payload but
        has a different signature.  This can occur when a message is created, forwarded, and for
        some reason the database is reset.  The next time that the client starts the exact same
        message may be generated.  However, because EC signatures contain a random element the
        signature will be different.

        This results in continues transfers because the bloom filters identify the two messages
        as different while the community/member/global_time triplet is the same.

        To solve this, we will silently replace one message with the other.  We choose to keep
        the message with the highest binary value while destroying the one with the lower binary
        value.


        === Optimization: temporarily modify the bloom filter ===

        Note: currently we generate bloom filters on the fly, therefore, we can not use this
        optimization.

        To further optimize, we will add both messages to our bloom filter whenever we detect
        this problem.  This will ensure that we do not needlessly receive the 'invalid' message
        until the bloom filter is synced with the database again.
        """
        community = message.community
        # fetch the duplicate binary packet from the database
        try:
            packet, undone = self._database.execute(u"SELECT packet, undone FROM sync WHERE community = ? AND member = ? AND global_time = ?",
                                                    (community.database_id, message.authentication.member.database_id, message.distribution.global_time)).next()
        except StopIteration:
            # this message is not a duplicate
            return False

        else:
            packet = str(packet)
            if packet == message.packet:
                # exact binary duplicates, do NOT process the message
                if __debug__: dprint(message.candidate, " received identical message [", message.name, " ", message.authentication.member.database_id, "@", message.distribution.global_time, " undone" if undone else "", "]")

                if undone:
                    try:
                        proof, = self._database.execute(u"SELECT packet FROM sync WHERE id = ?", (undone,)).next()
                    except StopIteration:
                        pass
                    else:
                        if __debug__:
                            self._statistics.outgoing(u"-duplicate-undo-", len(proof), 1)
                        self._endpoint.send([message.candidate], [str(proof)])

            else:
                signature_length = message.authentication.member.signature_length
                if packet[:signature_length] == message.packet[:signature_length]:
                    # the message payload is binary unique (only the signature is different)
                    if __debug__: dprint("received identical message with different signature [member:", message.authentication.member.database_id, "; @", message.distribution.global_time, "]")

                    if packet < message.packet:
                        # replace our current message with the other one
                        self._database.execute(u"UPDATE sync SET packet = ? WHERE community = ? AND member = ? AND global_time = ?",
                                               (buffer(message.packet), community.database_id, message.authentication.member.database_id, message.distribution.global_time))

                        # notify that global times have changed
                        # community.update_sync_range(message.meta, [message.distribution.global_time])

                else:
                    if __debug__: dprint("received message with duplicate community/member/global-time triplet.  possibly malicious behavior", level="warning")

            # this message is a duplicate
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

        # refuse messages where the global time is unreasonably high
        acceptable_global_time = messages[0].community.acceptable_global_time

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
                if message.distribution.global_time > acceptable_global_time:
                    yield DropMessage(message, "global time is not within acceptable range (%d, we accept %d)" % (message.distribution.global_time, acceptable_global_time))
                    continue

                key = (message.authentication.member, message.distribution.global_time)
                if key in unique:
                    yield DropMessage(message, "duplicate message by member^global_time (1)")
                    continue

                unique.add(key)
                seq = highest[message.authentication.member]

                if seq >= message.distribution.sequence_number:
                    # we already have this message (drop)
                    # TODO: something similar to _is_duplicate_sync_message can occur...
                    yield DropMessage(message, "duplicate message by sequence_number (we have %d, message has %d)"%(seq, message.distribution.sequence_number))
                    continue

                if seq + 1 != message.distribution.sequence_number:
                    # we do not have the previous message (delay and request)
                    yield DelayMessageBySequence(message, seq+1, message.distribution.sequence_number-1)
                    continue

                # we have the previous message, check for duplicates based on community,
                # member, and global_time
                if self._is_duplicate_sync_message(message):
                    # we have the previous message (drop)
                    yield DropMessage(message, "duplicate message by global_time (1)")
                    continue

                # we accept this message
                highest[message.authentication.member] += 1
                yield message

        else:
            for message in messages:
                if message.distribution.global_time > acceptable_global_time:
                    yield DropMessage(message, "global time is not within acceptable range")
                    continue

                key = (message.authentication.member, message.distribution.global_time)
                if key in unique:
                    yield DropMessage(message, "duplicate message by member^global_time (2)")
                    continue

                unique.add(key)

                # check for duplicates based on community, member, and global_time
                if self._is_duplicate_sync_message(message):
                    # we have the previous message (drop)
                    yield DropMessage(message, "duplicate message by global_time (2)")
                    continue

                # we accept this message
                yield message

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

                if message.distribution.global_time in tim and self._is_duplicate_sync_message(message):
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
                            if __debug__:
                                self._statistics.outgoing(u"-sequence-", len(packet), 1)
                            self._endpoint.send([message.candidate], [str(packet)])

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

                    if self._is_duplicate_sync_message(message):
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
                    #     if self._is_duplicate_sync_message(message):
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

                    if message.distribution.global_time in tim and self._is_duplicate_sync_message(message):
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
                                if __debug__:
                                    self._statistics.outgoing(u"-sequence-", sum(len(packet) for packet in packets), len(packets))
                                self._endpoint.send([message.candidate], [str(packet) for packet in packets])

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

        # refuse messages where the global time is unreasonably high
        acceptable_global_time = meta.community.acceptable_global_time
        messages = [message if message.distribution.global_time <= acceptable_global_time else DropMessage(message, "global time is not within acceptable range") for message in messages]

        if isinstance(meta.authentication, MemberAuthentication):
            # a message is considered unique when (creator, global-time), i.r. (authentication.member,
            # distribution.global_time), is unique.  UNIQUE is used in the check_member_and_global_time
            # function
            unique = set()
            times = {}
            messages = [message if isinstance(message, DropMessage) else check_member_and_global_time(unique, times, message) for message in messages]

        # instead of storing HISTORY_SIZE messages for each authentication.member, we will store
        # HISTORY_SIZE messages for each combination of authentication.members.
        else:
            assert isinstance(meta.authentication, MultiMemberAuthentication)
            unique = set()
            times = {}
            messages = [message if isinstance(message, DropMessage) else check_multi_member_and_global_time(unique, times, message) for message in messages]

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
        messages = sorted(messages, lambda a, b: cmp(a.distribution.global_time, b.distribution.global_time) or cmp(a.packet, b.packet))

        # direct messages tell us what other people believe is the current global_time
        community = messages[0].community
        for message in messages:
            assert isinstance(message.candidate, Candidate)
            assert not isinstance(message.candidate, WalkCandidate)
            candidate = self.get_candidate(message.candidate.sock_addr)
            if candidate:
                candidate.set_global_time(community, message.distribution.global_time)

        return messages

    def get_candidate(self, sock_addr, replace=True, lan_address=("0.0.0.0", 0)):
        """
        Returns an existing candidate object or None

        1. returns an existing candidate from self._candidates, or

        2. returns a bootstrap candidate from self._bootstrap_candidates, or

        3. returns an existing candidate with the same host on a different port if this candidate is
           marked as a symmetric NAT.  When replace is True, the existing candidate is moved from
           its previous sock_addr to the new sock_addr.
        """
        # use existing (bootstrap) candidate
        candidate = self._candidates.get(sock_addr) or self._bootstrap_candidates.get(sock_addr)
        if __debug__: dprint("%s:%d" % sock_addr, " -> ", candidate)

        if candidate is None:
            # find matching candidate with the same host but a different port (symmetric NAT)
            for candidate in self._candidates.itervalues():
                if candidate.sock_addr[0] == sock_addr[0] and candidate.lan_address in (("0.0.0.0", 0), lan_address):
                    if __debug__: dprint("using existing candidate ", candidate, " at different port ", sock_addr[1], " (replace)" if replace else " (no replace)")

                    if replace:
                        # remove vote under previous key
                        self.wan_address_unvote(candidate)

                        # replace candidate
                        del self._candidates[candidate.sock_addr]
                        lan_address, wan_address = self._estimate_lan_and_wan_addresses(sock_addr, candidate.lan_address, candidate.wan_address)
                        candidate.sock_addr = sock_addr
                        candidate.update(candidate.tunnel, lan_address, wan_address, candidate.connection_type)
                        self._candidates[candidate.sock_addr] = candidate

                    break

            else:
                # no symmetric NAT candidate found
                candidate = None

        return candidate

    def create_candidate(self, sock_addr, tunnel, lan_address, wan_address, connection_type):
        """
        Creates and returns a new WalkCandidate instance.
        """
        assert not sock_addr in self._candidates
        assert isinstance(tunnel, bool)
        self._candidates[sock_addr] = candidate = WalkCandidate(sock_addr, tunnel, lan_address, wan_address, connection_type)
        if __debug__: dprint(candidate)
        return candidate

    def _filter_duplicate_candidate(self, candidate):
        """
        A node told us its LAN and WAN address, it is possible that we can now determine that we
        already have CANDIDATE in our candidate list.

        When we learn that a candidate happens to be behind a symmetric NAT we must remove all other
        candidates that have the same host.

        Unfortunately this only allows us to 'see' one peer behind a symmetric NAT, even though
        multiple peers may exist.
        """
        is_symmetric_nat = candidate.connection_type == u"symmetric-NAT"
        sock_addr = candidate.sock_addr
        lan_address = candidate.lan_address

        # find existing candidates that are likely to be the same candidate
        others = [other
                  for other
                  in self._candidates.itervalues()
                  if ((is_symmetric_nat or other.connection_type == u"symmetric-NAT") and
                      other.sock_addr[0] == sock_addr[0] and
                      other.lan_address == lan_address)]

        # merge and remove existing candidates in favor of the new CANDIDATE
        for other in others:
            # all except for the CANDIDATE
            if not other == candidate:
                if __debug__: dprint("removing ", other, " in favor or ", candidate)
                candidate.merge(other)
                del self._candidates[other.sock_addr]
                self.wan_address_unvote(other)

    def load_message(self, community, member, global_time, verify=False):
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

        # attempt conversion
        try:
            message = conversion.decode_message(LoopbackCandidate(), packet, verify)

        except (DropPacket, DelayPacket), exception:
            if __debug__: dprint("unable to convert a ", len(packet), " byte packet (", exception, ")", level="warning")
            return None

        message.packet_id = packet_id
        return message

    def convert_packet_to_meta_message(self, packet, community=None, load=True, auto_load=True):
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
            return conversion.decode_meta_message(packet)

        except (DropPacket, DelayPacket), exception:
            if __debug__: dprint("unable to convert a ", len(packet), " byte packet (", exception, ")", level="warning")
            return None

    def convert_packet_to_message(self, packet, community=None, load=True, auto_load=True, candidate=None, verify=True):
        """
        Returns the Message.Implementation representing the packet or None when no conversion is
        possible.
        """
        if __debug__:
            # pylint: disable-msg=W0404
            from community import Community
        assert isinstance(packet, str), type(packet)
        assert community is None or isinstance(community, Community), type(community)
        assert isinstance(load, bool), type(load)
        assert isinstance(auto_load, bool), type(auto_load)
        assert candidate is None or isinstance(candidate, Candidate), type(candidate)

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
            return conversion.decode_message(LoopbackCandidate() if candidate is None else candidate, packet, verify)

        except (DropPacket, DelayPacket), exception:
            if __debug__: dprint("unable to convert a ", len(packet), " byte packet (", exception, ")", level="warning")
            return None

    def convert_packets_to_messages(self, packets, community=None, load=True, auto_load=True, candidate=None):
        """
        Returns a list with messages representing each packet or None when no conversion is
        possible.
        """
        return [self.convert_packet_to_message(packet, community, load, auto_load, candidate) for packet in packets]

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
                    # batch exceeds maximum size, schedule first max_size immediately
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
        assert isinstance(timestamp, float)
        assert isinstance(batch, list)
        assert len(batch) > 0
        if __debug__:
            dprint("processing  ", len(batch), "x ", meta.name, " batched messages")

        if meta in self._batch_cache and id(self._batch_cache[meta][2]) == id(batch):
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
        # 21/03/12 Boudewijn: we can not filter all packets this way.  i.e. when multiple people
        # send us missing-identity messages some of them will be dropped
        #
        # def unique(batch):
        #     unique = set()
        #     for candidate, packet, conversion in batch:
        #         assert isinstance(packet, str)
        #         if packet in unique:
        #             if __debug__:
        #                 dprint("drop a ", len(packet), " byte packet (duplicate in batch) from ", candidate, level="warning")
        #                 self._statistics.drop("_convert_packets_into_batch:duplicate in batch", len(packet))
        #         else:
        #             unique.add(packet)
        #             yield candidate, packet, conversion

        # # remove duplicated
        # # todo: make _convert_batch_into_messages accept iterator instead of list to avoid conversion
        # batch = list(unique(batch))

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
                if __debug__:
                    dprint("delay a ", len(message.delayed.packet), " byte ", message.delayed.name, " (", message, ") from ", message.delayed.candidate)
                    self._statistics.delay("on_message_batch:%s" % message, len(message.delayed.packet))
                # try to extend an existing Trigger with the same pattern
                for trigger in self._triggers:
                    if isinstance(trigger, TriggerMessage) and trigger.extend(message.pattern, [message.delayed]):
                        if __debug__: dprint("extended an existing TriggerMessage")
                        break
                else:
                    # create a new Trigger with this pattern
                    trigger = TriggerMessage(message.pattern, self.on_messages, [message.delayed])
                    if __debug__:
                        dprint("created a new TriggeMessage")
                        self._statistics.outgoing(message.request.name, len(message.request.packet), 1)
                    self._endpoint.send([message.delayed.candidate], [message.request.packet])
                    self._triggers.append(trigger)
                    self._callback.register(trigger.on_timeout, delay=10.0, priority=TRIGGER_TIMEOUT_PRIORITY)
                return False

            elif isinstance(message, DropMessage):
                if __debug__:
                    dprint("drop: ", message.dropped.name, " (", message, ")", level="warning")
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
        messages = [message for message in messages if isinstance(message, Message.Implementation) or _filter_fail(message)]
        if not messages:
            return 0

        # check all remaining messages on the community side.  may yield Message.Implementation,
        # DropMessage, and DelayMessage instances
        try:
            messages = list(meta.check_callback(messages))
        except:
            dprint("exception during check_callback for ", meta.name, exception=True, level="error")
            return 0
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
        if __debug__:
            dprint("in... ", len(messages), " ", meta.name, " messages from ", ", ".join(str(candidate) for candidate in set(message.candidate for message in messages)))
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
            # find associated community
            try:
                community = self.get_community(packet[2:22])
            except KeyError:
                if __debug__:
                    dprint("drop a ", len(packet), " byte packet (received packet for unknown community) from ", candidate, level="warning")
                    self._statistics.drop("_convert_packets_into_batch:unknown community", len(packet))
                continue

            # find associated conversion
            try:
                conversion = community.get_conversion(packet[:22])
            except KeyError:
                if __debug__:
                    dprint("drop a ", len(packet), " byte packet (received packet for unknown conversion) from ", candidate, level="warning")
                    self._statistics.drop("_convert_packets_into_batch:unknown conversion", len(packet))
                continue

            try:
                # convert binary data into the meta message
                yield conversion.decode_meta_message(packet), candidate, packet, conversion

            except DropPacket, exception:
                if __debug__:
                    dprint("drop a ", len(packet), " byte packet (", exception,") from ", candidate, level="warning")
                    self._statistics.drop("_convert_packets_into_batch:decode_meta_message:%s" % exception, len(packet))

    def _convert_batch_into_messages(self, batch):
        if __debug__:
            # pylint: disable-msg=W0404
            from conversion import Conversion
        assert isinstance(batch, (list, set))
        assert len(batch) > 0
        assert all(isinstance(x, tuple) for x in batch)
        assert all(len(x) == 3 for x in batch)

        for candidate, packet, conversion in batch:
            assert isinstance(candidate, Candidate)
            assert isinstance(packet, str)
            assert isinstance(conversion, Conversion)

            try:
                # convert binary data to internal Message
                yield conversion.decode_message(candidate, packet)

            except DropPacket, exception:
                if __debug__:
                    dprint("drop a ", len(packet), " byte packet (", exception, ") from ", candidate, level="warning")
                    self._statistics.drop("_convert_batch_into_messages:%s" % exception, len(packet))

            except DelayPacketUsingIdentifier, delay:
                if __debug__:
                    dprint("delay a ", len(packet), " byte packet (", delay, ") from ", candidate)
                    self._statistics.delay("_convert_batch_into_messages:%s" % delay, len(packet))
                delay.create_request(candidate, packet)

            except DelayPacket, delay:
                if __debug__:
                    dprint("delay a ", len(packet), " byte packet (", delay, ") from ", candidate)
                    self._statistics.delay("_convert_batch_into_messages:%s" % delay, len(packet))

                # try to extend an existing Trigger with the same pattern
                for trigger in self._triggers:
                    if isinstance(trigger, TriggerPacket) and trigger.extend(delay.pattern, [(candidate, packet)]):
                        if __debug__: dprint("extended an existing TriggerPacket")
                        break
                else:
                    # create a new Trigger with this pattern
                    trigger = TriggerPacket(delay.pattern, self.on_incoming_packets, [(candidate, packet)])
                    if __debug__:
                        dprint("created a new TriggerPacket")
                        self._statistics.outgoing(u"-delay-packet-", len(delay.request.packet), 1)
                    self._endpoint.send([candidate], [delay.request.packet])
                    self._triggers.append(trigger)
                    self._callback.register(trigger.on_timeout, delay=10.0, priority=TRIGGER_TIMEOUT_PRIORITY)

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
        highest_global_time = 0

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

            # update global time
            highest_global_time = max(highest_global_time, message.distribution.global_time)

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

        # update the global time
        meta.community.update_global_time(highest_global_time)

        # if update_sync_range:
        #     # notify that global times have changed
        #     meta.community.update_sync_range(meta, update_sync_range)

    @property
    def candidates(self):
        return self._candidates.itervalues()

    def yield_subjective_candidates(self, community, cluster):
        """
        Yields unique active random candidates that are part of COMMUNITY and who have us in their
        subjective set CLUSTER.
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert isinstance(cluster, int)

        def in_subjective_set(candidate):
            for member in candidate.members:
                subjective_set = community.get_subjective_set(member, cluster)
                # TODO when we do not have a subjective_set from member, we should request it to
                # ensure that we make a valid decision next time
                if subjective_set and community.my_member.public_key in subjective_set:
                    return True
            return False

        now = time()
        candidates = [candidate
                      for candidate
                      in self._candidates.itervalues()
                      if candidate.in_community(community, now) and candidate.is_any_active(now) and in_subjective_set(candidate)]
        shuffle(candidates)
        return iter(candidates)

    def yield_random_candidates(self, community):
        """
        Yields unique active random candidates that are part of COMMUNITY.
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)
        assert all(not sock_address in self._candidates for sock_address in self._bootstrap_candidates.iterkeys()), "none of the bootstrap candidates may be in self._candidates"

        now = time()
        W = []
        S = []
        for candidate in self._candidates.itervalues():
            if candidate.in_community(community, now) and candidate.is_any_active(now):
                category = candidate.get_category(community, now)
                if category == u"walk":
                    W.append(candidate)
                elif category == u"stumble":
                    S.append(candidate)

        while W and S:
            yield W.pop(int(random() * len(W))) if random() <= .5 else S.pop(int(random() * len(S)))

        while W:
            yield W.pop(int(random() * len(W)))

        while S:
            yield S.pop(int(random() * len(S)))

    def yield_walk_candidates(self, community):
        """
        Yields a mixture of all candidates that we could get our hands on that are part of
        COMMUNITY.
        """
        if __debug__:
            from community import Community
        assert isinstance(community, Community)

        # TODO we can optimize by not doing all the sorting until we select where we want to pick a
        # node.  since we always just need one candidate the other sorts would be useless

        # 13/02/12 Boudewijn: normal peers can not be visited multiple times within 30 seconds,
        # bootstrap peers can not be visited multiple times within 55 seconds.  this is handled by
        # the Candidate.is_eligible_for_walk(...) method

        # TODO we can further optimize by not collecting the bootstrap_candidates until we need one
        # of those

        now = time()
        bootstrap_candidates = [candidate
                                for candidate
                                in self._bootstrap_candidates.itervalues()
                                if candidate.in_community(community, now) and candidate.is_eligible_for_walk(community, now)]
        shuffle(bootstrap_candidates)
        assert all(isinstance(candidate, WalkCandidate) for candidate in bootstrap_candidates)

        categories = {u"walk":[], u"stumble":[], u"intro":[], u"sandi":[], u"none":[]}
        for candidate in self._candidates.itervalues():
            if isinstance(candidate, WalkCandidate) and candidate.in_community(community, now) and candidate.is_eligible_for_walk(community, now):
                categories[candidate.get_category(community, now)].append(candidate)

        walks = sorted(categories[u"walk"], key=lambda candidate: candidate.last_walk(community))
        stumbles = sorted(categories[u"stumble"], key=lambda candidate: candidate.last_stumble(community))
        intros = sorted(categories[u"intro"], key=lambda candidate: candidate.last_intro(community))
        sandis = sorted(categories[u"sandi"], key=lambda candidate: min(candidate.last_stumble(community), candidate.last_intro(community)))

        while walks or stumbles or intros or sandis:
            r = random()

            # 13/02/12 Boudewijn: we decrease the 1% chance to contact a bootstrap peer to .5%
            if r <= .4975: # ~50%
                if walks:
                    if __debug__: dprint("yield [%2d:%2d:%2d:%2d:%2d walk   ] " % (len(walks), len(stumbles), len(intros), len(sandis), len(bootstrap_candidates)), walks[0])
                    yield walks.pop(0)

            elif r <= .995: # ~50%
                if stumbles or intros or sandis:
                    while True:
                        r = random()

                        if r <= .3333:
                            if stumbles:
                                if __debug__: dprint("yield [%2d:%2d:%2d:%2d:%2d stumble] " % (len(walks), len(stumbles), len(intros), len(sandis), len(bootstrap_candidates)), stumbles[0])
                                yield stumbles.pop(0)
                                break

                        elif r <= .6666:
                            if intros:
                                if __debug__: dprint("yield [%2d:%2d:%2d:%2d:%2d intro  ] " % (len(walks), len(stumbles), len(intros), len(sandis), len(bootstrap_candidates)), intros[0])
                                yield intros.pop(0)
                                break

                        elif r <= .9999:
                            if sandis:
                                if __debug__: dprint("yield [%2d:%2d:%2d:%2d:%2d sandi  ] " % (len(walks), len(stumbles), len(intros), len(sandis), len(bootstrap_candidates)), sandis[0])
                                yield sandis.pop(0)
                                break

            elif bootstrap_candidates: # ~.5%
                if __debug__: dprint("yield [%2d:%2d:%2d:%2d:%2d bootstr] " % (len(walks), len(stumbles), len(intros), len(sandis), len(bootstrap_candidates)), bootstrap_candidates[0])
                yield bootstrap_candidates.pop(0)

        while bootstrap_candidates:
            if __debug__: dprint("yield [%2d:%2d:%2d:%2d:%2d bootstr] (no regular candidates available)" % (len(walks), len(stumbles), len(intros), len(sandis), len(bootstrap_candidates)), bootstrap_candidates[0])
            yield bootstrap_candidates.pop(0)

        if __debug__: dprint("no candidates or bootstrap candidates available")

    def _estimate_lan_and_wan_addresses(self, sock_addr, lan_address, wan_address):
        """
        We received a message from SOCK_ADDR claiming to have LAN_ADDRESS and WAN_ADDRESS, returns
        the estimated LAN and WAN address for this node.

        The returned LAN address is either ("0.0.0.0", 0) or passes _is_valid_lan_address.
        Similarly, the returned WAN address is either ("0.0.0.0", 0) or passes
        _is_valid_wan_address.
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
            assert self._is_valid_lan_address(sock_addr), sock_addr
            assert self._is_valid_wan_address(wan_address), wan_address
            return sock_addr, wan_address

        elif self._is_valid_wan_address(sock_addr):
            # we have a different WAN address and the sock address is WAN, we are probably behind a different NAT
            if __debug__:
                if wan_address != sock_addr:
                    dprint("estimate a different WAN address ", wan_address[0], ":", wan_address[1], " -> ", sock_addr[0], ":", sock_addr[1])
            assert self._is_valid_lan_address(lan_address), lan_address
            assert self._is_valid_wan_address(sock_addr), sock_addr
            return lan_address, sock_addr

        elif self._is_valid_wan_address(wan_address):
            # we have a different WAN address and the sock address is not WAN, we are probably on the same computer
            assert self._is_valid_lan_address(lan_address), lan_address
            assert self._is_valid_wan_address(wan_address), wan_address
            return lan_address, wan_address

        else:
            # we are unable to determine the WAN address, we are probably behind the same NAT
            assert self._is_valid_lan_address(lan_address), lan_address
            return lan_address, ("0.0.0.0", 0)

    def take_step(self, community):
        if community.cid in self._communities:
            try:
                candidate = self.yield_walk_candidates(community).next()

            except StopIteration:
                if __debug__:
                    now = time()
                    dprint(community.cid.encode("HEX"), " ", community.get_classification(), " no candidate to take step")
                    for candidate in self._candidates.itervalues():
                        if candidate.in_community(community, now):
                            dprint(community.cid.encode("HEX"), " ", candidate.is_eligible_for_walk(community, now), " ", candidate, " ", candidate.get_category(community, now))

                return False

            else:
                assert community.my_member.private_key
                if __debug__: dprint(community.cid.encode("HEX"), " ", community.get_classification(), " taking step towards ", candidate)
                self.create_introduction_request(community, candidate)
                return True

    def handle_missing_messages(self, messages, cls):
        assert issubclass(cls, DelayedPacketCache)
        for message in messages:
            cache = self._request_cache.pop(cls.message_to_identifier(message), cls)
            if cache:
                if __debug__: dprint("found request cache for ", message, " [", cls.message_to_identifier(message), "]")
                for response_func, response_args in cache.callbacks:
                    response_func(message, *response_args)

            else:
                if __debug__:
                    dprint("no request cache found for ", message, " [", cls.message_to_identifier(message), "]")
                    for index, identifier in enumerate(self._request_cache._identifiers.iterkeys()):
                        dprint(index, "] ", identifier)

    def create_introduction_request(self, community, destination):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]

        self._statistics.increment_walk_attempt()
        destination.walk(community, time())

        # temporary cache object
        identifier = self._request_cache.claim(IntroductionRequestCache(community, destination))

        # decide if the requested node should introduce us to someone else
        # advice = random() < 0.5 or len(self._candidates) <= 5
        advice = True

        # obtain sync range
        if isinstance(destination, BootstrapCandidate):
            # do not request a sync when we connecting to a bootstrap candidate
            sync = None

        else:
            # flush any sync-able items left in the cache before we create a sync
            flush_list = [(meta, tup) for meta, tup in self._batch_cache.iteritems() if meta.community == community and isinstance(meta.distribution, SyncDistribution)]
            flush_list.sort(key=lambda tup: tup[0].batch.priority, reverse=True)
            for meta, (task_identifier, timestamp, batch) in flush_list:
                if __debug__: dprint("flush cached ", len(batch), "x ", meta.name, " messages (id: ", task_identifier, ")")
                self._callback.unregister(task_identifier)
                self._on_batch_cache_timeout(meta, timestamp, batch)

            sync = community.dispersy_claim_sync_bloom_filter(identifier)
            if __debug__:
                assert sync is None or isinstance(sync, tuple), sync
                if not sync is None:
                    assert len(sync) == 5, sync
                    time_low, time_high, modulo, offset, bloom_filter = sync
                    assert isinstance(time_low, (int, long)), time_low
                    assert isinstance(time_high, (int, long)), time_high
                    assert isinstance(modulo, int), modulo
                    assert isinstance(offset, int), offset
                    assert isinstance(bloom_filter, BloomFilter), bloom_filter

                    # verify that the bloom filter is correct
                    binary = bloom_filter.bytes
                    bloom_filter.clear()
                    try:
                        packets = [str(packet) for packet, in self._database.execute(u"SELECT sync.packet FROM sync JOIN meta_message ON meta_message.id = sync.meta_message WHERE sync.community = ? AND meta_message.priority > 32 AND sync.undone == 0 AND global_time BETWEEN ? AND ? AND (sync.global_time + ?) % ? = 0",
                                                                                     (community.database_id, time_low, community.global_time if time_high == 0 else time_high, offset, modulo))]
                    except OverflowError:
                        dprint("time_low:  ", time_low, level="error")
                        dprint("time_high: ", time_high, level="error")
                        dprint("2**63 - 1: ", 2**63 - 1, level="error")
                        dprint("the sqlite3 python module can not handle values 2**63 or larger.  limit time_low and time_high to 2**63-1", exception=True, level="error")
                        assert False

                    bloom_filter.add_keys(packets)
                    assert binary == bloom_filter.bytes, "The returned bloom filter does not match the given range [%d:%d] packets:%d" % (time_low, time_high, len(packets))

        if __debug__:
            if destination.get_destination_address(self._wan_address) != destination.sock_addr:
                dprint("destination address, ", destination.get_destination_address(self._wan_address), " should (in theory) be the sock_addr ", destination, level="warning")

        meta_request = community.get_meta_message(u"dispersy-introduction-request")
        request = meta_request.impl(authentication=(community.my_member,),
                                    distribution=(community.global_time,),
                                    destination=(destination,),
                                    payload=(destination.get_destination_address(self._wan_address), self._lan_address, self._wan_address, advice, self._connection_type, sync, identifier))

        if __debug__:
            if sync:
                dprint(community.cid.encode("HEX"), " sending introduction request to ", destination, " [", sync[0], ":", sync[1], "] %", sync[2], "+", sync[3])
            else:
                dprint(community.cid.encode("HEX"), " sending introduction request to ", destination)
        self.store_update_forward([request], False, False, True)
        return request

    def check_introduction_request(self, messages):
        """
        We received a dispersy-introduction-request message.
        """
        for message in messages:
            if messages[0].community.dispersy_subjective_set_enabled:
                # all currently known sets
                subjective_sets = message.community.get_subjective_sets(message.authentication.member)

                # find messages that require subjective sets
                for meta in messages[0].community.get_meta_messages():
                    if (isinstance(meta.destination, SubjectiveDestination) and
                        isinstance(meta.distribution, SyncDistribution) and
                        meta.distribution.priority > 32):

                        # we need the subjective set for this particular cluster
                        assert meta.destination.cluster in subjective_sets, "subjective_sets must contain all existing clusters, however, some may be None"
                        if not subjective_sets.get(meta.destination.cluster):
                            if __debug__: dprint("subjective set not available (not ", meta.destination.cluster, " in ", subjective_sets.keys(), ")")
                            yield DelayMessageBySubjectiveSet(message, meta.destination.cluster)
                            has_been_delayed = True
                            break

                else:
                    # did not break
                    has_been_delayed = False

                if has_been_delayed:
                    continue

            # 25/01/12 Boudewijn: during all DAS2 NAT node314 often sends requests to herself.  This
            # results in more candidates (all pointing to herself) being added to the candidate
            # list.  This converges to only sending requests to herself.  To prevent this we will
            # drop all requests that have an outstanding identifier.  This is not a perfect
            # solution, but the change that two nodes select the same identifier and send requests
            # to each other is relatively small.
            if self._request_cache.has(message.payload.identifier, IntroductionRequestCache):
                if __debug__: dprint("dropping dispersy-introduction-request, this identifier is already in use.")
                yield DropMessage(message, "Duplicate identifier (most likely received from ourself)")
                continue

            if __debug__: dprint("accepting dispersy-introduction-request from ", message.candidate)
            yield message

    def on_introduction_request(self, messages):
        def is_valid_candidate(message, introduced):
            assert isinstance(introduced, WalkCandidate)
            assert self._is_valid_lan_address(introduced.lan_address), introduced.lan_address
            assert self._is_valid_wan_address(introduced.wan_address), introduced.wan_address

            # # we can only use WalkCandidates
            # if not isinstance(candidate, WalkCandidate):
            #     return False

            if message.candidate.sock_addr == introduced.wan_address:
                # must not introduce someone to herself
                return False

            if message.payload.connection_type == u"symmetric-NAT" and introduced.connection_type == u"symmetric-NAT":
                # must not introduce two symmetric NAT nodes to each other
                return False

            return True

        #
        # process the walker part of the request
        #

        community = messages[0].community
        meta_introduction_response = community.get_meta_message(u"dispersy-introduction-response")
        meta_puncture_request = community.get_meta_message(u"dispersy-puncture-request")
        responses = []
        requests = []
        now = time()

        random_candidate_iterator = self.yield_random_candidates(community)
        random_candidate_stack = []

        for message in messages:
            payload = message.payload

            # modify either the senders LAN or WAN address based on how we perceive that node
            source_lan_address, source_wan_address = self._estimate_lan_and_wan_addresses(message.candidate.sock_addr, payload.source_lan_address, payload.source_wan_address)

            # get or create WalkCandidate from Candidate
            assert isinstance(message.candidate, Candidate)
            assert not isinstance(message.candidate, WalkCandidate)
            candidate = self.get_candidate(message.candidate.sock_addr) or self.create_candidate(message.candidate.sock_addr, message.candidate.tunnel, source_lan_address, source_wan_address, payload.connection_type)

            # apply vote to determine our WAN address
            self.wan_address_vote(payload.destination_address, candidate)

            # until we implement a proper 3-way handshake we are going to assume that the creator of
            # this message is associated to this candidate
            candidate.associate(community, message.authentication.member)

            # update sender candidate
            candidate.update(candidate.tunnel, source_lan_address, source_wan_address, payload.connection_type)
            candidate.stumble(community, now)
            # candidate.active(community, now)
            self._filter_duplicate_candidate(candidate)
            if __debug__: dprint("received introduction request from ", candidate)

            if source_wan_address == ("0.0.0.0", 0):
                if __debug__: dprint("problems determining source WAN address, unable to introduce")
                introduced = None

            elif payload.advice:
                for introduced in random_candidate_iterator:
                    if is_valid_candidate(message, introduced):
                        # found candidate, break
                        break

                    else:
                        random_candidate_stack.append(introduced)

                else:
                    # did not break, no candidate found in iterator.  try the stack
                    for index, introduced in enumerate(random_candidate_stack):
                        if is_valid_candidate(message, introduced):
                            # found candidate, break
                            del random_candidate_stack[index]
                            break

                    else:
                        # did not break, no candidate found
                        introduced = None

            else:
                if __debug__: dprint("no candidates available to introduce")
                introduced = None

            if introduced:
                if __debug__: dprint("telling ", candidate, " that ", introduced, " exists")

                # create introduction response
                responses.append(meta_introduction_response.impl(authentication=(community.my_member,), distribution=(community.global_time,), destination=(candidate,), payload=(candidate.get_destination_address(self._wan_address), self._lan_address, self._wan_address, introduced.lan_address, introduced.wan_address, self._connection_type, introduced.tunnel, payload.identifier)))

                # create puncture request
                requests.append(meta_puncture_request.impl(distribution=(community.global_time,), destination=(introduced,), payload=(source_lan_address, source_wan_address, payload.identifier)))

            else:
                if __debug__: dprint("responding to ", candidate, " without an introduction")

                none = ("0.0.0.0", 0)
                responses.append(meta_introduction_response.impl(authentication=(community.my_member,), distribution=(community.global_time,), destination=(candidate,), payload=(candidate.get_destination_address(self._wan_address), self._lan_address, self._wan_address, none, none, self._connection_type, False, payload.identifier)))

        if responses:
            self._forward(responses)
        if requests:
            self._forward(requests)

        #
        # process the bloom filter part of the request
        #

        # obtain all available messages for this community
        syncable_messages = u", ".join(unicode(meta.database_id) for meta in community.get_meta_messages() if isinstance(meta.distribution, SyncDistribution) and meta.distribution.priority > 32)

        if community.dispersy_subjective_set_enabled:
            sql = u"""SELECT sync.packet, sync.meta_message, member.public_key
FROM sync
JOIN member ON member.id = sync.member
JOIN meta_message ON meta_message.id = sync.meta_message
WHERE sync.meta_message IN (%s) AND sync.undone = 0 AND sync.global_time BETWEEN ? AND ? AND (sync.global_time + ?) %% ? = 0
ORDER BY meta_message.priority DESC, sync.global_time * meta_message.direction""" % syncable_messages
            meta_messages = dict((meta_message.database_id, meta_message) for meta_message in community.get_meta_messages())
            if __debug__: dprint(sql)

            for message in messages:
                payload = message.payload

                if payload.sync:
                    # obtain all subjective sets for the sender of the dispersy-sync message
                    assert isinstance(message.authentication, MemberAuthentication.Implementation)
                    subjective_sets = community.get_subjective_sets(message.authentication.member)

                    # we limit the response by byte_limit bytes
                    byte_limit = community.dispersy_sync_response_limit

                    time_high = payload.time_high if payload.has_time_high else community.global_time
                    packets = []

                    # 07/05/12 Boudewijn: for an unknown reason values larger than 2^63-1 cause
                    # overflow exceptions in the sqlite3 wrapper
                    time_low = min(payload.time_low, 2**63-1)
                    time_high = min(time_high, 2**63-1)

                    generator = ((str(packet), meta_message_id, str(packet_public_key)) for packet, meta_message_id, packet_public_key in self._database.execute(sql, (time_low, time_high, payload.offset, payload.modulo)))
                    for packet, meta_message_id, packet_public_key in payload.bloom_filter.not_filter(generator):
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
                            assert subjective_set, "subjective_set must be available (i.e. not None), see check_introduction_request"

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
                        if __debug__:
                            dprint("syncing ", len(packets), " packets (", sum(len(packet) for packet in packets), " bytes) over [", time_low, ":", time_high, "] selecting (%", payload.modulo, "+", payload.offset, ") to " , message.candidate)
                            self._statistics.outgoing(u"-sync-", sum(len(packet) for packet in packets), len(packets))
                        self._endpoint.send([message.candidate], packets)

        else:
            sql = u"""SELECT sync.packet
FROM sync
JOIN meta_message ON meta_message.id = sync.meta_message
WHERE sync.meta_message IN (%s) AND sync.undone = 0 AND sync.global_time BETWEEN ? AND ? AND (sync.global_time + ?) %% ? = 0
ORDER BY meta_message.priority DESC, sync.global_time * meta_message.direction""" % syncable_messages
            if __debug__: dprint(sql)

            for message in messages:
                payload = message.payload

                if payload.sync:
                    # we limit the response by byte_limit bytes
                    byte_limit = community.dispersy_sync_response_limit

                    time_high = payload.time_high if payload.has_time_high else community.global_time

                    # 07/05/12 Boudewijn: for an unknown reason values larger than 2^63-1 cause
                    # overflow exceptions in the sqlite3 wrapper
                    time_low = min(payload.time_low, 2**63-1)
                    time_high = min(time_high, 2**63-1)

                    packets = []

                    generator = ((str(packet),) for packet, in self._database.execute(sql, (time_low, long(time_high), long(payload.offset), long(payload.modulo))))
                    for packet, in payload.bloom_filter.not_filter(generator):
                        if __debug__:dprint("found missing (", len(packet), " bytes) ", sha1(packet).digest().encode("HEX"))

                        packets.append(packet)
                        byte_limit -= len(packet)
                        if byte_limit <= 0:
                            if __debug__:
                                dprint("bandwidth throttle")
                            break

                    if packets:
                        if __debug__:
                            dprint("syncing ", len(packets), " packets (", sum(len(packet) for packet in packets), " bytes) over [", time_low, ":", time_high, "] selecting (%", message.payload.modulo, "+", message.payload.offset, ") to " , message.candidate)
                            self._statistics.outgoing(u"-sync-", sum(len(packet) for packet in packets), len(packets))
                        self._endpoint.send([message.candidate], packets)

    def check_introduction_response(self, messages):
        for message in messages:
            if __debug__:
                cache = self._request_cache.get(message.payload.identifier, IntroductionRequestCache)
                if cache and cache.timeout_occurred:
                    yield DropMessage(message, "invalid response identifier from %s, timeout occurred.  requested %.2fs ago" % (str(message.candidate), time() - cache.request_time))
                    continue
                if not cache:
                    yield DropMessage(message, "invalid response identifier")
                    continue
            else:
                if not self._request_cache.has(message.payload.identifier, IntroductionRequestCache):
                    yield DropMessage(message, "invalid response identifier")
                    continue

            # check introduced LAN address, if given
            if not message.payload.lan_introduction_address == ("0.0.0.0", 0):
                if not self._is_valid_lan_address(message.payload.lan_introduction_address):
                    yield DropMessage(message, "invalid LAN introduction address [_is_valid_lan_address]")
                    continue

                if message.payload.lan_introduction_address == message.candidate.sock_addr:
                    yield DropMessage(message, "invalid LAN introduction address [introducing herself]")
                    continue

                if message.payload.lan_introduction_address == self._lan_address:
                    yield DropMessage(message, "invalid LAN introduction address [introducing myself]")
                    continue

                if message.payload.lan_introduction_address in self._bootstrap_candidates:
                    yield DropMessage(message, "invalid LAN introduction address [introducing bootstrap node]")
                    continue

            # check introduced WAN address, if given
            if not message.payload.wan_introduction_address == ("0.0.0.0", 0):
                if not self._is_valid_wan_address(message.payload.wan_introduction_address):
                    yield DropMessage(message, "invalid WAN introduction address [_is_valid_wan_address]")
                    continue

                if message.payload.wan_introduction_address == message.candidate.sock_addr:
                    yield DropMessage(message, "invalid WAN introduction address [introducing herself]")
                    continue

                if message.payload.wan_introduction_address == self._wan_address:
                    yield DropMessage(message, "invalid WAN introduction address [introducing myself]")
                    continue

                if message.payload.wan_introduction_address in self._bootstrap_candidates:
                    yield DropMessage(message, "invalid WAN introduction address [introducing bootstrap node]")
                    continue

            yield message

    def on_introduction_response(self, messages):
        community = messages[0].community
        now = time()

        for message in messages:
            payload = message.payload

            # modify either the senders LAN or WAN address based on how we perceive that node
            source_lan_address, source_wan_address = self._estimate_lan_and_wan_addresses(message.candidate.sock_addr, payload.source_lan_address, payload.source_wan_address)

            # get or create WalkCandidate from Candidate
            assert isinstance(message.candidate, Candidate)
            assert not isinstance(message.candidate, WalkCandidate)
            candidate = self.get_candidate(message.candidate.sock_addr)
            if candidate is None:
                candidate = self.create_candidate(message.candidate.sock_addr, message.candidate.tunnel, source_lan_address, source_wan_address, payload.connection_type)
            else:
                candidate.update(candidate.tunnel, source_lan_address, source_wan_address, payload.connection_type)

            # until we implement a proper 3-way handshake we are going to assume that the creator of
            # this message is associated to this candidate
            candidate.associate(community, message.authentication.member)
            # candidate.active(community, now)
            self._filter_duplicate_candidate(candidate)
            if __debug__: dprint("introduction response from ", candidate)

            # apply vote to determine our WAN address
            self.wan_address_vote(payload.destination_address, candidate)

            # increment statistics only the first time
            self._statistics.increment_walk_success()

            # get cache object linked to this request and stop timeout from occurring
            cache = self._request_cache.pop(payload.identifier, IntroductionRequestCache)

            # handle the introduction
            lan_introduction_address = payload.lan_introduction_address
            wan_introduction_address = payload.wan_introduction_address
            if not (lan_introduction_address == ("0.0.0.0", 0) or wan_introduction_address == ("0.0.0.0", 0)):
                assert self._is_valid_lan_address(lan_introduction_address), lan_introduction_address
                assert self._is_valid_wan_address(wan_introduction_address), wan_introduction_address

                # get or create the introduced candidate
                sock_introduction_addr = lan_introduction_address if wan_introduction_address[0] == self._wan_address[0] else wan_introduction_address
                candidate = self.get_candidate(sock_introduction_addr, replace=False, lan_address=lan_introduction_address)
                if candidate is None:
                    # create candidate but set its state to inactive to ensure that it will not be
                    # used.  note that we call candidate.intro to allow the candidate to be returned
                    # by yield_walk_candidates
                    candidate = self.create_candidate(sock_introduction_addr, payload.tunnel, lan_introduction_address, wan_introduction_address, u"unknown")
                    candidate.inactive(community, now)

                # reset the 'I have been introduced' timer
                candidate.intro(community, now)
                if __debug__: dprint("received introduction to ", candidate)

                cache.response_candidate = candidate

    def check_puncture_request(self, messages):
        for message in messages:
            if message.payload.lan_walker_address == message.candidate.sock_addr:
                yield DropMessage(message, "invalid LAN walker address [puncture herself]")
                continue

            if not self._is_valid_lan_address(message.payload.lan_walker_address):
                yield DropMessage(message, "invalid LAN walker address [_is_valid_lan_address]")
                continue

            if message.payload.wan_walker_address == message.candidate.sock_addr:
                yield DropMessage(message, "invalid WAN walker address [puncture herself]")
                continue

            if not self._is_valid_wan_address(message.payload.wan_walker_address):
                yield DropMessage(message, "invalid WAN walker address [_is_valid_wan_address]")
                continue

            yield message

    def on_puncture_request(self, messages):
        community = messages[0].community
        meta_puncture = community.get_meta_message(u"dispersy-puncture")
        punctures = []
        for message in messages:
            lan_walker_address = message.payload.lan_walker_address
            wan_walker_address = message.payload.wan_walker_address
            assert self._is_valid_lan_address(lan_walker_address), lan_walker_address
            assert self._is_valid_wan_address(wan_walker_address), wan_walker_address

            # we are asked to send a message to a -possibly- unknown peer get the actual candidate
            # or create a dummy candidate
            sock_addr = lan_walker_address if wan_walker_address[0] == self._wan_address[0] else wan_walker_address
            candidate = self.get_candidate(sock_addr, replace=False, lan_address=lan_walker_address)
            if candidate is None:
                # assume that tunnel is disabled
                tunnel = False
                candidate = Candidate(sock_addr, tunnel)

            punctures.append(meta_puncture.impl(authentication=(community.my_member,), distribution=(community.global_time,), destination=(candidate,), payload=(self._lan_address, self._wan_address, message.payload.identifier)))
            if __debug__: dprint(message.candidate, " asked us to send a puncture to ", candidate)

        self.store_update_forward(punctures, False, False, True)

    def check_puncture(self, messages):
        for message in messages:
            if not self._request_cache.has(message.payload.identifier, IntroductionRequestCache):
                yield DropMessage(message, "invalid response identifier")
                continue

            yield message

    def on_puncture(self, messages):
        community = messages[0].community
        now = time()

        for message in messages:
            # get cache object linked to this request but does NOT stop timeout from occurring
            cache = self._request_cache.get(message.payload.identifier, IntroductionRequestCache)

            # when the sender is behind a symmetric NAT and we are not, we will not be able to get
            # through using the port that the helper node gave us (symmetric NAT will give a
            # different port for each destination address).

            # we can match this source address (message.candidate.sock_addr) to the candidate and
            # modify the LAN or WAN address that has been proposed.
            sock_addr = message.candidate.sock_addr
            lan_address, wan_address = self._estimate_lan_and_wan_addresses(sock_addr, message.payload.source_lan_address, message.payload.source_wan_address)

            if not (lan_address == ("0.0.0.0", 0) or wan_address == ("0.0.0.0", 0)):
                assert self._is_valid_lan_address(lan_address), lan_address
                assert self._is_valid_wan_address(wan_address), wan_address

                # get or create the introduced candidate
                candidate = self.get_candidate(sock_addr, replace=True, lan_address=lan_address)
                if candidate is None:
                    # create candidate but set its state to inactive to ensure that it will not be
                    # used.  note that we call candidate.intro to allow the candidate to be returned
                    # by yield_walk_candidates
                    candidate = self.create_candidate(sock_addr, message.candidate.tunnel, lan_address, wan_address, u"unknown")
                    candidate.inactive(community, now)

                else:
                    # update candidate
                    candidate.update(message.candidate.tunnel, lan_address, wan_address, u"unknown")

                # reset the 'I have been introduced' timer
                candidate.intro(community, now)
                if __debug__: dprint("received introduction to ", candidate)

                cache.puncture_candidate = candidate

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
            if __debug__:
                begin = time()
            try:
                messages[0].handle_callback(messages)
            except:
                dprint("exception during handle_callback for ", messages[0].name, exception=True, level="error")
                return False
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
            if not self._forward(messages):
                return False

        return True

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
                if __debug__:
                    # note that the statistics is different from the truth when less than NODE_COUNT
                    # candidates can be found
                    self._statistics.outgoing(meta.name, sum(len(message.packet) for message in messages) * meta.destination.node_count, len(messages) * meta.destination.node_count)
                return all(self._endpoint.send(list(islice(self.yield_random_candidates(meta.community), meta.destination.node_count)), [message.packet]) for message in messages)

        elif isinstance(meta.destination, SubjectiveDestination):
            # SubjectiveDestination.node_count is allowed to be zero
            if meta.destination.node_count > 0:
                if __debug__:
                    # note that the statistics is different from the truth when less than NODE_COUNT
                    # candidates can be found
                    self._statistics.outgoing(meta.name, sum(len(message.packet) for message in messages) * meta.destination.node_count, len(messages) * meta.destination.node_count)
                return all(self._endpoint.send(list(islice(self.yield_subjective_candidates(meta.community, meta.destination.cluster), meta.destination.node_count)), [message.packet]) for message in messages)

        elif isinstance(meta.destination, CandidateDestination):
            # CandidateDestination.candidates may be empty
            if __debug__:
                self._statistics.outgoing(meta.name, sum(len(message.packet) for message in messages) * sum(len(message.destination.candidates) for message in messages), sum(len(message.destination.candidates) for message in messages))
            return all(self._endpoint.send(message.destination.candidates, [message.packet]) for message in messages if message.destination.candidates)

        elif isinstance(meta.destination, MemberDestination):
            # MemberDestination.candidates may be empty
            # TODO add the _statistics.outgoing information
            return all(self._endpoint.send([candidate
                                            for candidate
                                            in self._candidates.itervalues()
                                            if any(candidate.is_associated(message.community, member)
                                                   for member
                                                   in message.destination.members)],
                                           [message.packet])
                       for message
                       in messages)

        else:
            raise NotImplementedError(meta.destination)

        return False

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
        return self._callback.register(trigger.on_timeout, delay=timeout, priority=TRIGGER_TIMEOUT_PRIORITY)

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
            if __debug__:
                self._statistics.outgoing(u"-malicious-proof", sum(len(packet) for packet in packets), len(packets))
            self._endpoint.send([candidate], packets)

    def create_missing_message(self, community, candidate, member, global_time, response_func=None, response_args=(), timeout=10.0, forward=True):
        """
        Create a dispersy-missing-message message.

        Each sync message in dispersy can be uniquely identified using the community identifier,
        member identifier, and global time.  This message requests a unique dispersy message from
        another peer.

        If the peer at CANDIDATE (1) receives the request, (2) has the requested message, and (3) is
        willing to upload, the optional RESPONSE_FUNC will be called.  Note that if there is a
        callback for the requested message, that will always be called regardless of RESPONSE_FUNC.

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
            assert response_func is None or callable(response_func)
            assert isinstance(response_args, tuple)
            assert isinstance(timeout, float)
            assert timeout > 0.0
            assert isinstance(forward, bool)
            dprint("DEPRECATED, use create_missing_message_newstyle instead.  Remember to add call to dispersy.handle_missing_messages", level="warning")

        meta = community.get_meta_message(u"dispersy-missing-message")
        request = meta.impl(distribution=(community.global_time,), destination=(candidate,), payload=(member, [global_time]))

        if response_func:
            # generate footprint
            footprint = "".join(("Community:", community.cid.encode("HEX"),
                                 "\s", "(MemberAuthentication:", member.mid.encode("HEX"), "|MultiMemberAuthentication:[^\s]*", member.mid.encode("HEX"), "[^\s]*)",
                                 "\s", "Resolution",
                                 "\s", "((Relay|Direct|)Distribution:", str(global_time), "|FullSyncDistribution:", str(global_time), ",[0-9]+)"))
            self.await_message(footprint, response_func, response_args, timeout, 1)

        if forward:
            self._forward([request])
        return request

    def create_missing_message_newstyle(self, community, candidate, member, global_time, response_func=None, response_args=(), timeout=10.0):
        # ensure that the identifier is 'triggered' somewhere

        identifier = MissingMessageCache.properties_to_identifier(community, member, global_time)
        cache = self._request_cache.get(identifier, MissingMessageCache)
        if not cache:
            if __debug__: dprint(identifier)
            cache = MissingMessageCache(timeout)
            self._request_cache.set(identifier, cache)

            meta = community.get_meta_message(u"dispersy-missing-message")
            request = meta.impl(distribution=(community.global_time,), destination=(candidate,), payload=(member, [global_time]))
            self._forward([request])

        cache.callbacks.append((response_func, response_args))

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
                    responses.append((candidate, str(packet)))

        for candidate, responses in groupby(responses, key=lambda tup: tup[0]):
            if __debug__:
                # responses is an iterator, for __debug__ we need a list
                responses = list(responses)
                self._statistics.outgoing(u"-missing-message", sum(len(packet) for packet in responses), len(responses))
            self._endpoint.send([candidate], [packet for _, packet in responses])

    def create_missing_last_message(self, community, candidate, member, message, count_, response_func=None, response_args=(), timeout=10.0):
        if __debug__:
            # pylint: disable-msg=W0404
            from community import Community
            assert isinstance(community, Community)
            assert isinstance(candidate, Candidate)
            assert isinstance(member, Member)
            assert isinstance(message, Message)
            assert isinstance(count_, int)
            assert response_func is None or callable(response_func)
            assert isinstance(response_args, tuple)
            assert isinstance(timeout, float)
            assert timeout > 0.0

        identifier = MissingLastMessageCache.properties_to_identifier(community, member, message)
        cache = self._request_cache.get(identifier, MissingLastMessageCache)
        if not cache:
            cache = MissingLastMessageCache(timeout)
            self._request_cache.set(identifier, cache)

            meta = community.get_meta_message(u"dispersy-missing-last-message")
            request = meta.impl(distribution=(community.global_time,), destination=(candidate,), payload=(member, message, count_))
            self._forward([request])

        cache.callbacks.append((response_func, response_args))

    def on_missing_last_message(self, messages):
        for message in messages:
            payload = message.payload
            packets = [str(packet) for packet, in list(self._database.execute(u"SELECT packet FROM sync WHERE community = ? AND member = ? AND meta_message = ? ORDER BY global_time DESC LIMIT ?",
                                                                              (message.community.database_id, payload.member.database_id, payload.message.database_id, payload.count)))]
            self._endpoint.send([message.candidate], packets)

    def _is_valid_lan_address(self, address, check_my_lan_address=True):
        """
        TODO we should rename _is_valid_lan_address to _is_valid_address as the way it is used now
        things will fail if it only accepted LAN domain addresses (10.xxx.yyy.zzz, etc.)
        """
        assert isinstance(address, tuple), type(address)
        assert len(address) == 2, len(address)
        assert isinstance(address[0], str), type(address[0])
        assert isinstance(address[1], int), type(address[1])

        if address[0] == "":
            return False

        if address[0] == "0.0.0.0":
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
        assert isinstance(address, tuple), type(address)
        assert len(address) == 2, len(address)
        assert isinstance(address[0], str), type(address[0])
        assert isinstance(address[1], int), type(address[1])

        if address[0] == "":
            return False

        if address[0] == "0.0.0.0":
            return False

        if address[1] <= 0:
            return False

        try:
            binary = inet_aton(address[0])
        except socket_error:
            return False

        # # ending with .0
        # if binary[3] == "\x00":
        #     return False

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

        # 13/03/12 Boudewijn: currently create_identity is either called when joining or creating a
        # community.  when creating a community self._global_time should be 1, since the master
        # member dispersy-identity message has just been created.  when joining a community
        # self._global time should be 0, since no messages have been either received or created.
        #
        # as a security feature we force that the global time on dispersy-identity messages are
        # always 2 or higher (except for master members who should get global time 1)
        global_time = community.claim_global_time()
        while global_time < 2:
            global_time = community.claim_global_time()

        message = meta.impl(authentication=(community.my_member,), distribution=(global_time,))
        assert message.distribution.global_time == 2, [global_time, message.distribution.global_time, community.global_time, community.database_id]
        self.store_update_forward([message], store, update, False)
        return message

    def on_identity(self, messages):
        """
        We received a dispersy-identity message.
        """
        for message in messages:
            # get cache object linked to this request and stop timeout from occurring
            identifier = MissingMemberCache.message_to_identifier(message)
            cache = self._request_cache.pop(identifier, MissingMemberCache)
            if cache:
                for func, args in cache.callbacks:
                    func(message, *args)

    def create_missing_identity(self, community, candidate, dummy_member, response_func=None, response_args=(), timeout=4.5, forward=True):
        """
        Create a dispersy-missing-identity message.

        To verify a message signature we need the corresponding public key from the member who made
        the signature.  When we are missing a public key, we can request a dispersy-identity message
        which contains this public key.
        """
        if __debug__:
            # pylint: disable-msg=W0404
            from community import Community
            assert isinstance(community, Community)
            assert isinstance(candidate, Candidate)
            assert isinstance(dummy_member, DummyMember)
            assert not dummy_member.public_key
            assert response_func is None or callable(response_func)
            assert isinstance(response_args, tuple)
            assert isinstance(timeout, float)
            assert isinstance(forward, bool)

        identifier = MissingMemberCache.properties_to_identifier(community, dummy_member)
        cache = self._request_cache.get(identifier, MissingMemberCache)
        if not cache:
            # cache = MissingMemberRequestCache(community)
            cache = MissingMemberCache(timeout)
            self._request_cache.set(identifier, cache)

            meta = community.get_meta_message(u"dispersy-missing-identity")
            request = meta.impl(distribution=(community.global_time,), destination=(candidate,), payload=(dummy_member.mid,))
            self._forward([request])

        cache.callbacks.append((response_func, response_args))

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
                if __debug__:
                    dprint("responding with ", len(packets), " identity messages")
                    self._statistics.outgoing(u"-dispersy-identity", sum(len(packet) for packet in packets), len(packets))
                self._endpoint.send([message.candidate], packets)

            else:
                assert not message.payload.mid == message.community.my_member.mid, "we should always have our own dispersy-identity"
                if __debug__: dprint("could not find any missing members.  no response is sent [", message.payload.mid.encode("HEX"), ", mid:", message.community.my_member.mid.encode("HEX"), ", cid:", message.community.cid.encode("HEX"), "]", level="warning")

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
                if __debug__:
                    self._statistics.outgoing(u"-dispersy-subjective-set", sum(len(packet) for packet in packets), len(packets))
                self._endpoint.send([message.candidate], packets)

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
    #         assert community.timeline.check(message)
    #         message.handle_callback(("", -1), message)

    #     if store_and_forward:
    #         self.store_and_forward([message])

    #     return message

    def create_signature_request(self, community, message, response_func, response_args=(), timeout=10.0, store=True, forward=True):
        """
        Create a dispersy-signature-request message.

        The dispersy-signature-request message contains a sub-message that is to be signed by
        multiple members.  The sub-message must use the MultiMemberAuthentication policy in order to
        store the multiple members and their signatures.

        Typically, each member that should add a signature will receive the
        dispersy-signature-request message.  If they choose to add their signature, a
        dispersy-signature-response message is send back.  This in turn will result in a call to
        RESPONSE_FUNC.

        Each dispersy-signed-response message will result in one call to RESPONSE_FUNC.  The first
        parameter for this call is MESSAGE, the second parameter is the proposed message that was
        send back, the third parameter is a boolean indicating that MESSAGE was modified.

        RESPONSE_FUNC must return three boolean values, each indicates weather the proposed message
        (the second parameter) must be stored, updated, or forwarded, respectively.  If any of these
        boolean values is True we will sign the proposed message with our own signature.

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

        # temporary cache object
        cache = SignatureRequestCache(members, response_func, response_args, timeout)
        identifier = self._request_cache.claim(cache)

        # the dispersy-signature-request message that will hold the
        # message that should obtain more signatures
        meta = community.get_meta_message(u"dispersy-signature-request")
        cache.request = meta.impl(distribution=(community.global_time,),
                                  destination=tuple(members),
                                  payload=(identifier, message))

        if __debug__: dprint("asking ", ", ".join(member.mid.encode("HEX") for member in members))
        self.store_update_forward([cache.request], store, False, forward)
        return cache.request

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
            # # if not message.community.timeline.check(submsg):
            # #     raise DropMessage("Does not fit timeline")

            # allow message
            yield message

    def on_signature_request(self, messages):
        """
        We received a dispersy-signature-request message.

        This message contains a sub-message (message.payload.message) that the message creator would
        like to have us sign.  The message may, or may not, have already been signed by some of the
        other members.  Furthermore, we can choose for ourselves if we want to add our signature to
        the sub-message or not.

        Once we have determined that we could provide a signature and that the sub-message is valid,
        from a timeline perspective, we will ask the community to say yes or no to adding our
        signature.  This question is done by calling the
        sub-message.authentication.allow_signature_func method.

        We will only add our signature if the allow_signature_func method returns the same, or a
        modified sub-message.  If so, a dispersy-signature-response message is send to the creator
        of the message, the first one in the authentication list.

        If we can add multiple signatures, i.e. we have the private keys for more that one member
        signing the sub-message, the allow_signature_func is called only once but multiple
        signatures will be appended.

        @see: create_signature_request

        @param messages: The dispersy-signature-request messages.
        @type messages: [Message.Implementation]
        """
        meta = messages[0].community.get_meta_message(u"dispersy-signature-response")
        responses = []
        for message in messages:
            assert isinstance(message, Message.Implementation), type(message)
            assert isinstance(message.payload.message, Message.Implementation), type(message.payload.message)
            assert isinstance(message.payload.message.authentication, MultiMemberAuthentication.Implementation), type(message.payload.message.authentication)

            # the community must allow this signature
            submsg = message.payload.message.authentication.allow_signature_func(message.payload.message)
            if submsg:
                responses.append(meta.impl(distribution=(message.community.global_time,),
                                           destination=(message.candidate,),
                                           payload=(message.payload.identifier, submsg)))

        self.store_update_forward(responses, False, False, True)

    def check_signature_response(self, messages):
        for message in messages:
            if not self._request_cache.has(message.payload.identifier, SignatureRequestCache):
                yield DropMessage(message, "invalid response identifier")
                continue

            yield message

    def on_signature_response(self, messages):
        """
        Handle one or more dispersy-signature-response messages.

        We sent out a dispersy-signature-request, through the create_signature_request method, and
        have now received a dispersy-signature-response in reply.  If the signature is valid, we
        will call response_func with sub-message, where sub-message is the message parameter given
        to the create_signature_request method.

        Note that response_func is also called when the sub-message does not yet contain all the
        signatures.  This can be checked using sub-message.authentication.is_signed.
        """
        for message in messages:
            # get cache object linked to this request and stop timeout from occurring
            cache = self._request_cache.pop(message.payload.identifier, SignatureRequestCache)

            if __debug__: dprint("response")
            old_submsg = cache.request.payload.message
            new_submsg = message.payload.message

            old_body = old_submsg.packet[:len(old_submsg.packet) - sum([member.signature_length for member in old_submsg.authentication.members])]
            new_body = new_submsg.packet[:len(new_submsg.packet) - sum([member.signature_length for member in new_submsg.authentication.members])]

            store, update, forward = cache.response_func(old_submsg, new_submsg, old_body != new_body, *cache.response_args)
            if store or update or forward:
                for signature, member in new_submsg.authentication.signed_members:
                    if not signature and member.private_key:
                        new_submsg.authentication.set_signature(member, member.sign(new_body))

                self.store_update_forward([new_submsg], store, update, forward)

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
        community = messages[0].community
        requests = {}

        if __debug__: dprint("received ", len(messages), " missing-sequence message for community ", community.database_id)

        # we know that there are buggy clients out there that give numerous overlapping requests.
        # we will filter these to perform as few queries on the database as possible
        for message in messages:
            request = requests.get(message.candidate.sock_addr)
            if not request:
                requests[message.candidate.sock_addr] = request = (message.candidate, set())
            candidate, numbers = request

            member_id = message.payload.member.database_id
            message_id = message.payload.message.database_id
            if __debug__:
                dprint(candidate, " requests member:", member_id, " message_id:", message_id, " range:[", message.payload.missing_low, ":", message.payload.missing_high, "]")
                for sequence in xrange(message.payload.missing_low, message.payload.missing_high + 1):
                    if (member_id, message_id, sequence) in numbers:
                        dprint("ignoring duplicate request for ", member_id, ":", message_id, ":", sequence, " from ", candidate)
            numbers.update((member_id, message_id, sequence) for sequence in xrange(message.payload.missing_low, message.payload.missing_high + 1))

        keyfunc = lambda tup: (tup[0], tup[1])
        for candidate, numbers in requests.itervalues():
            # we limit the response by byte_limit bytes per incoming candidate
            byte_limit = community.dispersy_missing_sequence_response_limit

            # it is much easier to count packets... hence, to optimize we translate the byte_limit
            # into a packet limit.  we will assume a 256 byte packet size (security packets are
            # generally small)
            packet_limit = max(1, int(byte_limit / 128))

            packets = []
            for (member_id, message_id), iterator in groupby(sorted(numbers), keyfunc):
                _, _, lowest = _, _, highest = iterator.next()
                for _, _, highest in iterator:
                    pass

                # limiter
                highest = min(lowest + packet_limit, highest)
                packet_limit -= (highest - lowest) + 1

                if __debug__: dprint("fetching member:", member_id, " message:", message_id, ", ", highest - lowest + 1, " packets from database for ", candidate)
                for packet, in self._database.execute(u"SELECT packet FROM sync WHERE member = ? AND meta_message = ? ORDER BY global_time LIMIT ? OFFSET ?",
                                                      (member_id, message_id, highest - lowest + 1, lowest - 1)):
                    packet = str(packet)
                    packets.append(packet)

                    byte_limit -= len(packet)
                    if byte_limit <= 0:
                        if __debug__: dprint("Bandwidth throttle")
                        break

                if byte_limit <= 0:
                    break

            if __debug__:
                # ensure we are sending the correct sequence numbers back
                for packet in packets:
                    msg = self.convert_packet_to_message(packet, community)
                    assert msg
                    key = (msg.authentication.member.database_id, msg.database_id, msg.distribution.sequence_number)
                    assert key in requests[candidate.sock_addr][1], key
                    dprint("Syncing ", len(packet), " member:", key[0], " message:", key[1], " sequence:", key[2], " to " , candidate)

                self._statistics.outgoing(u"-sequence-", sum(len(packet) for packet in packets), len(packets))
            self._endpoint.send([candidate], packets)

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
                msg = self.convert_packet_to_message(packet, community, verify=False)
                allowed, proofs = community.timeline.check(msg)
                if allowed and proofs:
                    if __debug__:
                        dprint(message.candidate, " found ", len(proofs), " [",", ".join("%s %d@%d" % (proof.name, proof.authentication.member.database_id, proof.distribution.global_time) for proof in proofs), "] for message ", msg.name, " ", message.payload.member.database_id, "@", message.payload.global_time)
                        self._statistics.outgoing(u"-proof-", sum(len(proof.packet) for proof in proofs), len(proofs))
                    self._endpoint.send([message.candidate], [proof.packet for proof in proofs])

                else:
                    if __debug__: dprint("unable to give ", message.candidate, " missing proof.  allowed:", allowed, ".  proofs:", len(proofs), " packets")

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
        >>> bob = Member(bob_public_key)
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
    #     check = message.community.timeline.check

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
            message.community.timeline.authorize(message.authentication.member, message.distribution.global_time, message.payload.permission_triplets, message)

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
        >>> bob = Member(bob_public_key)
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
            message.community.timeline.revoke(message.authentication.member, message.distribution.global_time, message.payload.permission_triplets, message)

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

                if __debug__:
                    assert msg.distribution.global_time > message.distribution.global_time
                    allowed, _ = community.timeline.check(msg)
                    assert allowed, "create_undo was called without having the permission to undo"

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
            allowed, _ = message.community.timeline.check(message)
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
                        if __debug__:
                            self._statistics.outgoing(msg.name, len(msg.packet), 1)
                        self._endpoint.send([message.candidate], [msg.packet])

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

        self._database.executemany(u"UPDATE sync SET undone = ? WHERE community = ? AND member = ? AND global_time = ?",
                                   ((message.packet_id, message.community.database_id, message.payload.member.database_id, message.payload.global_time) for message in messages))
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
        timeline = community.timeline
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

        if __debug__: dprint(community.cid.encode("HEX"), " start sanity check [db-id:", community.database_id, "]")
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

            if not member_id == community.my_member.database_id:
                raise ValueError("my member's database id is invalid", member_id, community.my_member.database_id)

            try:
                self._database.execute(u"SELECT 1 FROM private_key WHERE member = ?", (member_id,)).next()
            except StopIteration:
                raise ValueError("unable to find the private key for my member")

            try:
                self._database.execute(u"SELECT 1 FROM sync WHERE member = ? AND meta_message = ?", (member_id, meta_identity.database_id)).next()
            except StopIteration:
                raise ValueError("unable to find the dispersy-identity message for my member")

            if __debug__: dprint("my identity is OK")

            #
            # the dispersy-identity must be in the database for each member that has one or more
            # messages in the database
            #
            A = set(id_ for id_, in self._database.execute(u"SELECT member FROM sync WHERE community = ? GROUP BY member", (community.database_id,)))
            B = set(id_ for id_, in self._database.execute(u"SELECT member FROM sync WHERE meta_message = ?", (meta_identity.database_id,)))
            if not len(A) == len(B):
                raise ValueError("inconsistent dispersy-identity messages.", A.difference(B))

        try:
            meta_undo_other = community.get_meta_message(u"dispersy-undo-other")
        except KeyError:
            # undo-other is not enabled
            pass
        else:

            #
            # ensure that we have proof for every dispersy-undo-other message
            #
            # TODO we are not taking into account that undo messages can be undone
            for undo_packet_id, undo_packet_global_time, undo_packet in select(u"SELECT id, global_time, packet FROM sync WHERE community = ? AND meta_message = ? ORDER BY id LIMIT ? OFFSET ?", (community.database_id, meta_undo_other.database_id)):
                undo_packet = str(undo_packet)
                undo_message = self.convert_packet_to_message(undo_packet, community)

                # get the message that undo_message refers to
                try:
                    packet, undone = self._database.execute(u"SELECT packet, undone FROM sync WHERE community = ? AND member = ? AND global_time = ?", (community.database_id, undo_message.payload.member.database_id, undo_message.payload.global_time)).next()
                except StopIteration:
                    raise ValueError("found dispersy-undo-other but not the message that it refers to")
                packet = str(packet)
                message = self.convert_packet_to_message(packet, community)

                if not undone:
                    raise ValueError("found dispersy-undo-other but the message that it refers to is not undone")

                if message.undo_callback is None:
                    raise ValueError("found dispersy-undo-other but the message that it refers to does not have an undo_callback")

                # get the proof that undo_message is valid
                allowed, proofs = community.timeline.check(undo_message)

                if not allowed:
                    raise ValueError("found dispersy-undo-other that, according to the timeline, is not allowed")

                if not proofs:
                    raise ValueError("found dispersy-undo-other that, according to the timeline, has no proof")

                if __debug__: dprint("dispersy-undo-other packet ", undo_packet_id, "@", undo_packet_global_time, " referring ", undo_message.payload.packet.name, " ", undo_message.payload.member.database_id, "@", undo_message.payload.global_time, " is OK")

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

        if __debug__: dprint(community.cid.encode("HEX"), " success")

    def _generic_timeline_check(self, messages):
        meta = messages[0].meta
        if isinstance(meta.authentication, NoAuthentication):
            # we can not timeline.check this message because it uses the NoAuthentication policy
            for message in messages:
                yield message

        else:
            for message in messages:
                allowed, proofs = meta.community.timeline.check(message)
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
                yield 5 * 60.0

                # flush changes to disk every 1 minutes
                self._database.commit()
            except GeneratorExit:
                if __debug__:
                    dprint("shutdown")
                    dprint(self.info(), pprint=True)
                self._database.commit()
                break

    def _candidate_walker(self):
        """
        Periodically select a candidate and take a step in the network.
        """
        walker_communities = self._walker_commmunities

        steps = 0
        start = time()

        # delay will never be less than 0.1, hence we can accommodate 50 communities before the
        # interval between each step becomes larger than 5.0 seconds
        optimaldelay = max(0.1, 5.0 / len(walker_communities))
        if __debug__: dprint("there are ", len(walker_communities), " walker enabled communities.  pausing ", optimaldelay, "s (on average) between each step")

        if __debug__:
            RESETS = 0
            STEPS = 0
            START = start
            DELAY = 0.0
            for community in walker_communities:
                community.__MOST_RESENT_WALK = 0.0

        while True:
            community = walker_communities.pop(0)
            walker_communities.append(community)

            if __debug__:
                NOW = time()
                OPTIMALSTEPS = (NOW - START) / optimaldelay
                STEPDIFF = NOW - community.__MOST_RESENT_WALK
                community.__MOST_RESENT_WALK = NOW
                dprint(community.cid.encode("HEX"), " taking step every ", "%.2f" % DELAY, " sec in ", len(walker_communities), " communities.  steps: ", STEPS, "/", int(OPTIMALSTEPS), " ~ %.2f." % (STEPS / OPTIMALSTEPS), "  diff: %.1f" % STEPDIFF, ".  resets: ", RESETS)
                STEPS += 1

            # walk
            assert community.dispersy_enable_candidate_walker
            assert community.dispersy_enable_candidate_walker_responses
            community.dispersy_take_step()
            steps += 1

            optimaltime = start + steps * optimaldelay
            actualtime = time()

            if optimaltime + 5.0 < actualtime:
                # way out of sync!  reset start time
                start = actualtime
                steps = 0
                self._statistics.increment_walk_reset()
                if __debug__:
                    dprint("can not keep up!  resetting walker start time!", level="warning")
                    DELAY = 0.0
                    RESETS += 1

            else:
                if __debug__:
                    DELAY = max(0.0, optimaltime - actualtime)
                yield max(0.0, optimaltime - actualtime)

    def _periodically_cleanup_candidates(self):
        """
        Periodically remove Candidate instance where all communities are obsolete.
        """
        while True:
            yield 5 * 60.0

            now = time()
            for key, candidate in [(key, candidate) for key, candidate in self._candidates.iteritems() if candidate.is_all_obsolete(now)]:
                if __debug__: dprint("removing obsolete candidate ", candidate)
                del self._candidates[key]
                self.wan_address_unvote(candidate)

    if __debug__:
        def _stats_candidates(self):
            while True:
                yield 10.0
                now = time()
                dprint("--- %s:%d" % self._lan_address, " (%s:%d) " % self._wan_address, self._connection_type)
                for community in sorted(self._communities.itervalues(), key=lambda community: community.cid):
                    if community.get_classification() == u"PreviewChannelCommunity":
                        continue

                    candidates = [candidate for candidate in self._candidates.itervalues() if candidate.in_community(community, now) and candidate.is_any_active(now)]
                    dprint(" ", community.cid.encode("HEX"), " ", "%20s" % community.get_classification(), " with ", len(candidates), "" if community.dispersy_enable_candidate_walker else "*", " candidates[:5] ", ", ".join(str(candidate) for candidate in candidates[:5]))

        def _stats_detailed_candidates(self):
            while True:
                yield 10.0
                now = time()
                dprint("--- %s:%d" % self._lan_address, " (%s:%d) " % self._wan_address, self._connection_type)
                for community in sorted(self._communities.itervalues(), key=lambda community: community.cid):
                    if community.get_classification() == u"PreviewChannelCommunity":
                        continue

                    categories = {u"walk":[], u"stumble":[], u"intro":[], u"sandi":[], u"none":[]}
                    for candidate in self._candidates.itervalues():
                        if isinstance(candidate, WalkCandidate) and candidate.in_community(community, now):
                            categories[candidate.get_category(community, now)].append(candidate)

                    dprint("--- ", community.cid.encode("HEX"), " ", community.get_classification(), " ---")
                    dprint("--- [%2d:%2d:%2d:%2d:%2d]" % (len(categories[u"walk"]), len(categories[u"stumble"]), len(categories[u"intro"]), len(categories[u"sandi"]), len(self._bootstrap_candidates)))

                    for category, candidates in categories.iteritems():
                        for candidate in candidates:
                            dprint("%4ds " % min(candidate.age(now), 9999),
                                   "A " if candidate.is_any_active(now) else " I",
                                   "O" if candidate.is_all_obsolete(now) else " ",
                                   "E" if candidate.is_eligible_for_walk(community, now) else " ",
                                   "B" if isinstance(candidate, BootstrapCandidate) else " ",
                                   " %-7s" % category,
                                   " %-13s" % candidate.connection_type,
                                   " ", candidate)

        def _stats_triggers(self):
            while True:
                yield 10.0
                for counter, trigger in enumerate(self._triggers):
                    dprint("%3d " % (counter + 1), trigger)

        def _stats_info(self):
            while True:
                yield 10.0
                dprint(self._statistics.info(), pprint=True)

    def info(self, statistics=True, transfers=True, attributes=True, sync_ranges=True, database_sync=True, candidate=True):
        """
        Returns a dictionary with runtime statistical information.

        The dictionary should only contain simple data types such as dictionaries, lists, tuples,
        strings, integers, etc.  Just no objects, methods, and the like.

        Depending on __debug__ more or less information may be available.  Note that Release
        versions do NOT run __debug__ mode and hence may return less information.
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
        # 2.3: added info["timestamp"], community["candidates"] is no longer sorted
        # 2.4: added database_version
        # 2.5: removed delay, drop, outgoing, and success statistics (memory usage)
        # 2.6: added community["acceptable_global_time"],
        #      community["dispersy_acceptable_global_time_range"]
        # 2.7: added community["database_id"]
        # 2.8: added global_time to candidates
        # 2.9: added connection_type
        # 3.0: added info["statistics"]["walk_attempt"] and info["statistics"]["walk_success"]
        # 3.1: removed busy_time from statistics
        # 3.2: removed address specific information from info["statistics"]["outgoing"]
        #      all info["statistics"] are now stored in info directly
        #      info["total_up"] and info["total_down"] are now always present
        # 3.3: added info["walk_fail"] in __debug__ mode
        # 3.4: added info["walk_reset"]

        now = time()
        info = {"version":3.3,
                "class":"Dispersy",
                "lan_address":self._lan_address,
                "wan_address":self._wan_address,
                "timestamp":now,
                "database_version":self._database.database_version,
                "connection_type":self._connection_type,
                "total_up":self._endpoint.total_up,
                "total_down":self._endpoint.total_down}

        if statistics:
            info.update(self._statistics.info())

        info["communities"] = []
        for community in self._communities.itervalues():
            community_info = {"classification":community.get_classification(),
                              "database_id":community.database_id,
                              "hex_cid":community.cid.encode("HEX"),
                              "global_time":community.global_time,
                              "acceptable_global_time":community.acceptable_global_time,
                              "dispersy_acceptable_global_time_range":community.dispersy_acceptable_global_time_range,
                              "database_version":community.database_version}
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
                community_info["candidates"] = [(candidate.lan_address, candidate.wan_address, candidate.get_global_time(community)) for candidate in self._candidates.itervalues() if candidate.in_community(community, now) and candidate.is_any_active(now)]

                if __debug__: dprint(community_info["classification"], " has ", len(community_info["candidates"]), " candidates")

        if __debug__: dprint(info, pprint=True)
        return info
