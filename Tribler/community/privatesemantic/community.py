# Written by Niels Zeilemaker
import sys
from binascii import hexlify
from collections import defaultdict, namedtuple
from hashlib import md5
from itertools import groupby
from random import sample, randint, shuffle, choice
from time import time

from Crypto.Random.random import StrongRandom
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall, deferLater

from .conversion import ForwardConversion, PSearchConversion, HSearchConversion, PoliSearchConversion
from .crypto.paillier import (paillier_add, paillier_init, paillier_encrypt, paillier_decrypt, paillier_polyval,
                              paillier_multiply, paillier_add_unenc)
from .crypto.polycreate import compute_coeff, polyval
from .crypto.rsa import rsa_init, rsa_encrypt, rsa_decrypt, rsa_compatible, hash_element
from .payload import *
from Tribler.community.privatesemantic.conversion import bytes_to_long, long_to_bytes
from Tribler.community.privatesemantic.database import SemanticDatabase
from Tribler.dispersy.authentication import MemberAuthentication, NoAuthentication
from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME, WalkCandidate, BootstrapCandidate, Candidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.member import Member
from Tribler.dispersy.message import Message, DelayMessageByProof, DropMessage
from Tribler.dispersy.requestcache import NumberCache, IntroductionRequestCache, RandomNumberCache
from Tribler.dispersy.resolution import PublicResolution

DEBUG = False
DEBUG_VERBOSE = False
ENCRYPTION = True

PING_INTERVAL = CANDIDATE_WALK_LIFETIME / 5
PING_TIMEOUT = CANDIDATE_WALK_LIFETIME / 2
TIME_BETWEEN_CONNECTION_ATTEMPTS = 10.0

PSI_CARDINALITY, PSI_OVERLAP, PSI_AES = range(3)

class TasteBuddy():
    def __init__(self, overlap, sock_addr):
        assert isinstance(overlap, (list, int, long, float)), type(overlap)
        if isinstance(overlap, list):
            assert all(isinstance(cur_overlap, (int, long, float)) for cur_overlap in overlap)

        self.overlap = overlap
        self.sock_addr = sock_addr

    def update_overlap(self, other):
        if isinstance(self.overlap, list):
            if len(other.overlap) > len(self.overlap):
                self.overlap = other.overlap
        else:
            self.overlap = max(self.overlap, other.overlap)

    def does_overlap(self, preference):
        if isinstance(self.overlap, list):
            return preference in self.overlap
        return False

    def __cmp__(self, other):
        if isinstance(other, TasteBuddy):
            if isinstance(self.overlap, list):
                return cmp(len(self.overlap), len(other.overlap))
            return cmp(self.overlap, other.overlap)

        elif isinstance(other, int):
            if isinstance(self.overlap, list):
                return cmp(len(self.overlap), other)
            return cmp(self.overlap, other)

    def __str__(self):
        overlap = self.overlap
        if isinstance(self.overlap, list):
            overlap = len(overlap)
        return "TB_%s_%s" % (overlap, self.sock_addr)

    def __hash__(self):
        return hash(self.sock_addr)

class ActualTasteBuddy(TasteBuddy):
    def __init__(self, overlap, timestamp, candidate):
        assert isinstance(candidate, WalkCandidate), type(candidate)

        TasteBuddy.__init__(self, overlap, candidate.sock_addr)
        self.timestamp = timestamp
        self.candidate = candidate

    def should_cache(self):
        return self.candidate.connection_type == u"public"

    def time_remaining(self):
        too_old = time() - PING_TIMEOUT
        diff = self.timestamp - too_old
        return diff if diff > 0 else 0

    def __eq__(self, other):
        if isinstance(other, TasteBuddy):
            return self.sock_addr == other.sock_addr

        elif isinstance(other, Member):
            return other.mid == self.candidate.get_member().mid

        elif isinstance(other, Candidate):
            return self.candidate.sock_addr == other.sock_addr

        elif isinstance(other, tuple):
            return self.candidate.sock_addr == other

    def __str__(self):
        overlap = self.overlap
        if isinstance(self.overlap, list):
            overlap = len(overlap)
        return "ATB_%d_%s_%s" % (self.timestamp, overlap, self.candidate)

class PossibleTasteBuddy(TasteBuddy):
    def __init__(self, overlap, timestamp, candidate_mid, received_from):
        assert isinstance(timestamp, (long, float)), type(timestamp)
        assert isinstance(received_from, WalkCandidate), type(received_from)

        TasteBuddy.__init__(self, overlap, None)
        self.timestamp = timestamp
        self.candidate_mid = candidate_mid
        self.received_from = received_from

    def time_remaining(self):
        too_old = time() - PING_TIMEOUT
        diff = self.timestamp - too_old
        return diff if diff > 0 else 0

    def __eq__(self, other):
        if isinstance(other, Candidate):
            return self.received_from.sock_addr == other.sock_addr
        return self.candidate_mid == other.candidate_mid

    def __str__(self):
        overlap = self.overlap
        if isinstance(self.overlap, list):
            overlap = len(overlap)
        return "PTB_%d_%d_%s_%s" % (self.timestamp, overlap, self.candidate_mid.encode("HEX"), self.received_from)

    def __hash__(self):
        return hash(self.candidate_mid)

