# Written by Niels Zeilemaker
import sys
from os import path
from time import time
from random import sample, randint, shuffle, random, choice
from Crypto.Util.number import bytes_to_long, long_to_bytes
from math import ceil
from hashlib import md5
from itertools import groupby

from Tribler.dispersy.authentication import MemberAuthentication
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

from pallier import pallier_add, pallier_init, pallier_encrypt, pallier_decrypt, \
    pallier_polyval, pallier_multiply
from rsa import rsa_init, rsa_encrypt, rsa_decrypt, rsa_compatible, hash_element
from polycreate import compute_coeff, polyval

DEBUG = False
DEBUG_VERBOSE = False
ENCRYPTION = True
PING_INTERVAL = CANDIDATE_WALK_LIFETIME - 5.0

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

        return [Message(self, u"ping", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), PingPayload(), self._dispersy._generic_timeline_check, self.on_ping),
                Message(self, u"pong", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), PongPayload(), self.check_pong, self.on_pong)]

    def initiate_conversions(self):
        return [DefaultConversion(self), SemanticConversion(self)]

    def add_taste_buddies(self, new_taste_buddies):
        for new_tb_tuple in new_taste_buddies[:]:
            for tb_tuple in self.taste_buddies:
                if tb_tuple[-1].sock_addr == new_tb_tuple[-1].sock_addr:

                    # update similarity
                    tb_tuple[0] = max(new_tb_tuple[0], tb_tuple[0])
                    new_taste_buddies.remove(new_tb_tuple)
                    break

            # new peer
            else:
                if len(self.taste_buddies) < self.max_taste_buddies or new_tb_tuple[0] > self.taste_buddies[-1][0]:
                    self.taste_buddies.append(new_tb_tuple)
                    self.dispersy.callback.register(self.create_ping_request, args=(new_tb_tuple[-1],), delay=PING_INTERVAL)

                # if we have any similarity, cache peer
                if new_tb_tuple[0] and new_tb_tuple[-1].connection_type == u"public":
                    self._peercache.add_peer(new_tb_tuple[0], new_tb_tuple[-1].sock_addr)

        self.taste_buddies.sort(reverse=True)
        self.taste_buddies = self.taste_buddies[:self.max_taste_buddies]

        if DEBUG:
            print >> sys.stderr, long(time()), "SearchCommunity: current tastebuddy list", len(self.taste_buddies), self.taste_buddies

    def yield_taste_buddies(self, ignore_candidate=None):
        taste_buddies = self.taste_buddies[:]
        shuffle(taste_buddies)

        ignore_sock_addr = ignore_candidate.sock_addr if ignore_candidate else None

        for tb_tuple in taste_buddies:
            if tb_tuple[0] and tb_tuple[-1].sock_addr != ignore_sock_addr:
                yield tb_tuple[-1]

    def is_taste_buddy(self, candidate):
        candidate_mids = set(candidate.get_members())
        for tb in self.yield_taste_buddies():
            tb_mids = set(tb.get_members())
            if tb_mids & candidate_mids:
                return True

    def is_taste_buddy_mid(self, mid):
        for tb in self.yield_taste_buddies():
            if mid in [member.mid for member in tb.get_members()]:
                return True

    def is_taste_buddy_sock(self, sock_addr):
        for tb in self.yield_taste_buddies():
            if tb.sock_addr == sock_addr:
                return True

    def resetTastebuddy(self, member):
        for tb in self.taste_buddies:
            if member in tb[-1].get_members():
                tb[1] = time()

    def removeTastebuddy(self, member):
        remove = None

        removeIf = time() - CANDIDATE_WALK_LIFETIME
        for taste_buddy in self.taste_buddies:
            if member in taste_buddy[-1].get_members():
                if taste_buddy[1] < removeIf:
                    remove = taste_buddy
                break

        if remove:
            self.taste_buddies.remove(remove)

    def add_possible_taste_buddies(self, possibles):
        if __debug__:
            for possible in possibles:
                assert isinstance(possible[0], (float, int, long)), type(possible[0])
                assert isinstance(possible[1], (float, long)), type(possible[1])
                assert isinstance(possible[2], str), type(possible[2])
                assert isinstance(possible[3], WalkCandidate), type(possible[3])

        low_sim = self.get_low_sim()
        for new_pos_tuple in possibles:
            if new_pos_tuple[0] <= low_sim:
                continue

            for i, pos_tuple in enumerate(self.possible_taste_buddies):
                if new_pos_tuple[2] == pos_tuple[2]:
                    # max similarity
                    new_pos_tuple[0] = max(pos_tuple[0], new_pos_tuple[0])

                    # replace in list
                    self.possible_taste_buddies[i] = new_pos_tuple
                    break

            # new peer
            else:
                self.possible_taste_buddies.append(new_pos_tuple)

        self.possible_taste_buddies.sort(reverse=True)

        if DEBUG and possibles:
            print >> sys.stderr, long(time()), "ForwardCommunity: got possible taste buddies, current list", len(self.possible_taste_buddies), [possible[0] for possible in self.possible_taste_buddies]

    def has_possible_taste_buddies(self, candidate):
        for _, _, _, from_candidate in self.possible_taste_buddies:
            if from_candidate.sock_addr == candidate.sock_addr:
                return True
        return False

    def get_low_sim(self):
        if len(self.taste_buddies) == self.max_taste_buddies:
            return self.taste_buddies[-1][0]
        return 0

    def get_most_similar(self, candidate):
        assert isinstance(candidate, WalkCandidate), [type(candidate), candidate]

        # clean possible taste buddies, remove all entries older than 60s
        to_be_removed = time() - 60
        low_sim = self.get_low_sim()

        for i in range(len(self.possible_taste_buddies) - 1, -1, -1):
            to_low_sim = self.possible_taste_buddies[i][0] <= low_sim
            to_old = self.possible_taste_buddies[i][1] < to_be_removed
            is_tb = self.is_taste_buddy_mid(self.possible_taste_buddies[i][2])
            if to_low_sim or to_old or is_tb:
                if DEBUG:
                    print >> sys.stderr, long(time()), long(time()), "ForwardCommunity: removing possible tastebuddy", long(time()), to_low_sim, to_old, is_tb, self.possible_taste_buddies[i]
                self.possible_taste_buddies.pop(i)

        if self.possible_taste_buddies:
            most_similar = self.possible_taste_buddies.pop(0)
            return most_similar[3], most_similar[2]

        return candidate, None

    def get_connections(self, nr=10, ignore_candidate=None):
        # use taste buddies and fill with random candidates
        candidates = set(self.yield_taste_buddies(ignore_candidate))
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

        return candidates

    # connect to first nr peers in peercache
    def connect_to_peercache(self, nr=10):
        def attempt_to_connect(candidate, attempts):
            while not self.is_taste_buddy(candidate) and attempts:
                self.create_msimilarity_request(candidate)

                yield IntroductionRequestCache.timeout_delay + IntroductionRequestCache.cleanup_delay
                attempts -= 1

        peers = self._peercache.get_peers()[:nr]
        for sock_addr in peers:
            candidate = self.get_candidate(sock_addr, replace=False)
            if not candidate:
                candidate = self.create_candidate(sock_addr, False, sock_addr, sock_addr, u"unknown")

            self.dispersy.callback.register(attempt_to_connect, args=(candidate, 10))

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

    def create_msimilarity_request(self, destination):
        identifier = self._dispersy.request_cache.claim(ForwardCommunity.SimilarityAttempt(self, destination))
        send = self.send_msimilarity_request(destination, identifier)

        if not send:
            self._dispersy.request_cache.pop(identifier, ForwardCommunity.SimilarityAttempt)
        return send

    def send_msimilarity_request(self, destination, indentifier):
        raise NotImplementedError()

    class MSimilarityRequest(Cache):
        timeout_delay = 7.0
        cleanup_delay = 0.0

        def __init__(self, community, message, requested_candidates):
            self.community = community

            self.requesting_candidate = message.candidate
            self.requested_candidates = requested_candidates
            self.requested_mids = set()
            for candidate in self.requested_candidates:
                for member in candidate.get_members():
                    self.requested_mids.add(member.mid)

            self.received_candidates = set()
            self.received_lists = []
            self.isProcessed = False

        def add_response(self, candidate_mid, response):
            if candidate_mid:
                if candidate_mid in self.requested_mids:
                    if candidate_mid not in self.received_candidates:
                        self.received_candidates.add(candidate_mid)
                        self.received_lists.append((candidate_mid, response))
            else:
                self.my_response = response

        def is_complete(self):
            return len(self.received_lists) == len(self.requested_candidates)

        def process(self):
            if not self.isProcessed:
                self.isProcessed = True
                if DEBUG_VERBOSE:
                    print >> sys.stderr, long(time()), "ForwardCommunity: processed MSimilarityRequest send msimilarity-response to", self.requesting_candidate

                self.community._dispersy.request_cache.pop(self.identifier, ForwardCommunity.MSimilarityRequest)
                return self.community.send_msimilarity_response(self.requesting_candidate, self.identifier, self.my_response, self.received_lists)

        def on_timeout(self):
            if not self.isProcessed:
                if DEBUG:
                    print >> sys.stderr, long(time()), "ForwardCommunity: timeout MSimilarityRequest", self.identifier, len(self.received_lists), len(self.requested_candidates)

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
            request = ForwardCommunity.MSimilarityRequest(self, message, candidates)
            # add local response
            request.add_response(None, self.on_similarity_request([message], False))

            self._dispersy.request_cache.set(message.payload.identifier, request)
            if candidates:
                # forward it to others
                self.send_similarity_request(message, candidates)

            if request.is_complete():
                request.process()

    def send_similarity_request(self, msimilarity_request, candidates):
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

            if not self._dispersy.request_cache.has(message.payload.identifier, ForwardCommunity.MSimilarityRequest):
                yield DropMessage(message, "unknown identifier")
                continue

            yield message

    def on_similarity_response(self, messages):
        for message in messages:
            request = self._dispersy.request_cache.get(message.payload.identifier, ForwardCommunity.MSimilarityRequest)
            if request:
                request.add_response(message.authentication.member.mid, message.payload)
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

        def __init__(self, community, candidate):
            IntroductionRequestCache.__init__(self, community, None)
            self.candidate = candidate
            self.processed = False

        def on_success(self):
            self.processed = True

        def on_timeout(self):
            if not self.processed:
                if DEBUG:
                    print >> sys.stderr, long(time()), "SearchCommunity: no response on ping, removing from taste_buddies", self.candidate
                for member in self.candidate.get_members():
                    self.community.removeTastebuddy(member)

    def create_ping_request(self, candidate):
        while self.is_taste_buddy(candidate):
            self._create_pingpong(u"ping", [candidate])

            yield PING_INTERVAL

    def on_ping(self, messages):
        candidates = [message.candidate for message in messages]
        identifiers = [message.payload.identifier for message in messages]

        self._create_pingpong(u"pong", candidates, identifiers)

        for message in messages:
            self.resetTastebuddy(message.authentication.member)

    def check_pong(self, messages):
        for message in messages:
            accepted, _ = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue

            if not self._dispersy.request_cache.has(message.payload.identifier, ForwardCommunity.PingRequestCache):
                yield DropMessage(message, "invalid response identifier")
                continue

            yield message

    def on_pong(self, messages):
        for message in messages:
            request = self._dispersy.request_cache.pop(message.payload.identifier, ForwardCommunity.PingRequestCache)
            request.on_success()

            self.resetTastebuddy(message.authentication.member)

    def _create_pingpong(self, meta_name, candidates, identifiers=None):
        for index, candidate in enumerate(candidates):
            if identifiers:
                identifier = identifiers[index]
            else:
                identifier = self._dispersy.request_cache.claim(ForwardCommunity.PingRequestCache(self, candidate))

            # create torrent-collect-request/response message
            meta = self.get_meta_message(meta_name)
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,), payload=(identifier, []))
            self._dispersy._send([candidate], [message])

            if DEBUG:
                print >> sys.stderr, long(time()), "SearchCommunity: send", meta_name, "to", candidate

