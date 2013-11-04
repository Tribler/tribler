# Written by Niels Zeilemaker
import sys
from os import path
from time import time
from random import sample, randint, shuffle, random, choice
from Crypto.Util.number import bytes_to_long, long_to_bytes
from math import ceil
from hashlib import md5
from itertools import groupby

from Tribler.dispersy.authentication import MemberAuthentication, \
    NoAuthentication
from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME, \
    WalkCandidate, BootstrapCandidate, Candidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination, Destination
from Tribler.dispersy.dispersy import IntroductionRequestCache
from Tribler.dispersy.dispersydatabase import DispersyDatabase
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.member import DummyMember, Member
from Tribler.dispersy.message import Message, DelayMessageByProof, DropMessage
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.requestcache import Cache
from Tribler.dispersy.script import assert_

from payload import *
from conversion import SemanticConversion, PSearchConversion, \
    HSearchConversion, PoliSearchConversion

from paillier import paillier_add, paillier_init, paillier_encrypt, paillier_decrypt, \
    paillier_polyval, paillier_multiply, paillier_add_unenc
from rsa import rsa_init, rsa_encrypt, rsa_decrypt, rsa_compatible, hash_element
from polycreate import compute_coeff, polyval
from collections import namedtuple

DEBUG = False
DEBUG_VERBOSE = False
ENCRYPTION = True
PING_INTERVAL = (CANDIDATE_WALK_LIFETIME - 5.0) / 4

class TasteBuddy():
    def __init__(self, overlap, timestamp, candidate):
        self.overlap = overlap
        self.timestamp = timestamp
        self.candidate = candidate

    def update_overlap(self, other):
        if isinstance(self.overlap, list):
            if len(other.overlap) > len(self.overlap):
                self.overlap = other.overlap
        else:
            self.overlap = max(self.overlap, other.overlap)

    def should_cache(self):
        return self.candidate.connection_type == u"public"

    def time_remaining(self):
        too_old = time() - CANDIDATE_WALK_LIFETIME - 5.0
        diff = self.timestamp - too_old
        return diff if diff > 0 else 0

    def __eq__(self, other):
        if isinstance(other, TasteBuddy):
            return self.candidate.sock_addr == other.candidate.sock_addr

        elif isinstance(other, Member):
            return other in self.candidate.get_members()

        elif isinstance(other, Candidate):
            return self.candidate == other

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
        return "TB_%d_%s_%s" % (self.timestamp, overlap, self.candidate)

class PossibleTasteBuddy(TasteBuddy):
    def __init__(self, overlap, timestamp, candidate_mid, received_from):
        TasteBuddy.__init__(self, overlap, timestamp, None)
        self.candidate_mid = candidate_mid
        self.received_from = received_from

    def __eq__(self, other):
        if isinstance(other, Candidate):
            return self.received_from.sock_addr == other.sock_addr

        return self.candidate_mid == other.candidate_mid

    def __str__(self):
        overlap = self.overlap
        if isinstance(self.overlap, list):
            overlap = len(overlap)
        return "PTB_%d_%d_%s_%s" % (self.timestamp, overlap, self.candidate_mid.encode("HEX"), self.received_from)