class ForwardCommunity():

    def initialize(self, integrate_with_tribler=True, encryption=ENCRYPTION, forward_to=10, max_prefs=None, max_fprefs=None, max_taste_buddies=10, psi_mode=PSI_CARDINALITY, send_simi_reveal=False):
        self.integrate_with_tribler = bool(integrate_with_tribler)
        self.encryption = bool(encryption)
        self.key = self.init_key()
        self.psi_mode = psi_mode

        if not max_prefs:
            max_len = 2 ** 16 - 60  # self.dispersy_sync_bloom_filter_bits
            max_prefs = max_len / self.key.encsize
            max_hprefs = max_len / 20
        else:
            max_hprefs = max_prefs

        if not max_fprefs:
            max_fprefs = max_prefs

        self.max_prefs = max_prefs
        self.max_h_prefs = max_hprefs
        self.max_f_prefs = max_fprefs

        self.forward_to = forward_to
        self.max_taste_buddies = max_taste_buddies

        self.send_simi_reveal = send_simi_reveal

        self.taste_buddies = []
        self.possible_taste_buddies = []
        self.requested_introductions = {}

        self.my_preference_cache = [None, None]

        self.create_time_encryption = 0.0
        self.create_time_decryption = 0.0
        self.receive_time_encryption = 0.0

        self.send_packet_size = 0
        self.forward_packet_size = 0
        self.reply_packet_size = 0

        if self.integrate_with_tribler:
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import MyPreferenceDBHandler
            from Tribler.Core.CacheDB.Notifier import Notifier

            # tribler channelcast database
            self._mypref_db = MyPreferenceDBHandler.getInstance()
            self._notifier = Notifier.getInstance()
        else:
            self._mypref_db = Das4DBStub(self._dispersy)
            self._notifier = None

        self._peercache = SemanticDatabase(self._dispersy)
        self._peercache.open()

    def init_key(self):
        return rsa_init()

    def unload_community(self):
        self._peercache.close()

    def initiate_meta_messages(self):
        return [Message(self, u"similarity-reveal", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), SimiRevealPayload(), self.check_similarity_reveal, self.on_similarity_reveal),
                Message(self, u"ping", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PingPayload(), self._generic_timeline_check, self.on_ping),
                Message(self, u"pong", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PongPayload(), self.check_pong, self.on_pong)]

    def _initialize_meta_messages(self):
        ori = self._meta_messages[u"dispersy-introduction-request"]
        new = Message(self, ori.name, ori.authentication, ori.resolution, ori.distribution, ori.destination, ExtendedIntroPayload(), ori.check_callback, ori.handle_callback)
        self._meta_messages[u"dispersy-introduction-request"] = new

    def initiate_conversions(self):
        return [DefaultConversion(self), ForwardConversion(self)]

    def add_taste_buddies(self, new_taste_buddies):
        for new_taste_buddy in new_taste_buddies:
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "ForwardCommunity: new taste buddy?", new_taste_buddy

            for taste_buddy in self.taste_buddies:
                if new_taste_buddy == taste_buddy:
                    if DEBUG_VERBOSE:
                        print >> sys.stderr, long(time()), "ForwardCommunity: new taste buddy? no equal to", new_taste_buddy, taste_buddy

                    taste_buddy.update_overlap(new_taste_buddy)
                    new_taste_buddies.remove(new_taste_buddy)
                    break

            # new peer
            else:
                if len(self.taste_buddies) < self.max_taste_buddies or new_taste_buddy > self.taste_buddies[-1]:
                    if DEBUG_VERBOSE:
                        print >> sys.stderr, long(time()), "ForwardCommunity: new taste buddy? yes adding to list"

                    self.taste_buddies.append(new_taste_buddy)
                    if "send_ping_requests" not in self._pending_tasks:
                        self._pending_tasks["send_ping_requests"] = lc = LoopingCall(self.create_ping_requests)
                        lc.start(PING_INTERVAL)

                elif DEBUG_VERBOSE:
                    print >> sys.stderr, long(time()), "ForwardCommunity: new taste buddy? no smaller than", new_taste_buddy, self.taste_buddies[-1]

                self.new_taste_buddy(new_taste_buddy)

        self.taste_buddies.sort(reverse=True)
        self.taste_buddies = self.taste_buddies[:self.max_taste_buddies]

        if DEBUG_VERBOSE:
            print >> sys.stderr, long(time()), "ForwardCommunity: current tastebuddy list", len(self.taste_buddies), map(str, self.taste_buddies)
        elif DEBUG:
            print >> sys.stderr, long(time()), "ForwardCommunity: current tastebuddy list", len(self.taste_buddies)

    def yield_taste_buddies(self, ignore_candidate=None):
        for i in range(len(self.taste_buddies) - 1, -1, -1):
            if self.taste_buddies[i].time_remaining() == 0:
                if DEBUG:
                    print >> sys.stderr, long(time()), "ForwardCommunity: removing tastebuddy too old", self.taste_buddies[i]
                self.taste_buddies.pop(i)

        taste_buddies = self.taste_buddies[:]
        shuffle(taste_buddies)
        ignore_sock_addr = ignore_candidate.sock_addr if ignore_candidate else None

        for taste_buddy in taste_buddies:
            if taste_buddy.overlap and taste_buddy.candidate.sock_addr != ignore_sock_addr:
                yield taste_buddy

    def yield_taste_buddies_candidates(self, ignore_candidate=None):
        for tb in self.yield_taste_buddies(ignore_candidate):
            yield tb.candidate

    def is_taste_buddy(self, candidate):
        for tb in self.yield_taste_buddies():
            if tb == candidate:
                return tb

    def is_taste_buddy_mid(self, mid):
        assert isinstance(mid, str), type(mid)
        assert len(mid) == 20, len(mid)

        for tb in self.yield_taste_buddies():
            if mid == tb.candidate.get_member().mid:
                return tb

    def is_taste_buddy_sock(self, sock_addr):
        for tb in self.yield_taste_buddies():
            if tb == sock_addr:
                return tb

    def is_overlapping_taste_buddy_mid(self, mid):
        assert isinstance(mid, str), type(mid)
        assert len(mid) == 20, len(mid)

        if self.is_taste_buddy_mid(mid):
            return True

        _mid = long(hexlify(mid), 16)
        for tb in self.yield_taste_buddies():
            if tb.does_overlap(_mid):
                return True

    def reset_taste_buddy(self, candidate):
        for tb in self.yield_taste_buddies():
            if tb == candidate:
                tb.timestamp = time()
                break

    def remove_taste_buddy(self, candidate):
        for tb in self.yield_taste_buddies():
            if tb == candidate:
                self.taste_buddies.remove(tb)
                break

    def new_taste_buddy(self, tb):
        # if we have any similarity, cache peer
        if tb.overlap and tb.should_cache():
            self._peercache.add_peer(tb.overlap, *tb.candidate.sock_addr)

    def add_possible_taste_buddies(self, possibles):
        if __debug__:
            for possible in possibles:
                assert isinstance(possible, PossibleTasteBuddy), type(possible)

        low_sim = self.get_least_similar_tb()
        for new_possible in possibles:
            if new_possible <= low_sim or self.is_taste_buddy_mid(new_possible.candidate_mid) or self.my_member.mid == new_possible.candidate_mid:
                possibles.remove(new_possible)
                continue

            for i, possible in enumerate(self.possible_taste_buddies):
                if possible == new_possible:
                    new_possible.update_overlap(possible)

                    # replace in list
                    self.possible_taste_buddies[i] = new_possible
                    break

            # new peer
            else:
                self.possible_taste_buddies.append(new_possible)

        self.possible_taste_buddies.sort(reverse=True)
        if DEBUG_VERBOSE and possibles:
            print >> sys.stderr, long(time()), "ForwardCommunity: got possible taste buddies, current list", len(self.possible_taste_buddies), map(str, self.possible_taste_buddies)
        elif DEBUG and possibles:
            print >> sys.stderr, long(time()), "ForwardCommunity: got possible taste buddies, current list", len(self.possible_taste_buddies)

    def clean_possible_taste_buddies(self):
        low_sim = self.get_least_similar_tb()
        for i in range(len(self.possible_taste_buddies) - 1, -1, -1):
            to_low_sim = self.possible_taste_buddies[i] <= low_sim
            to_old = self.possible_taste_buddies[i].time_remaining() == 0
            is_tb = self.is_taste_buddy_mid(self.possible_taste_buddies[i].candidate_mid)

            if to_low_sim or to_old or is_tb:
                if DEBUG:
                    print >> sys.stderr, long(time()), "ForwardCommunity: removing possible tastebuddy", long(time()), to_low_sim, to_old, is_tb, self.possible_taste_buddies[i]
                self.possible_taste_buddies.pop(i)

    def has_possible_taste_buddies(self, candidate):
        for possible in self.possible_taste_buddies:
            if possible == candidate:
                return True
        return False

    def get_least_similar_tb(self):
        if len(self.taste_buddies) == self.max_taste_buddies:
            return self.taste_buddies[-1]
        return 0

    def get_most_similar(self, candidate):
        assert isinstance(candidate, WalkCandidate), [type(candidate), candidate]

        self.clean_possible_taste_buddies()

        if self.possible_taste_buddies:
            most_similar = self.possible_taste_buddies.pop(0)
            return most_similar.received_from, most_similar.candidate_mid

        return candidate, None

    def get_connections(self, nr=10, ignore_candidate=None):
        # use taste buddies and fill with random candidates
        candidates = set(self.yield_taste_buddies_candidates(ignore_candidate))
        if len(candidates) < nr:
            sock_addresses = set(candidate.sock_addr for candidate in candidates)
            if ignore_candidate:
                sock_addresses.add(ignore_candidate.sock_addr)

            for candidate in self.dispersy_yield_verified_candidates():
                if candidate.sock_addr not in sock_addresses:
                    candidates.add(candidate)
                    sock_addresses.add(candidate.sock_addr)

                if len(candidates) == nr:
                    break

        elif len(candidates) > nr:
            candidates = sample(candidates, nr)

        return list(candidates)

    # connect to first nr peers in peercache
    def connect_to_peercache(self, nr=10, standins=10):
        payload = self.create_similarity_payload()
        if payload:
            tbs = self.get_tbs_from_peercache(nr, standins)
            if DEBUG:
                print >> sys.stderr, long(time()), "ForwardCommunity: connecting to", len(tbs), [str(tb_possibles[0]) for tb_possibles in tbs]

            @inlineCallbacks
            def attempt_to_connect(tbs):
                for tb in tbs:
                    candidate = self.get_candidate(tb.sock_addr, replace=False)
                    if not candidate:
                        candidate = self.create_candidate(tb.sock_addr, False, tb.sock_addr, tb.sock_addr, u"unknown")

                    if not self.is_taste_buddy_sock(candidate.sock_addr):
                        self.create_similarity_request(candidate, payload)

                    yield deferLater(reactor, TIME_BETWEEN_CONNECTION_ATTEMPTS, lambda: None)

                    if self.is_taste_buddy_sock(candidate.sock_addr):
                        break

            for i, tb_possibles in enumerate(tbs):
                self._pending_tasts["attempt to connect %d" % i] = reactor.callLater(0.005 * i, attempt_to_connect, tb_possibles)

        elif DEBUG:
            print >> sys.stderr, long(time()), "ForwardCommunity: no similarity_payload, cannot connect"

    def get_tbs_from_peercache(self, nr, standins):
        return [[TasteBuddy(overlap, (ip, port))] * standins for overlap, ip, port in self._peercache.get_peers()[:nr]]

    class SimilarityAttempt(RandomNumberCache):

        def __init__(self, community, requested_candidate):
            super(ForwardCommunity.SimilarityAttempt, self).__init__(community.request_cache, u"similarity-attempt")
            assert isinstance(requested_candidate, WalkCandidate), type(requested_candidate)
            self.community = community
            self.requested_candidate = requested_candidate

        @property
        def timeout_delay(self):
            return 10.5

        def on_timeout(self):
            self.community.send_introduction_request(self.requested_candidate)

    def create_introduction_request(self, destination, allow_sync):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]

        if DEBUG:
            print >> sys.stderr, long(time()), "ForwardCommunity: creating intro request", isinstance(destination, BootstrapCandidate), self.is_taste_buddy(destination), self.has_possible_taste_buddies(destination)

        send = False
        if not isinstance(destination, BootstrapCandidate) and not self.is_taste_buddy(destination) and not self.has_possible_taste_buddies(destination):
            send = self.create_msimilarity_request(destination)

        if not send:
            self.send_introduction_request(destination, allow_sync=allow_sync)

    def create_similarity_payload(self):
        raise NotImplementedError()

    def process_similarity_response(self, candidate, candidate_mid, payload):
        raise NotImplementedError()
    def process_msimilarity_response(self, message):
        raise NotImplementedError()

    def create_msimilarity_request(self, destination):
        payload = self.create_similarity_payload()
        if payload:
            cache = self._request_cache.add(ForwardCommunity.SimilarityAttempt(self, destination))

            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "ForwardCommunity: sending msimilarity request to", destination, "with identifier", cache.number

            self.send_msimilarity_request(destination, cache.number, payload)
            return True

        return False

    def send_msimilarity_request(self, destination, identifier, payload):
        assert isinstance(identifier, int), type(identifier)
        raise NotImplementedError()

    class MSimilarityRequest(NumberCache):

        def __init__(self, community, requesting_candidate, requested_candidates, force_number, send_reveal=False):
            NumberCache.__init__(self, community.request_cache, u"m-similarity-request", force_number)
            self.community = community

            self.requesting_candidate = requesting_candidate
            self.requested_candidates = requested_candidates

            self.received_candidates = set()
            self.received_lists = []
            self.isProcessed = False
            self.send_reveal = send_reveal

        @property
        def timeout_delay(self):
            return 7.0

        @property
        def cleanup_delay(self):
            return 0.0

        def add_response(self, candidate, member, response):
            if candidate:
                rcandidate = self.did_request(candidate)
                if rcandidate:
                    # we need to associated this candidate with this mid, apparently this is only done when receiving an induction response
                    rcandidate.associate(member)

                    if rcandidate not in self.received_candidates:
                        self.received_candidates.add(rcandidate)
                        self.received_lists.append((rcandidate, member.mid, response))

                elif DEBUG:
                    print >> sys.stderr, long(time()), "ForwardCommunity: did not send request to candidate", candidate, "ignoring response"

            else:
                self.my_response = response

        def did_request(self, candidate):
            if candidate:
                for rcandidate in self.requested_candidates:
                    if rcandidate.sock_addr == candidate.sock_addr:
                        return rcandidate
            return False

        def is_complete(self):
            return len(self.received_lists) == len(self.requested_candidates)

        def process(self):
            if not self.isProcessed:
                self.isProcessed = True

                if self.requesting_candidate:
                    if DEBUG_VERBOSE:
                        print >> sys.stderr, long(time()), "ForwardCommunity: processed MSimilarityRequest send msimilarity-response to", self.requesting_candidate, self.received_lists

                    self.community.request_cache.pop(self.prefix, self.number)
                    return self.community.send_msimilarity_response(self.requesting_candidate, self.number, self.my_response, self.received_lists)

                for response in self.received_lists:
                    overlap = self.community.process_similarity_response(response[0], response[1], response[2])

                    if self.send_reveal and overlap:
                        if DEBUG_VERBOSE:
                            print >> sys.stderr, long(time()), "ForwardCommunity: sending reveal to", self.requested_candidates
                        self.community.send_similarity_reveal(response[0], overlap)
                return 0

        def on_timeout(self):
            if not self.isProcessed:
                if DEBUG:
                    print >> sys.stderr, long(time()), "ForwardCommunity: timeout MSimilarityRequest", self.number, len(self.received_lists), len(self.requested_candidates), str(self.requested_candidates[0])

                self.process()

    def check_msimilarity_request(self, messages):
        for message in messages:
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue

            if self._request_cache.has(u"similarity-attempt", message.payload.identifier):
                yield DropMessage(message, "send similarity attempt to myself?")
                continue

            if self._request_cache.has(u"m-similarity-request", message.payload.identifier):
                yield DropMessage(message, "currently processing another msimilarity request with this identifier")
                continue

            yield message

    def on_msimilarity_request(self, messages):
        for message in messages:
            # get candidates to forward requests to, excluding the requesting peer
            candidates = self.get_connections(self.forward_to, message.candidate)

            # create a register similarity request
            request = ForwardCommunity.MSimilarityRequest(self, message.candidate, candidates, message.payload.identifier)
            # TODO: this shouldn't be necessary, requires a change in dispersy
            request._number = message.payload.identifier
            assert request.number == message.payload.identifier, (request.number, message.payload.identifier)

            # add local response
            request.add_response(None, None, self.on_similarity_request([message], False))

            if candidates:
                # forward it to others
                self.send_similarity_request(candidates, message.payload.identifier, message.payload)
                self._request_cache.add(request)

            if request.is_complete():
                request.process()

    def create_similarity_request(self, destination, payload):
        cache = self._request_cache.add(ForwardCommunity.MSimilarityRequest(self, None, [destination], RandomNumberCache.find_unclaimed_identifier(self._request_cache, u"m-similarity-request"), self.send_simi_reveal))
        self.send_similarity_request([destination], cache.number, payload)

        if DEBUG:
            print >> sys.stderr, long(time()), "ForwardCommunity: send_similarity_request to", destination, cache.number

    def send_similarity_request(self, candidates, identifier, payload):
        raise NotImplementedError()

    def check_similarity_request(self, messages):
        for message in messages:
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue

            if self._request_cache.has(u"similarity-attempt", message.payload.identifier):
                yield DropMessage(message, "got similarity request issued by myself?")
                continue

            if self._request_cache.has(u"m-similarity-request", message.payload.identifier):
                yield DropMessage(message, "got similarity request forwarded by myself?")
                continue

            yield message

    def on_similarity_request(self, messages, send_messages=True):
        raise NotImplementedError()

    def check_similarity_response(self, messages):
        for message in messages:
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue

            request = self._request_cache.get(u"m-similarity-request", message.payload.identifier)
            if not request:
                yield DropMessage(message, "unknown identifier")
                continue

            if not request.did_request(message.candidate):
                yield DropMessage(message, "did not send request to this candidate")
                continue

            yield message

    def on_similarity_response(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "ForwardCommunity: got similarity response from", message.candidate

            request = self._request_cache.get(u"m-similarity-request", message.payload.identifier)
            if request:
                request.add_response(message.candidate, message.authentication.member, message.payload)
                if request.is_complete():
                    self.reply_packet_size += request.process()

            elif DEBUG:
                print >> sys.stderr, long(time()), "ForwardCommunity: could not get msimilarity requestcache for", message.payload.identifier

    def send_msimilarity_response(self, requesting_candidate, identifier, my_response, received_responses):
        assert isinstance(identifier, int), type(identifier)
        raise NotImplementedError()

    def check_msimilarity_response(self, messages):
        for message in messages:
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue

            request = self._request_cache.get(u"similarity-attempt", message.payload.identifier)
            if not request:
                print >> sys.stderr, "cannot find", message.payload.identifier, self._request_cache._identifiers.keys()

                yield DropMessage(message, "unknown identifier")
                continue

            yield message

    def on_msimilarity_response(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "ForwardCommunity: got msimilarity response from", message.candidate

            request = self._request_cache.pop(u"similarity-attempt", message.payload.identifier)
            if request:
                # replace message.candidate with WalkCandidate
                # TODO: this seems to be a bit dodgy
                message._candidate = request.requested_candidate

                overlap = self.process_msimilarity_response(message)
                if self.send_simi_reveal and overlap:
                    self.send_similarity_reveal(message.candidate, overlap)

                destination, introduce_me_to = self.get_most_similar(message.candidate)
                self.send_introduction_request(destination, introduce_me_to)

                if DEBUG and introduce_me_to:
                    print >> sys.stderr, long(time()), "ForwardCommunity: asking candidate %s to introduce me to %s after receiving similarities from %s" % (destination, introduce_me_to.encode("HEX"), message.candidate)
            elif DEBUG:
                print >> sys.stderr, long(time()), "ForwardCommunity: could not get similarity requestcache for", message.payload.identifier

    def send_similarity_reveal(self, destination, overlap):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]
        assert isinstance(overlap, (list, int))

        meta_request = self.get_meta_message(u"similarity-reveal")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=(overlap,))
        self._dispersy._forward([request])

    def check_similarity_reveal(self, messages):
        for message in messages:
            yield message

    def on_similarity_reveal(self, messages):
        for message in messages:
            if not isinstance(message.candidate, WalkCandidate):
                candidate = self.create_candidate(message.candidate.sock_addr, message.candidate.tunnel, message.candidate.sock_addr, message.candidate.sock_addr, u"unknown")
                candidate.associate(message.authentication.member)
                message._candidate = candidate

            self.add_taste_buddies([ActualTasteBuddy(message.payload.overlap, time(), message.candidate)])

            if DEBUG:
                print >> sys.stderr, "GOT similarity reveal from", message.candidate, self.is_taste_buddy(message.candidate), message.payload.overlap

    def send_introduction_request(self, destination, introduce_me_to=None, allow_sync=True, advice=True):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]
        assert not introduce_me_to or isinstance(introduce_me_to, str), type(introduce_me_to)

        cache = self._request_cache.add(IntroductionRequestCache(self, destination))
        destination.walk(time())

        if allow_sync:
            sync = self.dispersy_claim_sync_bloom_filter(cache)
        else:
            sync = None
        payload = (destination.sock_addr, self._dispersy._lan_address, self._dispersy._wan_address, advice, self._dispersy._connection_type, sync, cache.number, introduce_me_to)

        meta_request = self.get_meta_message(u"dispersy-introduction-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=payload)

        self._dispersy._forward([request])

        if DEBUG:
            print >> sys.stderr, long(time()), "ForwardCommunity: sending introduction-request to %s (%s,%s,%s)" % (destination, introduce_me_to.encode("HEX") if introduce_me_to else '', allow_sync, advice)


    def on_introduction_request(self, messages):
        for message in messages:
            introduce_me_to = ''
            if message.payload.introduce_me_to:
                candidate = self.get_walkcandidate(message)
                message._candidate = candidate

                if DEBUG:
                    ctb = self.is_taste_buddy(candidate)
                    print >> sys.stderr, "Got intro request from", ctb, ctb.overlap

                self.requested_introductions[candidate] = introduce_me_to = self.get_tb_or_candidate_mid(message.payload.introduce_me_to)

            if DEBUG:
                print >> sys.stderr, long(time()), "ForwardCommunity: got introduction request", message.payload.introduce_me_to.encode("HEX") if message.payload.introduce_me_to else '', introduce_me_to, self.requested_introductions

        Community.on_introduction_request(self, messages)

        if self._notifier:
            from Tribler.Core.simpledefs import NTFY_ACT_MEET, NTFY_ACTIVITIES, NTFY_INSERT
            for message in messages:
                self._notifier.notify(NTFY_ACTIVITIES, NTFY_INSERT, NTFY_ACT_MEET, "%s:%d" % message.candidate.sock_addr)

    def get_tb_or_candidate_mid(self, mid):
        tb = self.is_taste_buddy_mid(mid)
        if tb:
            return tb.candidate

        # no exact match, see if this is a friend
        _mid = long(hexlify(mid), 16)
        tbs = [tb for tb in self.yield_taste_buddies() if tb.does_overlap(_mid)]
        if tbs:
            tb = choice(tbs)
            return tb.candidate

        return self.get_candidate_mid(mid)

    def dispersy_get_introduce_candidate(self, exclude_candidate=None):
        if exclude_candidate:
            if exclude_candidate in self.requested_introductions:
                intro_me_candidate = self.requested_introductions[exclude_candidate]
                del self.requested_introductions[exclude_candidate]
                return intro_me_candidate

        return Community.dispersy_get_introduce_candidate(self, exclude_candidate)

    class PingRequestCache(RandomNumberCache):

        def __init__(self, community, requested_candidates):
            RandomNumberCache.__init__(self, community._request_cache, u"ping")
            self.community = community
            self.requested_candidates = requested_candidates
            self.received_candidates = set()

        def on_success(self, candidate):
            if self.did_request(candidate):
                self.received_candidates.add(candidate)

            return self.is_complete()

        def is_complete(self):
            return len(self.received_candidates) == len(self.requested_candidates)

        def did_request(self, candidate):
            # TODO: change if there's an __eq__ implemented in candidate
            return candidate.sock_addr in [rcandidate.sock_addr for rcandidate in self.requested_candidates]

        def on_timeout(self):
            for candidate in self.requested_candidates:
                if candidate not in self.received_candidates:
                    if DEBUG:
                        print >> sys.stderr, long(time()), "ForwardCommunity: no response on ping, removing from taste_buddies", candidate
                    self.community.remove_taste_buddy(candidate)

    def create_ping_requests(self):
        tbs = self.filter_tb(self.yield_taste_buddies())
        tbs = [tb.candidate for tb in tbs if tb.time_remaining() < PING_INTERVAL]

        if tbs:
            cache = self._request_cache.add(ForwardCommunity.PingRequestCache(self, tbs))
            self._create_pingpong(u"ping", tbs, cache.number)

    def on_ping(self, messages):
        for message in messages:
            self._create_pingpong(u"pong", [message.candidate], message.payload.identifier)

            self.reset_taste_buddy(message.candidate)

    def check_pong(self, messages):
        for message in messages:
            request = self._request_cache.get(u"ping", message.payload.identifier)
            if not request:
                yield DropMessage(message, "invalid response identifier")
                continue

            if not request.did_request(message.candidate):
                print >> sys.stderr, "did not send request to", message.candidate.sock_addr, [rcandidate.sock_addr for rcandidate in request.requested_candidates]
                yield DropMessage(message, "did not send ping to this candidate")
                continue

            yield message

    def on_pong(self, messages):
        for message in messages:
            request = self._request_cache.get(u"ping", message.payload.identifier)
            if request.on_success(message.candidate):
                self._request_cache.pop(u"ping", message.payload.identifier)

            self.reset_taste_buddy(message.candidate)

    def _create_pingpong(self, meta_name, candidates, identifier):
        meta = self.get_meta_message(meta_name)
        message = meta.impl(distribution=(self.global_time,), payload=(identifier,))
        self._dispersy._send(candidates, [message])

        if DEBUG:
            print >> sys.stderr, long(time()), "ForwardCommunity: send", meta_name, "to", len(candidates), "candidates:", map(str, candidates)

    def filter_tb(self, tbs):
        return list(tbs)

class PForwardCommunity(ForwardCommunity):

    def init_key(self):
        return paillier_init(ForwardCommunity.init_key(self))

    def initiate_meta_messages(self):
        messages = ForwardCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"msimilarity-request", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedVectorPayload(), self.check_msimilarity_request, self.on_msimilarity_request))
        messages.append(Message(self, u"similarity-request", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedVectorPayload(), self.check_similarity_request, self.on_similarity_request))
        messages.append(Message(self, u"msimilarity-response", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedSumsPayload(), self.check_msimilarity_response, self.on_msimilarity_response))
        messages.append(Message(self, u"similarity-response", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedSumPayload(), self.check_similarity_response, self.on_similarity_response))
        return messages

    def initiate_conversions(self):
        return [DefaultConversion(self), PSearchConversion(self)]

    def create_similarity_payload(self):
        t1 = time()

        global_vector = self.create_global_vector()
        str_global_vector = str(global_vector)
        if self.my_preference_cache[0] == str_global_vector:
            encrypted_vector = self.my_preference_cache[1]
        else:
            my_vector = self.get_my_vector(global_vector, local=True)
            if self.encryption:
                encrypted_vector = []
                for element in my_vector:
                    cipher = paillier_encrypt(self.key, element)
                    encrypted_vector.append(cipher)
            else:
                encrypted_vector = my_vector

            self.my_preference_cache = [str_global_vector, encrypted_vector]

        self.create_time_encryption += time() - t1

        if encrypted_vector:
            Payload = namedtuple('Payload', ['key_n', 'preference_list', 'global_vector'])
            return Payload(long(self.key.n), encrypted_vector, global_vector)
        return False

    def process_similarity_response(self, candidate, candidate_mid, payload):
        overlap = self.compute_overlap(payload._sum)
        self.add_taste_buddies([ActualTasteBuddy(overlap, time(), candidate)])
        return overlap

    def process_msimilarity_response(self, message):
        if DEBUG_VERBOSE:
            print >> sys.stderr, long(time()), "PSearchCommunity: got msimi response from", message.candidate, len(message.payload.sums)

        overlap = self.compute_overlap(message.payload._sum)
        self.add_taste_buddies([ActualTasteBuddy(overlap, time(), message.candidate)])

        _sums = [PossibleTasteBuddy(self.compute_overlap(_sum), time(), candidate_mid, message.candidate) for candidate_mid, _sum in message.payload.sums]
        if _sums:
            self.add_possible_taste_buddies(_sums)

        return overlap

    def compute_overlap(self, _sum):
        t1 = time()

        if self.encryption:
            _sum = paillier_decrypt(self.key, _sum)

        self.create_time_decryption += time() - t1

        return _sum

    def send_msimilarity_request(self, destination, identifier, payload):
        meta_request = self.get_meta_message(u"msimilarity-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=(identifier, payload.key_n, payload.preference_list, payload.global_vector))

        if self._dispersy._forward([request]):
            self.send_packet_size += len(request.packet)

            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "PSearchCommunity: sending msimilarity request to", destination, "containing", len(payload.preference_list), "hashes"
            return True
        return False

    def send_similarity_request(self, candidates, identifier, payload):
        # forward it to others
        meta_request = self.get_meta_message(u"similarity-request")
        request = meta_request.impl(authentication=(self.my_member,),
                            distribution=(self.global_time,),
                            payload=(identifier, payload.key_n, payload.preference_list, payload.global_vector))

        if self._dispersy._send(candidates, [request]):
            self.forward_packet_size += len(request.packet) * len(candidates)

            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "PSearchCommunity: sending similarity request to", map(str, candidates), "containing", len(payload.preference_list), "hashes"
            return True
        return False

    def on_similarity_request(self, messages, send_messages=True):
        t1 = time()

        for message in messages:
            user_vector = message.payload.preference_list
            global_vector = message.payload.global_vector
            my_vector = self.get_my_vector(global_vector)
            assert len(global_vector) == len(user_vector) and len(global_vector) == len(my_vector), "vector sizes not equal %d vs %d vs %d" % (len(global_vector), len(user_vector), len(my_vector))

            if self.encryption:
                _sum = 1l
                user_n2 = pow(message.payload.key_n, 2)

                for i, element in enumerate(user_vector):
                    if my_vector[i]:
                        _sum = paillier_add(_sum, element, user_n2)
            else:
                _sum = 0l
                for i, element in enumerate(user_vector):
                    if my_vector[i] and element:
                        _sum += 1

            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "PSearchCommunity: calculated sum", _sum

            if send_messages:
                meta_request = self.get_meta_message(u"similarity-response")
                response = meta_request.impl(authentication=(self.my_member,),
                                        distribution=(self.global_time,),
                                        destination=(message.candidate,),
                                        payload=(message.payload.identifier, _sum))

                self._dispersy._forward([response])
            else:
                self.receive_time_encryption += time() - t1
                return _sum

        self.receive_time_encryption += time() - t1

    def send_msimilarity_response(self, requesting_candidate, identifier, my_sum, received_sums):
        assert isinstance(identifier, int), type(identifier)
        received_sums = [(mid, payload._sum) for _, mid, payload in received_sums]

        meta_request = self.get_meta_message(u"msimilarity-response")
        response = meta_request.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,),
                                destination=(requesting_candidate,),
                                payload=(identifier, my_sum, received_sums))

        self._dispersy._forward([response])
        return len(response.packet)

    def create_global_vector(self):
        # 1. fetch my preferences
        global_vector = [long(preference) for preference in self._mypref_db.getMyPrefListInfohash(local=True) if preference]

        # 2. reduce/extend the vector in size
        if len(global_vector) > self.max_prefs:
            global_vector = sample(global_vector, self.max_prefs)

        elif len(global_vector) < self.max_prefs:
            global_vector += [0l] * (self.max_prefs - len(global_vector))

        assert len(global_vector) == self.max_prefs, 'vector sizes not equal'
        return global_vector

    def get_my_vector(self, global_vector, local=False):
        my_preferences = set([preference for preference in self._mypref_db.getMyPrefListInfohash(local=local) if preference])
        my_vector = [0l] * len(global_vector)
        for i, element in enumerate(global_vector):
            if element in my_preferences:
                my_vector[i] = 1l
        return my_vector