class PForwardCommunity(ForwardCommunity):

    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION, forward_to=10, max_prefs=None, max_fprefs=None, max_taste_buddies=10):
        ForwardCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption, forward_to, max_prefs, max_fprefs, max_taste_buddies)

        self.key = pallier_init(self.key)

    def initiate_meta_messages(self):
        messages = ForwardCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"msimilarity-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedVectorPayload(), self.check_msimilarity_request, self.on_msimilarity_request))
        messages.append(Message(self, u"similarity-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedVectorPayload(), self.check_similarity_request, self.on_similarity_request))
        messages.append(Message(self, u"msimilarity-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedSumsPayload(), self._dispersy._generic_timeline_check, self.on_msimilarity_response))
        messages.append(Message(self, u"similarity-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedSumPayload(), self.check_similarity_response, self.on_similarity_response))
        return messages

    def initiate_conversions(self):
        return [DefaultConversion(self), PSearchConversion(self)]

    def send_msimilarity_request(self, destination, identifier):
        global_vector = self.create_global_vector(destination, identifier)

        str_global_vector = str(global_vector)
        if self.my_preference_cache[0] == str_global_vector:
            encrypted_vector = self.my_preference_cache[1]
        else:
            my_vector = self.get_my_vector(global_vector, local=True)
            if self.encryption:

                t1 = time()
                encrypted_vector = []
                for element in my_vector:
                    cipher = pallier_encrypt(self.key, element)
                    encrypted_vector.append(cipher)

                self.create_time_encryption += time() - t1
            else:
                encrypted_vector = my_vector

            self.my_preference_cache = [str_global_vector, encrypted_vector]

        if encrypted_vector:
            meta_request = self.get_meta_message(u"msimilarity-request")
            request = meta_request.impl(authentication=(self.my_member,),
                                    distribution=(self.global_time,),
                                    destination=(destination,),
                                    payload=(identifier, self.key.n, encrypted_vector, global_vector))

            self._dispersy._forward([request])
            self.send_packet_size += len(request.packet)
            return True
        return False

    def send_similarity_request(self, msimilarity_request, candidates):
        # forward it to others
        meta_request = self.get_meta_message(u"similarity-request")
        request = meta_request.impl(authentication=(self.my_member,),
                            distribution=(self.global_time,),
                            payload=(msimilarity_request.payload.identifier, msimilarity_request.payload.key_n, msimilarity_request.payload.preference_list, msimilarity_request.payload.global_vector))

        self._dispersy._send(candidates, [request])
        self.forward_packet_size += len(request.packet) * len(candidates)

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
                        _sum = pallier_add(_sum, element, user_n2)
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
        received_sums = [(mid, payload._sum) for mid, payload in received_sums]

        meta_request = self.get_meta_message(u"msimilarity-response")
        response = meta_request.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,),
                                destination=(requesting_candidate,),
                                payload=(identifier, my_sum, received_sums))

        self._dispersy._forward([response])
        return len(response.packet)

    def on_msimilarity_response(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "PSearchCommunity: received sums", message.payload._sum

            t1 = time()
            if self.encryption:
                _sums = [[pallier_decrypt(self.key, _sum), time(), candidate_mid, message.candidate] for candidate_mid, _sum in message.payload.sums]
                _sum = pallier_decrypt(self.key, message.payload._sum)
            else:
                _sums = [[_sum, time(), candidate_mid, message.candidate] for candidate_mid, _sum in message.payload.sums]
                _sum = message.payload._sum

            self.create_time_decryption += time() - t1

            self.add_taste_buddies([[_sum, time(), message.candidate]])

            _sums = [possible for possible in _sums if possible[0]]
            if _sums:
                self.add_possible_taste_buddies(_sums)

        ForwardCommunity.on_msimilarity_response(self, messages)

    def create_global_vector(self, destination, identifier):
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

    def send_msimilarity_request(self, destination, identifier):
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
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "HSearchCommunity: sending similarity request to", destination, "containing", len(myPreferences), "hashes"

            meta_request = self.get_meta_message(u"msimilarity-request")
            request = meta_request.impl(authentication=(self.my_member,),
                                    distribution=(self.global_time,),
                                    destination=(destination,),
                                    payload=(identifier, long(self.key.n), myPreferences))

            self._dispersy._forward([request])
            return True
        return False

    def send_similarity_request(self, msimilarity_request, candidates):
        # forward it to others
        meta_request = self.get_meta_message(u"similarity-request")
        request = meta_request.impl(authentication=(self.my_member,),
                            distribution=(self.global_time,),
                            payload=(msimilarity_request.payload.identifier, msimilarity_request.payload.key_n, msimilarity_request.payload.preference_list[:self.max_f_prefs]))

        self._dispersy._send(candidates, [request])
        self.forward_packet_size += len(request.packet) * len(candidates)

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
        received_responses = [(mid, (payload.preference_list, payload.his_preference_list)) for mid, payload in received_responses]

        meta_request = self.get_meta_message(u"msimilarity-response")
        response = meta_request.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,),
                                destination=(requesting_candidate,),
                                payload=(identifier, my_response, received_responses))

        self._dispersy._forward([response])
        return len(response.packet)

    def compute_overlap(self, lists):
        preference_list, his_preference_list = lists

        if self.encryption:
            t1 = time()
            myList = [hash_element(rsa_decrypt(self.key, infohash)) for infohash in preference_list]

            self.create_time_decryption += time() - t1
        else:
            myList = [long_to_bytes(infohash) for infohash in preference_list]

        assert all(len(infohash) == 20 for infohash in myList)

        overlap = 0
        for pref in myList:
            if pref in his_preference_list:
                overlap += 1
        return overlap

    def on_msimilarity_response(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "HSearchCommunity: got msimi response from", message.candidate, len(message.payload.bundled_responses)

            overlap = self.compute_overlap([message.payload.preference_list, message.payload.his_preference_list])
            self.add_taste_buddies([[overlap, time(), message.candidate]])

            possibles = []
            for candidate_mid, remote_response in message.payload.bundled_responses:
                overlap = self.compute_overlap(remote_response)
                possibles.append([overlap, time(), candidate_mid, message.candidate])

            self.add_possible_taste_buddies(possibles)

        ForwardCommunity.on_msimilarity_response(self, messages)

class PoliForwardCommunity(ForwardCommunity):

    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION, forward_to=10, max_prefs=None, max_fprefs=None, max_taste_buddies=10):
        ForwardCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption, forward_to, max_prefs, max_fprefs, max_taste_buddies)
        self.key = pallier_init(self.key)

    def initiate_conversions(self):
        return [DefaultConversion(self), PoliSearchConversion(self)]

    def initiate_meta_messages(self):
        messages = ForwardCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"msimilarity-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), PoliSimilarityRequest(), self.check_msimilarity_request, self.on_msimilarity_request))
        messages.append(Message(self, u"similarity-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), PoliSimilarityRequest(), self.check_similarity_request, self.on_similarity_request))
        messages.append(Message(self, u"msimilarity-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedPoliResponsesPayload(), self._dispersy._generic_timeline_check, self.on_msimilarity_response))
        messages.append(Message(self, u"similarity-response", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), EncryptedPoliResponsePayload(), self.check_similarity_response, self.on_similarity_response))
        return messages

    def send_msimilarity_request(self, destination, identifier):
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
                    coeffs = [pallier_encrypt(self.key, coeff) for coeff in coeffs]

                partitions[partition] = coeffs

            self.create_time_encryption += time() - t1
            self.my_preference_cache = [str_myPreferences, partitions]

        if partitions:
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "PoliSearchCommunity: sending similarity request to", destination, "containing", len(partitions), "partitions and", sum(len(coeffs) for coeffs in partitions.itervalues()), "coefficients"

            meta_request = self.get_meta_message(u"msimilarity-request")
            request = meta_request.impl(authentication=(self.my_member,),
                                    distribution=(self.global_time,),
                                    destination=(destination,),
                                    payload=(identifier, long(self.key.n), partitions))

            self._dispersy._forward([request])
            self.send_packet_size += len(request.packet)
            return True
        return False

    def send_similarity_request(self, msimilarity_request, candidates):
        coefficients = msimilarity_request.payload.coefficients.copy()
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
                            payload=(msimilarity_request.payload.identifier, msimilarity_request.payload.key_n, coefficients))

        self._dispersy._send(candidates, [request])
        self.forward_packet_size += len(request.packet) * len(candidates)

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
                    py = pallier_polyval(message.payload.coefficients[partition], val, user_n2)
                    py = pallier_multiply(py, randint(0, 2 ** 40), user_n2)
                    results.append(py)
            else:
                for partition, val in _myPreferences:
                    py = polyval(message.payload.coefficients[partition], val)
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
        received_responses = [(mid, payload.my_response) for mid, payload in received_responses]

        meta_request = self.get_meta_message(u"msimilarity-response")
        response = meta_request.impl(authentication=(self._my_member,),
                                distribution=(self.global_time,),
                                destination=(requesting_candidate,),
                                payload=(identifier, my_response, received_responses))

        self._dispersy._forward([response])
        return len(response.packet)

    def on_msimilarity_response(self, messages):
        for message in messages:
            if DEBUG_VERBOSE:
                print >> sys.stderr, long(time()), "PoliSearchCommunity: got msimi response from", message.candidate, len(message.payload.bundled_responses)

            overlap = self.compute_overlap(message.payload.my_response)
            self.add_taste_buddies([[overlap, time(), message.candidate]])

            possibles = []
            for candidate_mid, remote_response in message.payload.bundled_responses:
                overlap = self.compute_overlap(remote_response)
                possibles.append([overlap, time(), candidate_mid, message.candidate])

            self.add_possible_taste_buddies(possibles)

        ForwardCommunity.on_msimilarity_response(self, messages)

    def compute_overlap(self, evaluated_polynomial):
        overlap = 0

        t1 = time()
        for py in evaluated_polynomial:
            if self.encryption:
                if pallier_decrypt(self.key, py) == 0:
                    overlap += 1
            else:
                if py == 0:
                    overlap += 1
        self.create_time_decryption += time() - t1
        return overlap

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