class ForwardCommunity():

    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION, forward_to=10, max_prefs=None, max_fprefs=None, max_taste_buddies=10):
        self.integrate_with_tribler = bool(integrate_with_tribler)
        self.encryption = bool(encryption)
        self.key = rsa_init()

        if not max_prefs:
            max_len = self.dispersy_sync_bloom_filter_bits
            max_prefs = max_len / self.key.size
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
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler, MyPreferenceDBHandler
            from Tribler.Core.CacheDB.Notifier import Notifier

            # tribler channelcast database
            self._torrent_db = TorrentDBHandler.getInstance()
            self._mypref_db = MyPreferenceDBHandler.getInstance()
            self._notifier = Notifier.getInstance()
            self._peercache = None
        else:
            self._mypref_db = self._torrent_db = self._peercache = Das4DBStub(self._dispersy)
            self._notifier = None

    def initiate_meta_messages(self):
        ori = self._meta_messages[u"dispersy-introduction-request"]
        self._disp_intro_handler = ori.handle_callback

        new = Message(self, ori.name, ori.authentication, ori.resolution, ori.distribution, ori.destination, ExtendedIntroPayload(), ori.check_callback, self.on_intro_request)
        self._meta_messages[u"dispersy-introduction-request"] = new

        return [Message(self, u"ping", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PingPayload(), self._dispersy._generic_timeline_check, self.on_ping),
                Message(self, u"pong", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PongPayload(), self.check_pong, self.on_pong)]

    def initiate_conversions(self):
        return [DefaultConversion(self), SemanticConversion(self)]

    def add_taste_buddies(self, new_taste_buddies):
        for new_taste_buddy in new_taste_buddies:
            for taste_buddy in self.taste_buddies:
                if new_taste_buddy == taste_buddy:
                    taste_buddy.update_overlap(new_taste_buddy)
                    new_taste_buddies.remove(new_taste_buddy)
                    break

            # new peer
            else:
                if len(self.taste_buddies) < self.max_taste_buddies or new_taste_buddy > self.taste_buddies[-1]:
                    self.taste_buddies.append(new_taste_buddy)
                    self.dispersy.callback.persistent_register(u"send_ping_requests", self.create_ping_requests, delay=new_taste_buddy.time_remaining() - 5.0)

                # if we have any similarity, cache peer
                if new_taste_buddy.overlap and new_taste_buddy.should_cache():
                    self._peercache.add_peer(new_taste_buddy.overlap, new_taste_buddy.candidate.sock_addr)

        self.taste_buddies.sort(reverse=True)
        self.taste_buddies = self.taste_buddies[:self.max_taste_buddies]

        if DEBUG_VERBOSE:
            print >> sys.stderr, long(time()), "SearchCommunity: current tastebuddy list", len(self.taste_buddies), map(str, self.taste_buddies)
        elif DEBUG:
            print >> sys.stderr, long(time()), "SearchCommunity: current tastebuddy list", len(self.taste_buddies)

    def yield_taste_buddies(self, ignore_candidate=None):
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
        candidate_mids = set(candidate.get_members())
        for tb in self.yield_taste_buddies_candidates():
            tb_mids = set(tb.get_members())
            if tb_mids & candidate_mids:
                return tb

    def is_taste_buddy_mid(self, mid):
        for tb in self.yield_taste_buddies_candidates():
            if mid in [member.mid for member in tb.get_members()]:
                return True

    def is_taste_buddy_sock(self, sock_addr):
        for tb in self.yield_taste_buddies_candidates():
            if tb.sock_addr == sock_addr:
                return True

    def reset_taste_buddy(self, candidate):
        for taste_buddy in self.taste_buddies:
            if taste_buddy == candidate:
                taste_buddy.timestamp = time()
                break

    def remove_taste_buddy(self, candidate):
        for taste_buddy in self.taste_buddies:
            if taste_buddy == candidate:
                self.taste_buddies.remove(taste_buddy)
                break

    def add_possible_taste_buddies(self, possibles):
        if __debug__:
            for possible in possibles:
                assert isinstance(possible, PossibleTasteBuddy), type(possible)

        low_sim = self.get_least_similar_tb()
        for new_possible in possibles:
            if new_possible <= low_sim:
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

        low_sim = self.get_least_similar_tb()
        for i in range(len(self.possible_taste_buddies) - 1, -1, -1):
            to_low_sim = self.possible_taste_buddies[i] <= low_sim
            to_old = self.possible_taste_buddies[i].time_remaining() == 0
            is_tb = self.is_taste_buddy_mid(self.possible_taste_buddies[i].candidate_mid)

            if to_low_sim or to_old or is_tb:
                if DEBUG:
                    print >> sys.stderr, long(time()), "ForwardCommunity: removing possible tastebuddy", long(time()), to_low_sim, to_old, is_tb, self.possible_taste_buddies[i]
                self.possible_taste_buddies.pop(i)

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
    def connect_to_peercache(self, nr=10):
        payload = self.create_similarity_payload()
        if payload:
            peers = self._peercache.get_peers()[:nr]

            def attempt_to_connect(candidate, attempts):
                while not self.is_taste_buddy_sock(candidate.sock_addr) and attempts:
                    self.create_similarity_request(candidate, payload)

                    yield IntroductionRequestCache.timeout_delay + IntroductionRequestCache.cleanup_delay
                    attempts -= 1

            for i, sock_addr in enumerate(peers):
                candidate = self.get_candidate(sock_addr, replace=False)
                if not candidate:
                    candidate = self.create_candidate(sock_addr, False, sock_addr, sock_addr, u"unknown")

                self.dispersy.callback.register(attempt_to_connect, args=(candidate, 10), delay=0.005 * i)

    def dispersy_get_introduce_candidate(self, exclude_candidate=None):
        if exclude_candidate:
            if exclude_candidate in self.requested_introductions:
                intro_me_candidate = self.requested_introductions[exclude_candidate]
                del self.requested_introductions[exclude_candidate]
                return intro_me_candidate

        return Community.dispersy_get_introduce_candidate(self, exclude_candidate)

    class SimilarityAttempt(Cache):
        timeout_delay = 10.5
        cleanup_delay = 0.0

        def __init__(self, community, requested_candidate):
            self.community = community
            self.requested_candidate = requested_candidate

        def on_timeout(self):
            self.community.send_introduction_request(self.requested_candidate)

    def create_introduction_request(self, destination, allow_sync):
        send = False
        if not isinstance(destination, BootstrapCandidate) and not self.is_taste_buddy(destination) and not self.has_possible_taste_buddies(destination) and allow_sync:
            send = self.create_msimilarity_request(destination)

        if not send:
            self.send_introduction_request(destination)

    def create_similarity_payload(self):
        raise NotImplementedError()

    def process_similarity_response(self, candidate_mid, response):
        raise NotImplementedError()
    def process_msimilarity_response(self, message):
        raise NotImplementedError()

    def create_msimilarity_request(self, destination):
        identifier = self._dispersy.request_cache.claim(ForwardCommunity.SimilarityAttempt(self, destination))

        payload = self.create_similarity_payload()
        if payload:
            self.send_msimilarity_request(destination, identifier, payload)
            return True

        self._dispersy.request_cache.pop(identifier, ForwardCommunity.SimilarityAttempt)
        return False

    def send_msimilarity_request(self, destination, indentifier, payload):
        raise NotImplementedError()

    class MSimilarityRequest(Cache):
        timeout_delay = 7.0
        cleanup_delay = 0.0

        def __init__(self, community, requesting_candidate, requested_candidates):
            self.community = community

            self.requesting_candidate = requesting_candidate
            self.requested_candidates = requested_candidates

            self.received_candidates = set()
            self.received_lists = []
            self.isProcessed = False

        def add_response(self, candidate, member, response):
            if candidate:
                if self.did_request(candidate):

                    # we need to associated this candidate with this mid, apparently this is only done when receiving an induction response
                    candidate.associate(member)

                    if candidate not in self.received_candidates:
                        self.received_candidates.add(candidate)
                        self.received_lists.append((candidate, member.mid, response))
            else:
                self.my_response = response

        def did_request(self, candidate):
            if candidate:
                return candidate in self.requested_candidates
            return False

        def is_complete(self):
            return len(self.received_lists) == len(self.requested_candidates)

        def process(self):
            if not self.isProcessed:
                self.isProcessed = True

                if self.requesting_candidate:
                    if DEBUG_VERBOSE:
                        print >> sys.stderr, long(time()), "ForwardCommunity: processed MSimilarityRequest send msimilarity-response to", self.requesting_candidate

                    self.community._dispersy.request_cache.pop(self.identifier, ForwardCommunity.MSimilarityRequest)
                    return self.community.send_msimilarity_response(self.requesting_candidate, self.identifier, self.my_response, self.received_lists)

                for response in self.received_lists:
                    self.community.process_similarity_response(response[0], response[1], response[2])
                return 0

        def on_timeout(self):
            if not self.isProcessed:
                if DEBUG:
                    print >> sys.stderr, long(time()), "ForwardCommunity: timeout MSimilarityRequest", self.identifier, len(self.received_lists), len(self.requested_candidates), str(self.requested_candidates[0])

                self.process()

    def check_msimilarity_request(self, messages):
        for message in messages:
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue

            if self._dispersy.request_cache.has(message.payload.identifier, ForwardCommunity.SimilarityAttempt):
                yield DropMessage(message, "send similarity attempt to myself?")
                continue

            yield message

    def on_msimilarity_request(self, messages):
        for message in messages:
            # get candidates to forward requests to, excluding the requesting peer
            candidates = self.get_connections(self.forward_to, message.candidate)

            # create a register similarity request
            request = ForwardCommunity.MSimilarityRequest(self, message.candidate, candidates)
            # add local response
            request.add_response(None, None, self.on_similarity_request([message], False))

            self._dispersy.request_cache.set(message.payload.identifier, request)
            if candidates:
                # forward it to others
                self.send_similarity_request(candidates, message.payload.identifier, message.payload)

            if request.is_complete():
                request.process()

    def create_similarity_request(self, destination, payload):
        identifier = self._dispersy.request_cache.claim(ForwardCommunity.MSimilarityRequest(self, None, [destination]))

        if DEBUG:
            print >> sys.stderr, long(time()), "SearchCommunity: sending similarity request to", str(destination), identifier
        self.send_similarity_request([destination], identifier, payload)

    def send_similarity_request(self, candidates, identifier, payload):
        raise NotImplementedError()

    def check_similarity_request(self, messages):
        for message in messages:
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue

            if self._dispersy.request_cache.has(message.payload.identifier, ForwardCommunity.SimilarityAttempt):
                yield DropMessage(message, "got similarity request issued by myself?")
                continue

            if self._dispersy.request_cache.has(message.payload.identifier, ForwardCommunity.MSimilarityRequest):
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

            request = self._dispersy.request_cache.get(message.payload.identifier, ForwardCommunity.MSimilarityRequest)
            if not request:
                yield DropMessage(message, "unknown identifier")
                continue

            if not request.did_request(message.candidate):
                yield DropMessage(message, "did not send request to this candidate")
                continue

            yield message

    def on_similarity_response(self, messages):
        for message in messages:
            request = self._dispersy.request_cache.get(message.payload.identifier, ForwardCommunity.MSimilarityRequest)
            if request:
                request.add_response(message.candidate, message.authentication.member, message.payload)
                if request.is_complete():
                    self.reply_packet_size += request.process()

    def send_msimilarity_response(self, requesting_candidate, identifier, my_response, received_responses):
        raise NotImplementedError()

    def on_msimilarity_response(self, messages):
        for message in messages:
            request = self._dispersy.request_cache.pop(message.payload.identifier, ForwardCommunity.SimilarityAttempt)
            if request:
                # replace message.candidate with WalkCandidate
                # TODO: this seems to be a bit dodgy
                message._candidate = request.requested_candidate

                self.process_msimilarity_response(message)

                destination, introduce_me_to = self.get_most_similar(message.candidate)
                self.send_introduction_request(destination, introduce_me_to)

                if DEBUG and introduce_me_to:
                    print >> sys.stderr, long(time()), "ForwardCommunity: asking candidate %s to introduce me to %s after receiving similarities from %s" % (destination, introduce_me_to.encode("HEX"), message.candidate)

    def send_introduction_request(self, destination, introduce_me_to=None):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]
        assert not introduce_me_to or isinstance(introduce_me_to, str), type(introduce_me_to)

        self._dispersy.statistics.walk_attempt += 1
        destination.walk(time(), IntroductionRequestCache.timeout_delay)

        advice = True
        identifier = self._dispersy.request_cache.claim(IntroductionRequestCache(self, destination))
        payload = (destination.get_destination_address(self._dispersy._wan_address), self._dispersy._lan_address, self._dispersy._wan_address, advice, self._dispersy._connection_type, None, identifier, introduce_me_to)

        meta_request = self.get_meta_message(u"dispersy-introduction-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=payload)

        self._dispersy._forward([request])

    def on_intro_request(self, messages):
        for message in messages:
            if message.payload.introduce_me_to:
                candidate = self._dispersy.get_walkcandidate(message, self)
                self.requested_introductions[candidate] = introduce_me_to = self.get_candidate_mid(message.payload.introduce_me_to)

                if not introduce_me_to and DEBUG:
                    print >> sys.stderr, long(time()), long(time()), "Cannot create candidate for mid", message.payload.introduce_me_to

        self._disp_intro_handler(messages)

        if self._notifier:
            from Tribler.Core.simpledefs import NTFY_ACT_MEET, NTFY_ACTIVITIES, NTFY_INSERT
            for message in messages:
                self._notifier.notify(NTFY_ACTIVITIES, NTFY_INSERT, NTFY_ACT_MEET, "%s:%d" % message.candidate.sock_addr)

    class PingRequestCache(IntroductionRequestCache):
        cleanup_delay = 0.0

        def __init__(self, community, requested_candidates):
            IntroductionRequestCache.__init__(self, community, None)
            self.requested_candidates = requested_candidates
            self.received_candidates = set()

        def on_success(self, candidate):
            if self.did_request(candidate):
                self.received_candidates.add(candidate)

        def did_request(self, candidate):
            return candidate in self.requested_candidates

        def on_timeout(self):
            for candidate in self.requested_candidates:
                if candidate not in self.received_candidates:
                    if DEBUG:
                        print >> sys.stderr, long(time()), "ForwardCommunity: no response on ping, removing from taste_buddies", candidate
                    self.community.remove_taste_buddy(candidate)

    def create_ping_requests(self):
        while True:
            tbs = [tb.candidate for tb in self.yield_taste_buddies() if tb.time_remaining() < PING_INTERVAL]

            identifier = self._dispersy.request_cache.claim(ForwardCommunity.PingRequestCache(self, tbs))
            self._create_pingpong(u"ping", tbs, identifier)

            yield PING_INTERVAL

    def on_ping(self, messages):
        for message in messages:
            self._create_pingpong(u"pong", [message.candidate], message.payload.identifier)

            self.reset_taste_buddy(message.candidate)

    def check_pong(self, messages):
        for message in messages:
            request = self._dispersy.request_cache.get(message.payload.identifier, ForwardCommunity.PingRequestCache)
            if not request:
                yield DropMessage(message, "invalid response identifier")
                continue

            if not request.did_request(message.candidate):
                yield DropMessage(message, "did not send ping to this candidate")
                continue

            yield message

    def on_pong(self, messages):
        for message in messages:
            request = self._dispersy.request_cache.pop(message.payload.identifier, ForwardCommunity.PingRequestCache)
            request.on_success(message.candidate)

            self.reset_taste_buddy(request.candidate)

    def _create_pingpong(self, meta_name, candidates, identifier=None):
        meta = self.get_meta_message(meta_name)
        message = meta.impl(distribution=(self.global_time,), payload=(identifier,))
        self._dispersy._send(candidates, [message])

        if True or DEBUG:
            print >> sys.stderr, long(time()), "ForwardCommunity: send", meta_name, "to", len(candidates), "candidates:", map(str, candidates)

class PForwardCommunity(ForwardCommunity):

    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION, forward_to=10, max_prefs=None, max_fprefs=None, max_taste_buddies=10):
        ForwardCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption, forward_to, max_prefs, max_fprefs, max_taste_buddies)

        self.key = paillier_init(self.key)

    def initiate_meta_messages(self):
        messages = ForwardCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"msimilarity-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedVectorPayload(), self.check_msimilarity_request, self.on_msimilarity_request))
        messages.append(Message(self, u"similarity-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedVectorPayload(), self.check_similarity_request, self.on_similarity_request))
        messages.append(Message(self, u"msimilarity-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedSumsPayload(), self._dispersy._generic_timeline_check, self.on_msimilarity_response))
        messages.append(Message(self, u"similarity-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedSumPayload(), self.check_similarity_response, self.on_similarity_response))
        return messages

    def initiate_conversions(self):
        return [DefaultConversion(self), PSearchConversion(self)]

    def create_similarity_payload(self):
        global_vector = self.create_global_vector()

        str_global_vector = str(global_vector)
        if self.my_preference_cache[0] == str_global_vector:
            encrypted_vector = self.my_preference_cache[1]
        else:
            my_vector = self.get_my_vector(global_vector, local=True)
            if self.encryption:

                t1 = time()
                encrypted_vector = []
                for element in my_vector:
                    cipher = paillier_encrypt(self.key, element)
                    encrypted_vector.append(cipher)

                self.create_time_encryption += time() - t1
            else:
                encrypted_vector = my_vector

            self.my_preference_cache = [str_global_vector, encrypted_vector]

        if encrypted_vector:
            Payload = namedtuple('Payload', ['key_n', 'preference_list', 'global_vector'])
            return Payload(self.key.n, encrypted_vector, global_vector)
        return False

    def process_similarity_response(self, candidate, candidate_mid, payload):
        _sum = self.compute_overlap(payload._sum)
        self.add_taste_buddies([TasteBuddy(_sum, time(), candidate)])

    def process_msimilarity_response(self, message):
        if DEBUG_VERBOSE:
            print >> sys.stderr, long(time()), "PSearchCommunity: received sums", message.payload._sum

        self.add_taste_buddies([TasteBuddy(self.compute_overlap(message.payload._sum), time(), message.candidate)])

        _sums = [PossibleTasteBuddy(self.compute_overlap(_sum), time(), candidate_mid, message.candidate) for candidate_mid, _sum in message.payload.sums]
        if _sums:
            self.add_possible_taste_buddies(_sums)

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

        self._dispersy._forward([request])
        self.send_packet_size += len(request.packet)

    def send_similarity_request(self, candidates, identifier, payload):
        # forward it to others
        meta_request = self.get_meta_message(u"similarity-request")
        request = meta_request.impl(authentication=(self.my_member,),
                            distribution=(self.global_time,),
                            payload=(identifier, payload.key_n, payload.preference_list, payload.global_vector))

        if self._dispersy._send(candidates, [request]):
            self.forward_packet_size += len(request.packet) * len(candidates)
            return True
        return False

    def on_similarity_request(self, messages, send_messages=True):
        for message in messages:
            user_vector = message.payload.preference_list
            global_vector = message.payload.global_vector
            my_vector = self.get_my_vector(global_vector)
            assert len(global_vector) == len(user_vector) and len(global_vector) == len(my_vector), "vector sizes not equal %d vs %d vs %d" % (len(global_vector), len(user_vector), len(my_vector))

            t1 = time()
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
            self.receive_time_encryption += time() - t1

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
                return _sum

    def send_msimilarity_response(self, requesting_candidate, identifier, my_sum, received_sums):
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

        assert_(len(global_vector) == self.max_prefs, 'vector sizes not equal')
        return global_vector

    def get_my_vector(self, global_vector, local=False):
        my_preferences = set([long(preference) for preference in self._mypref_db.getMyPrefListInfohash(local=local) if preference])
        my_vector = [0l] * len(global_vector)
        for i, element in enumerate(global_vector):
            if element in my_preferences:
                my_vector[i] = 1l
        return my_vector

class HForwardCommunity(ForwardCommunity):

    def initiate_meta_messages(self):
        messages = ForwardCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"msimilarity-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), SimilarityRequest(), self.check_msimilarity_request, self.on_msimilarity_request))
        messages.append(Message(self, u"similarity-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), SimilarityRequest(), self.check_similarity_request, self.on_similarity_request))
        messages.append(Message(self, u"msimilarity-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), BundledEncryptedResponsePayload(), self._dispersy._generic_timeline_check, self.on_msimilarity_response))
        messages.append(Message(self, u"similarity-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedResponsePayload(), self.check_similarity_response, self.on_similarity_response))
        return messages

    def initiate_conversions(self):
        return [DefaultConversion(self), HSearchConversion(self)]

    def create_similarity_payload(self):
        myPreferences = [preference for preference in self._mypref_db.getMyPrefListInfohash() if preference]
        str_myPreferences = str(myPreferences)

        if self.my_preference_cache[0] == str_myPreferences:
            myPreferences = self.my_preference_cache[1]
        else:
            if len(myPreferences) > self.max_prefs:
                myPreferences = sample(myPreferences, self.max_prefs)
            shuffle(myPreferences)

            myPreferences = [bytes_to_long(infohash) for infohash in myPreferences]
            if self.encryption:
                t1 = time()
                myPreferences = [rsa_encrypt(self.key, infohash) for infohash in myPreferences]
                self.create_time_encryption += time() - t1

            self.my_preference_cache = [str_myPreferences, myPreferences]

        if myPreferences:
            Payload = namedtuple('Payload', ['key_n', 'preference_list'])
            return Payload(long(self.key.n), myPreferences)

        return False

    def process_similarity_response(self, candidate, candidate_mid, payload):
        overlap = self.compute_overlap([payload.preference_list, payload.his_preference_list])
        self.add_taste_buddies([TasteBuddy(overlap, time(), candidate)])

    def process_msimilarity_response(self, message):
        if DEBUG_VERBOSE:
            print >> sys.stderr, long(time()), "HSearchCommunity: got msimi response from", message.candidate, len(message.payload.bundled_responses)

        overlap = self.compute_overlap([message.payload.preference_list, message.payload.his_preference_list])
        self.add_taste_buddies([TasteBuddy(overlap, time(), message.candidate)])

        possibles = []
        for candidate_mid, remote_response in message.payload.bundled_responses:
            possibles.append(PossibleTasteBuddy(self.compute_overlap(remote_response), time(), candidate_mid, message.candidate))

        self.add_possible_taste_buddies(possibles)

    def compute_overlap(self, lists):
        preference_list, his_preference_list = lists

        t1 = time()

        if self.encryption:
            myList = [hash_element(rsa_decrypt(self.key, infohash)) for infohash in preference_list]
        else:
            myList = [long_to_bytes(infohash) for infohash in preference_list]

        assert all(len(infohash) == 20 for infohash in myList)

        overlap = 0
        for pref in myList:
            if pref in his_preference_list:
                overlap += 1

        self.create_time_decryption += time() - t1

        return overlap

    def send_msimilarity_request(self, destination, identifier, payload):
        if DEBUG_VERBOSE:
            print >> sys.stderr, long(time()), "HSearchCommunity: sending similarity request to", destination, "containing", len(payload.preference_list), "hashes"

        meta_request = self.get_meta_message(u"msimilarity-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=(identifier, payload.key_n, payload.preference_list))

        self._dispersy._forward([request])

    def send_similarity_request(self, candidates, identifier, payload):
        # forward it to others
        meta_request = self.get_meta_message(u"similarity-request")
        request = meta_request.impl(authentication=(self.my_member,),
                            distribution=(self.global_time,),
                            payload=(identifier, payload.key_n, payload.preference_list[:self.max_f_prefs]))

        if self._dispersy._send(candidates, [request]):
            self.forward_packet_size += len(request.packet) * len(candidates)
            return True
        return False

    def on_similarity_request(self, messages, send_messages=True):
        # 1. fetch my preferences
        myPreferences = [preference for preference in self._mypref_db.getMyPrefListInfohash(local=False) if preference]
        myListLen = len(myPreferences)

        # 2. use subset if we have to many preferences
        if myListLen > self.max_h_prefs:
            myPreferences = sample(myPreferences, self.max_h_prefs)

        if self.encryption:
            myPreferences = [bytes_to_long(preference) for preference in myPreferences]

        for message in messages:
            if self.encryption:
                t1 = time()

                # 3. construct a rsa key to encrypt my preferences
                his_n = message.payload.key_n
                fake_phi = his_n / 2
                compatible_key = rsa_compatible(his_n, fake_phi)

                # 4. encrypt hislist and mylist + hash mylist
                hisList = [rsa_encrypt(compatible_key, infohash) for infohash in message.payload.preference_list]
                myList = [hash_element(rsa_encrypt(compatible_key, infohash)) for infohash in myPreferences]

                self.receive_time_encryption += time() - t1
            else:
                hisList = message.payload.preference_list
                myList = myPreferences

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
                return hisList, myList

    def send_msimilarity_response(self, requesting_candidate, identifier, my_response, received_responses):
        received_responses = [(mid, (payload.preference_list, payload.his_preference_list)) for _, mid, payload in received_responses]

        meta_request = self.get_meta_message(u"msimilarity-response")
        response = meta_request.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,),
                                destination=(requesting_candidate,),
                                payload=(identifier, my_response, received_responses))

        self._dispersy._forward([response])
        return len(response.packet)

class PoliForwardCommunity(ForwardCommunity):

    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION, forward_to=10, max_prefs=None, max_fprefs=None, max_taste_buddies=10, use_cardinality=True):
        ForwardCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption, forward_to, max_prefs, max_fprefs, max_taste_buddies)
        self.key = paillier_init(self.key)
        self.use_cardinality = use_cardinality

    def initiate_conversions(self):
        return [DefaultConversion(self), PoliSearchConversion(self)]

    def initiate_meta_messages(self):
        messages = ForwardCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"msimilarity-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), PoliSimilarityRequest(), self.check_msimilarity_request, self.on_msimilarity_request))
        messages.append(Message(self, u"similarity-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), PoliSimilarityRequest(), self.check_similarity_request, self.on_similarity_request))
        messages.append(Message(self, u"msimilarity-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedPoliResponsesPayload(), self._dispersy._generic_timeline_check, self.on_msimilarity_response))
        messages.append(Message(self, u"similarity-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedPoliResponsePayload(), self.check_similarity_response, self.on_similarity_response))
        return messages

    def create_similarity_payload(self):
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
            myPreferences = [(val >> 32, val & partitionmask) for val in myPreferences]

            partitions = {}
            t1 = time()
            for partition, g in groupby(myPreferences, lambda x: x[0]):
                values = [value for _, value in list(g)]
                coeffs = compute_coeff(values)

                if self.encryption:
                    coeffs = [paillier_encrypt(self.key, coeff) for coeff in coeffs]

                partitions[partition] = coeffs

            self.create_time_encryption += time() - t1
            self.my_preference_cache = [str_myPreferences, partitions]

        if partitions:
            Payload = namedtuple('Payload', ['key_n', 'key_g', 'coefficients'])
            return Payload(long(self.key.n), long(self.key.g), partitions)
        return False

    def process_similarity_response(self, candidate, candidate_mid, payload):
        overlap = self.compute_overlap(payload.my_response)
        self.add_taste_buddies([TasteBuddy(overlap, time(), candidate)])

    def process_msimilarity_response(self, message):
        if DEBUG_VERBOSE:
            print >> sys.stderr, long(time()), "PoliSearchCommunity: got msimi response from", message.candidate, len(message.payload.bundled_responses)

        overlap = self.compute_overlap(message.payload.my_response)
        self.add_taste_buddies([TasteBuddy(overlap, time(), message.candidate)])

        possibles = []
        for candidate_mid, remote_response in message.payload.bundled_responses:
            possibles.append(PossibleTasteBuddy(self.compute_overlap(remote_response), time(), candidate_mid, message.candidate))

        self.add_possible_taste_buddies(possibles)

    def compute_overlap(self, evaluated_polynomial):
        if self.use_cardinality:
            overlap = 0
            if self.encryption:
                t1 = time()
                for py in evaluated_polynomial:
                    if paillier_decrypt(self.key, py) == 0:
                        overlap += 1
                self.create_time_decryption += time() - t1
            else:
                for py in evaluated_polynomial:
                    if py == 0:
                        overlap += 1

            return overlap

        bitmask = (2 ** 32) - 1
        myPreferences = set([preference for preference in self._mypref_db.getMyPrefListInfohash() if preference])
        myPreferences = [long(md5(str(infohash)).hexdigest(), 16) & bitmask for infohash in myPreferences]

        overlap = []
        if self.encryption:
            t1 = time()
            for py in evaluated_polynomial:
                py = paillier_decrypt(self.key, py)
                if py in myPreferences:
                    overlap.append(py)

            self.create_time_decryption += time() - t1
        else:
            for py in evaluated_polynomial:
                if py in myPreferences:
                    overlap.append(py)
        return overlap

    def send_msimilarity_request(self, destination, identifier, payload):
        if DEBUG_VERBOSE:
            print >> sys.stderr, long(time()), "PoliSearchCommunity: sending similarity request to", destination, "containing", len(payload.coefficients), "partitions and", sum(len(coeffs) for coeffs in payload.coefficients.itervalues()), "coefficients"

        meta_request = self.get_meta_message(u"msimilarity-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                distribution=(self.global_time,),
                                destination=(destination,),
                                payload=(identifier, payload.key_n, payload.key_g, payload.coefficients))

        self._dispersy._forward([request])
        self.send_packet_size += len(request.packet)

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
            return True
        return False

    def on_similarity_request(self, messages, send_messages=True):
        # 1. fetch my preferences
        myPreferences = [preference for preference in self._mypref_db.getMyPrefListInfohash(local=False) if preference]

        # 2. partition the preferences
        # convert our infohashes to 40 bit long
        bitmask = (2 ** 40) - 1
        myPreferences = [long(md5(str(infohash)).hexdigest(), 16) & bitmask for infohash in myPreferences]

        # partition the infohashes
        partitionmask = (2 ** 32) - 1
        myPreferences = [(val >> 32, val & partitionmask) for val in myPreferences]

        for message in messages:
            _myPreferences = [(partition, val) for partition, val in myPreferences if partition in message.payload.coefficients]

            results = []
            t1 = time()
            if self.encryption:
                user_n2 = pow(message.payload.key_n, 2)
                for partition, val in _myPreferences:
                    py = paillier_polyval(message.payload.coefficients[partition], val, user_n2)
                    py = paillier_multiply(py, randint(0, 2 ** 40), user_n2)
                    if not self.use_cardinality:
                        py = paillier_add_unenc(py, val, message.payload.key_g, user_n2)
                    results.append(py)
            else:
                for partition, val in _myPreferences:
                    py = polyval(message.payload.coefficients[partition], val)
                    py = py * randint(0, 2 ** 40)
                    if not self.use_cardinality:
                        py += val
                    results.append(py)

            self.receive_time_encryption += time() - t1

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
                    print >> sys.stderr, long(time()), "PoliSearchCommunity: sending similarity-response to", message.payload.identifier, message.candidate
            else:
                return results

    def send_msimilarity_response(self, requesting_candidate, identifier, my_response, received_responses):
        received_responses = [(mid, payload.my_response) for _, mid, payload in received_responses]

        meta_request = self.get_meta_message(u"msimilarity-response")
        response = meta_request.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,),
                                destination=(requesting_candidate,),
                                payload=(identifier, my_response, received_responses))

        self._dispersy._forward([response])
        return len(response.packet)

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

        self.myMegaCache = OrderedDict()
        self.id2category = {1:u''}

        self.peercache = {}

    def addMyPreference(self, torrent_id, data):
        infohash = str(torrent_id)
        self.myPreferences.add(infohash)

    def addTestPreference(self, torrent_id):
        infohash = str(torrent_id)
        self.myTestPreferences.add(infohash)

    def getMyPrefListInfohash(self, limit=None, local=True):
        preferences = self.myPreferences
        if not local:
            preferences = preferences | self.myTestPreferences
        preferences = list(preferences)

        if limit:
            return preferences[:limit]
        return preferences

    def add_peer(self, similarity, ipport):
        self.peercache[ipport] = similarity

    def get_peers(self):
        peers = self.peercache.items()
        peers.sort(cmp=lambda a, b: cmp(a[1], b[1]), reverse=True)

        return [ipport for ipport, _ in peers]