class HForwardCommunity(ForwardCommunity):

    def initiate_meta_messages(self):
        messages = ForwardCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"msimilarity-request", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), SimilarityRequest(), self.check_msimilarity_request, self.on_msimilarity_request))
        messages.append(Message(self, u"similarity-request", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), SimilarityRequest(), self.check_similarity_request, self.on_similarity_request))
        messages.append(Message(self, u"msimilarity-response", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), BundledEncryptedResponsePayload(), self.check_msimilarity_response, self.on_msimilarity_response))
        messages.append(Message(self, u"similarity-response", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedResponsePayload(), self.check_similarity_response, self.on_similarity_response))
        return messages

    def initiate_conversions(self):
        return [DefaultConversion(self), HSearchConversion(self)]

    def create_similarity_payload(self):
        t1 = time()

        myPreferences = [preference for preference in self._mypref_db.getMyPrefListInfohash() if preference]
        str_myPreferences = str(myPreferences)

        if self.my_preference_cache[0] == str_myPreferences:
            myPreferences = self.my_preference_cache[1]

        else:
            if len(myPreferences) > self.max_prefs:
                myPreferences = sample(myPreferences, self.max_prefs)
            shuffle(myPreferences)

            # 1. hash to limit size
            myPreferences = [hash_element(preference) for preference in myPreferences]

            # 2. convert to long
            myPreferences = [bytes_to_long(preference) for preference in myPreferences]

            # 3. encrypt
            if self.encryption:
                myPreferences = [rsa_encrypt(self.key, preference) for preference in myPreferences]

            self.my_preference_cache = [str_myPreferences, myPreferences]

        self.create_time_encryption += time() - t1

        if myPreferences:
            Payload = namedtuple('Payload', ['key_n', 'preference_list'])
            return Payload(long(self.key.n), myPreferences)

        return False

    def process_similarity_response(self, candidate, candidate_mid, payload):
        overlap = self.compute_overlap([payload.preference_list, payload.his_preference_list])
        self.add_taste_buddies([ActualTasteBuddy(overlap, time(), candidate)])
        return overlap

    def process_msimilarity_response(self, message):
        if DEBUG_VERBOSE:
            print >> sys.stderr, long(time()), "HSearchCommunity: got msimi response from", message.candidate, len(message.payload.bundled_responses)

        overlap = self.compute_overlap([message.payload.preference_list, message.payload.his_preference_list])
        self.add_taste_buddies([ActualTasteBuddy(overlap, time(), message.candidate)])

        possibles = []
        for candidate_mid, remote_response in message.payload.bundled_responses:
            possibles.append(PossibleTasteBuddy(self.compute_overlap(remote_response), time(), candidate_mid, message.candidate))

        self.add_possible_taste_buddies(possibles)
        return overlap

    def compute_overlap(self, lists):
        t1 = time()

        preference_list, his_preference_list = lists

        if self.encryption:
            preference_list = [rsa_decrypt(self.key, preference) for preference in preference_list]
        preference_list = [hash_element(preference) for preference in preference_list]

        assert all(isinstance(preference, str) for preference in preference_list)
        assert all(isinstance(his_preference, str) for his_preference in his_preference_list)

        overlap = 0
        for pref in preference_list:
            if pref in his_preference_list:
                overlap += 1

        self.create_time_decryption += time() - t1

        return overlap

    def send_msimilarity_request(self, destination, identifier, payload):
        meta_request = self.get_meta_message(u"msimilarity-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=(identifier, payload.key_n, payload.preference_list))

        if self._dispersy._forward([request]):
            self.send_packet_size += len(request.packet)

            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "HSearchCommunity: sending msimilarity request to", destination, "containing", len(payload.preference_list), "hashes"
            return True
        return False

    def send_similarity_request(self, candidates, identifier, payload):
        # forward it to others
        meta_request = self.get_meta_message(u"similarity-request")
        request = meta_request.impl(authentication=(self.my_member,),
                            distribution=(self.global_time,),
                            payload=(identifier, payload.key_n, payload.preference_list[:self.max_f_prefs]))

        if self._dispersy._send(candidates, [request]):
            self.forward_packet_size += len(request.packet) * len(candidates)

            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "PoliSearchCommunity: sending similarity request to", map(str, candidates), "containing", len(payload.preference_list), "hashes"

            return True
        return False

    def on_similarity_request(self, messages, send_messages=True):
        t1 = time()

        # 1. fetch my preferences
        myPreferences = [preference for preference in self._mypref_db.getMyPrefListInfohash(local=False) if preference]
        myListLen = len(myPreferences)

        # 2. use subset if we have to many preferences
        if myListLen > self.max_h_prefs:
            myPreferences = sample(myPreferences, self.max_h_prefs)

        # 3. hash to limit size
        myPreferences = [hash_element(preference) for preference in myPreferences]

        # 4. convert to long
        myPreferences = [bytes_to_long(preference) for preference in myPreferences]

        for message in messages:
            if self.encryption:
                # 5. construct a rsa key to encrypt my preferences
                his_n = message.payload.key_n
                fake_phi = his_n / 2
                compatible_key = rsa_compatible(his_n, fake_phi)

                # 6. encrypt hislist and mylist + hash mylist
                hisList = [rsa_encrypt(compatible_key, preference) for preference in message.payload.preference_list]
                myList = [hash_element(rsa_encrypt(compatible_key, preference)) for preference in myPreferences]

            else:
                hisList = message.payload.preference_list
                myList = [hash_element(preference) for preference in myPreferences]

            shuffle(hisList)
            shuffle(myList)
            if send_messages:
                # 5. create a messages, containing hislist encrypted with my compatible key and mylist only encrypted by the compatible key + hashed
                meta = self.get_meta_message(u"similarity-response")
                resp_message = meta.impl(authentication=(self._my_member,),
                                    distribution=(self.global_time,),
                                    destination=(message.candidate,),
                                    payload=(message.payload.identifier, hisList, myList))

                self._dispersy._forward([resp_message])

                if DEBUG_VERBOSE:
                    print >> sys.stderr, long(time()), "HSearchCommunity: sending similarity-response to", message.payload.identifier, message.candidate
            else:
                self.receive_time_encryption += time() - t1
                return hisList, myList

        self.receive_time_encryption += time() - t1

    def send_msimilarity_response(self, requesting_candidate, identifier, my_response, received_responses):
        assert isinstance(identifier, int), type(identifier)
        received_responses = [(mid, (payload.preference_list, payload.his_preference_list)) for _, mid, payload in received_responses]

        meta_request = self.get_meta_message(u"msimilarity-response")
        response = meta_request.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,),
                                destination=(requesting_candidate,),
                                payload=(identifier, my_response, received_responses))

        self._dispersy._forward([response])
        return len(response.packet)

class PoliForwardCommunity(ForwardCommunity):

    def init_key(self):
        return paillier_init(ForwardCommunity.init_key(self))

    def initiate_conversions(self):
        return [DefaultConversion(self), PoliSearchConversion(self)]

    def initiate_meta_messages(self):
        messages = ForwardCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"msimilarity-request", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PoliSimilarityRequest(), self.check_msimilarity_request, self.on_msimilarity_request))
        messages.append(Message(self, u"similarity-request", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PoliSimilarityRequest(), self.check_similarity_request, self.on_similarity_request))
        messages.append(Message(self, u"msimilarity-response", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedPoliResponsesPayload(), self.check_msimilarity_response, self.on_msimilarity_response))
        messages.append(Message(self, u"similarity-response", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedPoliResponsePayload(), self.check_similarity_response, self.on_similarity_response))
        return messages

    def create_similarity_payload(self):
        t1 = time()

        # 1. fetch my preferences
        myPreferences = [preference for preference in self._mypref_db.getMyPrefListInfohash() if preference]
        str_myPreferences = str(myPreferences)

        if self.my_preference_cache[0] == str_myPreferences:
            partitions = self.my_preference_cache[1]
        else:
            if len(myPreferences) > self.max_prefs:
                myPreferences = sample(myPreferences, self.max_prefs)
            shuffle(myPreferences)

            # convert our infohashes to 40 bit long
            bitmask = (2 ** 40) - 1
            myPreferences = [long(md5(str(infohash)).hexdigest(), 16) & bitmask for infohash in myPreferences]

            # partition the infohashes
            partitionmask = (2 ** 32) - 1
            myPreferences = [(int(val >> 32), val & partitionmask) for val in myPreferences]

            partitions = {}
            for partition, g in groupby(myPreferences, lambda x: x[0]):
                values = [value for _, value in list(g)]
                coeffs = compute_coeff(values)

                if self.encryption:
                    coeffs = [paillier_encrypt(self.key, coeff) for coeff in coeffs]
                else:
                    coeffs = [long(coeff) for coeff in coeffs]

                partitions[partition] = coeffs

            self.my_preference_cache = [str_myPreferences, partitions]

        self.create_time_encryption += time() - t1

        if partitions:
            Payload = namedtuple('Payload', ['key_n', 'key_g', 'coefficients'])
            return Payload(long(self.key.n), 0l if self.psi_mode == PSI_CARDINALITY else long(self.key.g), partitions)
        return False

    def process_similarity_response(self, candidate, candidate_mid, payload):
        if DEBUG_VERBOSE:
            print >> sys.stderr, long(time()), "PoliSearchCommunity: got simi response from", candidate, payload.identifier

        overlap = self.compute_overlap(payload.my_response)
        self.add_taste_buddies([ActualTasteBuddy(overlap, time(), candidate)])
        return overlap

    def process_msimilarity_response(self, message):
        if DEBUG_VERBOSE:
            print >> sys.stderr, long(time()), "PoliSearchCommunity: got msimi response from", message.candidate, len(message.payload.bundled_responses)

        overlap = self.compute_overlap(message.payload.my_response)
        self.add_taste_buddies([ActualTasteBuddy(overlap, time(), message.candidate)])

        possibles = []
        for candidate_mid, remote_response in message.payload.bundled_responses:
            possibles.append(PossibleTasteBuddy(self.compute_overlap(remote_response), time(), candidate_mid, message.candidate))

        self.add_possible_taste_buddies(possibles)
        return overlap

    def compute_overlap(self, evaluated_polynomial):
        if DEBUG_VERBOSE:
            print >> sys.stderr, long(time()), "PoliSearchCommunity: determining overlap", evaluated_polynomial

        t1 = time()

        decrypted_values = []
        if self.encryption:
            for py in evaluated_polynomial:
                decrypted_values.append(paillier_decrypt(self.key, py))
        else:
            decrypted_values = evaluated_polynomial

        self.create_time_decryption += time() - t1

        if self.psi_mode == PSI_CARDINALITY:
            overlap = sum(1 if value == 0 else 0 for value in decrypted_values)

        elif self.psi_mode == PSI_OVERLAP:
            bitmask = (2 ** 32) - 1
            myPreferences = set([preference for preference in self._mypref_db.getMyPrefListInfohash() if preference])
            myPreferences = dict([(long(md5(str(preference)).hexdigest(), 16) & bitmask, preference) for preference in myPreferences])

            overlap = [myPreferences[value] for value in decrypted_values if value in myPreferences]

        else:
            MAX_128 = (2 ** 129) - 1
            overlap = [value for value in decrypted_values if value < MAX_128]

            if all(value == overlap[0] for value in overlap):
                aes_key = overlap[0]
                overlap = len(overlap)

                assert aes_key == 42, [aes_key, 42]

        return overlap

    def send_msimilarity_request(self, destination, identifier, payload):
        meta_request = self.get_meta_message(u"msimilarity-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=(identifier, payload.key_n, payload.key_g, payload.coefficients))

        if self._dispersy._forward([request]):
            self.send_packet_size += len(request.packet)

            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "PoliSearchCommunity: sending msimilarity request to", destination, "containing", len(payload.coefficients), "partitions and", sum(len(coeffs) for coeffs in payload.coefficients.itervalues()), "coefficients"

            return True
        return False

    def send_similarity_request(self, candidates, identifier, payload):
        coefficients = payload.coefficients.copy()
        if self.max_f_prefs != self.max_prefs:
            # modify the coefficients to at most forward max_f_prefs coefficients
            new_coefficients = {}
            while len(coefficients.keys()) > 0 and sum(len(coeffs) - 1 for coeffs in new_coefficients.itervalues()) < self.max_f_prefs:
                partition = choice(coefficients.keys())
                new_coefficients[partition] = coefficients[partition]
                del coefficients[partition]

            coefficients = new_coefficients

        # forward it to others
        meta_request = self.get_meta_message(u"similarity-request")
        request = meta_request.impl(authentication=(self.my_member,),
                            distribution=(self.global_time,),
                            payload=(identifier, payload.key_n, payload.key_g, coefficients))

        if self._dispersy._send(candidates, [request]):
            self.forward_packet_size += len(request.packet) * len(candidates)

            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "PoliSearchCommunity: sending similarity request to", map(str, candidates), "containing", len(coefficients), "partitions and", sum(len(coeffs) for coeffs in coefficients.itervalues()), "coefficients"
            return True
        return False

    def on_similarity_request(self, messages, send_messages=True):
        t1 = time()

        # 1. fetch my preferences
        myPreferences = [preference for preference in self._mypref_db.getMyPrefListInfohash(local=False) if preference]

        # 2. partition the preferences
        # convert our infohashes to 40 bit long
        bitmask = (2 ** 40) - 1
        myPreferences = [long(md5(str(infohash)).hexdigest(), 16) & bitmask for infohash in myPreferences]

        # partition the infohashes
        partitionmask = (2 ** 32) - 1
        myPreferences = [(int(val >> 32), val & partitionmask) for val in myPreferences]

        for message in messages:
            _myPreferences = [(partition, val) for partition, val in myPreferences if partition in message.payload.coefficients]

            if self.psi_mode == PSI_AES:
                # generate 128 bit session key
                aes_key = StrongRandom().getrandbits(128)
                aes_key = 42l

            results = []
            if self.encryption:
                user_n2 = pow(message.payload.key_n, 2)
                for partition, val in _myPreferences:
                    py = paillier_polyval(message.payload.coefficients[partition], val, user_n2)
                    py = paillier_multiply(py, randint(0, 2 ** self.key.size), user_n2)
                    if self.psi_mode == PSI_OVERLAP:
                        py = paillier_add_unenc(py, val, message.payload.key_g, user_n2)
                    elif self.psi_mode == PSI_AES:
                        py = paillier_add_unenc(py, aes_key, message.payload.key_g, user_n2)
                    results.append(py)
            else:
                for partition, val in _myPreferences:
                    py = polyval(message.payload.coefficients[partition], val)
                    py = py * randint(0, 2 ** self.key.size)
                    if self.psi_mode == PSI_OVERLAP:
                        py += val
                    elif self.psi_mode == PSI_AES:
                        py += aes_key
                    results.append(py)

            if len(results) > self.max_prefs:
                results = sample(results, self.max_prefs)
            else:
                shuffle(results)

            if send_messages:
                # 4. create a messages, containing the py values
                meta = self.get_meta_message(u"similarity-response")
                resp_message = meta.impl(authentication=(self._my_member,),
                                    distribution=(self.global_time,),
                                    destination=(message.candidate,),
                                    payload=(message.payload.identifier, results))

                self._dispersy._forward([resp_message])
                self.reply_packet_size += len(resp_message.packet)

                if DEBUG_VERBOSE:
                    print >> sys.stderr, long(time()), "PoliSearchCommunity: sending similarity-response to", message.payload.identifier, message.candidate, results
            else:
                self.receive_time_encryption += time() - t1
                return results

        self.receive_time_encryption += time() - t1

    def send_msimilarity_response(self, requesting_candidate, identifier, my_response, received_responses):
        assert isinstance(identifier, int), type(identifier)
        received_responses = [(mid, payload.my_response) for _, mid, payload in received_responses]

        meta_request = self.get_meta_message(u"msimilarity-response")
        response = meta_request.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,),
                                destination=(requesting_candidate,),
                                payload=(identifier, my_response, received_responses))

        self._dispersy._forward([response])
        return len(response.packet)

    def get_most_similar(self, candidate):
        if self.psi_mode == PSI_CARDINALITY:
            return ForwardCommunity.get_most_similar(self, candidate)

        ctb = self.is_taste_buddy(candidate)
        if ctb and ctb.overlap:
            # see which peer i havn't made a connection to/have fewest connections with
            connections = defaultdict(int)
            for keyhash in ctb.overlap:
                connections[keyhash] += 1

            for tb in self.yield_taste_buddies(candidate):
                for keyhash in tb.overlap:
                    if keyhash in connections:
                        connections[keyhash] += 1

            ckeys = connections.keys()
            ckeys.sort(cmp=lambda a, b: cmp(connections[a], connections[b]))
            return candidate, long_to_bytes(ckeys[0], 20)

        return candidate, None

class Das4DBStub():
    def __init__(self, dispersy):
        self._dispersy = dispersy

        self.myPreferences = set()
        self.myTestPreferences = set()

        try:
            # python 2.7 only...
            from collections import OrderedDict
        except ImportError:
            from python27_ordereddict import OrderedDict

        self.id2category = {1:u''}

    def addMyPreference(self, preference, data):
        assert isinstance(preference, long), type(preference)
        self.myPreferences.add(preference)

    def addTestPreference(self, preference):
        assert isinstance(preference, long), type(preference)
        self.myTestPreferences.add(preference)

    def getMyPrefListInfohash(self, limit=None, local=True):
        preferences = self.myPreferences
        if not local:
            preferences = preferences | self.myTestPreferences
        preferences = list(preferences)

        if limit:
            return preferences[:limit]
        return preferences
