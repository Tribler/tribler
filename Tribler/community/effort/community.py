try:
    # python 2.7 only...
    from collections import OrderedDict
except ImportError:
    from Tribler.dispersy.python27_ordereddict import OrderedDict

from json import dumps
from httplib import HTTPConnection
from random import random, sample
from time import time
from zlib import compress

from .conversion import EffortConversion
from .database import EffortDatabase
from .efforthistory import CYCLE_SIZE, EffortHistory
from .payload import EffortRecordPayload, PingPayload, PongPayload, DebugRequestPayload, DebugResponsePayload

from Tribler.dispersy.authentication import DoubleMemberAuthentication, NoAuthentication, MemberAuthentication
from Tribler.dispersy.candidate import BootstrapCandidate, WalkCandidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.dispersy.destination import CommunityDestination, CandidateDestination
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.distribution import LastSyncDistribution, DirectDistribution
from Tribler.dispersy.dprint import dprint
from Tribler.dispersy.member import Member
from Tribler.dispersy.message import BatchConfiguration, Message, DropMessage, DelayMessageByProof
from Tribler.dispersy.requestcache import Cache
from Tribler.dispersy.resolution import PublicResolution, LinearResolution
from Tribler.dispersy.revision import update_revision_information, get_revision

# update version information directly from SVN
update_revision_information("$HeadURL$", "$Revision$")

# generated: Thu Sep  6 10:02:41 2012
# curve: high <<< NID_sect571r1 >>>
# len: 571 bits ~ 144 bytes signature
# pub: 170 3081a7301006072a8648ce3d020106052b810400270381920004039bb20a07b2c09fe2eb0d75a6ab8f23503728fb105c5b34fea181d2b30130fa5b493ee6317b5af3b079d3509a0225d8bafd940438e07aa48b76a37ace874a1612cbcd0878f8b7eb03b95d6bb27992d61a165a657c2b1fe096e2d39998fca7604f3bf3cf317c33be8e449c5015fbef8981f6f9d5d4ddc38f2c728cf823f9faca3224629ab6282b29136117b21737c0f4
# pub-sha1 925f18381cb79b446332f92b8756bfab98c6dddb
# -----BEGIN PUBLIC KEY-----
# MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQDm7IKB7LAn+LrDXWmq48jUDco+xBc
# WzT+oYHSswEw+ltJPuYxe1rzsHnTUJoCJdi6/ZQEOOB6pIt2o3rOh0oWEsvNCHj4
# t+sDuV1rsnmS1hoWWmV8Kx/gluLTmZj8p2BPO/PPMXwzvo5EnFAV+++Jgfb51dTd
# w48scoz4I/n6yjIkYpq2KCspE2EXshc3wPQ=
# -----END PUBLIC KEY-----
MASTER_MEMBER_PUBLIC_KEY = "3081a7301006072a8648ce3d020106052b810400270381920004039bb20a07b2c09fe2eb0d75a6ab8f23503728fb105c5b34fea181d2b30130fa5b493ee6317b5af3b079d3509a0225d8bafd940438e07aa48b76a37ace874a1612cbcd0878f8b7eb03b95d6bb27992d61a165a657c2b1fe096e2d39998fca7604f3bf3cf317c33be8e449c5015fbef8981f6f9d5d4ddc38f2c728cf823f9faca3224629ab6282b29136117b21737c0f4".decode("HEX")

def bitcount(l):
    c = 0
    while l:
        if l & 1:
            c += 1
        l >>= 1
    return c

class PingCache(Cache):
    cleanup_delay = 0.0
    timeout_delay = 10.0

    def __init__(self, community, candidate, member):
        self.community = community
        self.candidate = candidate
        self.member = member

    def on_timeout(self):
        self.community.remove_from_slope(self.member)
        if isinstance(self.candidate, WalkCandidate):
            self.candidate.obsolete(self.community, time())

class RecordCandidate(object):
    def __init__(self, community, candidate, history, callback_id):
        self.community = community
        self.candidate = candidate
        self.history = history
        self.score = bitcount(history.long)
        self.callback_id = callback_id

class BandwidthGuess(object):
    def __init__(self, member=None, timestamp=0.0, upload=0.0, download=0.0):
        self.member = member
        self.timestamp = timestamp
        # up- and download in kilobytes (i.e. bytes / 1024, hence the float)
        self.upload = upload
        self.download = download

class EffortCommunity(Community):
    @classmethod
    def get_master_members(cls):
        return [Member(MASTER_MEMBER_PUBLIC_KEY)]

    @classmethod
    def load_community(cls, master):
        dispersy = Dispersy.get_instance()
        try:
            # test if this community already exists
            next(dispersy.database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)))
        except StopIteration:
            # join the community with a new my_member, using a cheap cryptography key
            ec = ec_generate_key(u"NID_secp160r1")
            return cls.join_community(master, Member(ec_to_public_bin(ec), ec_to_private_bin(ec)))
        else:
            return super(EffortCommunity, cls).load_community(master)

    def __init__(self, master):
        # original walker callbacks (will be set during super(...).__init__)
        self._original_on_introduction_request = None
        self._original_on_introduction_response = None

        super(EffortCommunity, self).__init__(master)

        # _DATABASE stores all direct observations and indirect hearsay
        self._database = EffortDatabase.get_instance(self._dispersy)

        # _OBSERVATIONS cache (reduce _DATABASE access)
        self._observations_length = 512
        self._observations = OrderedDict()

        # _bandwidth_guesses cache (reduce _DATABASE access)
        self._bandwidth_guesses_length = 512
        self._bandwidth_guesses = OrderedDict()

        # _DOWNLOAD_STATES contains all peers that are currently downloading.  when we determine
        # that a peer is missing, we will update its bandwidth statistics
        self._download_states = dict()
        self._swift_raw_bytes_up = 0
        self._swift_raw_bytes_down = 0

        # _SLOPE contains the promising members as Member:RecordCandidate
        self._slope_length = 10
        self._slope = {}

        # _SIGNATURE_COUNT is the number of members that will be asked to sign
        self._signature_count = 5

        # simple statistics
        self._statistic_incoming_signature_request_success = 0
        self._statistic_outgoing_signature_request = 0
        self._statistic_outgoing_signature_request_success = 0
        self._statistic_outgoing_signature_request_timeout = 0
        self._statistic_member_ordering_fail = 0
        self._statistic_initial_timestamp_fail = 0
        self._statistic_cycle_fail = 0

        # wait till next time we can create records with the candidates on our slope
        self._pending_callbacks.append(self._dispersy.callback.register(self._periodically_create_records))
        self._pending_callbacks.append(self._dispersy.callback.register(self._periodically_push_statistics))
        self._pending_callbacks.append(self._dispersy.callback.register(self._periodically_cleanup_database))

    @property
    def dispersy_sync_response_limit(self):
        return 5 * 1024

    @property
    def dispersy_sync_bloom_filter_strategy(self):
        return self._dispersy_claim_sync_bloom_filter_modulo

    def initiate_meta_messages(self):
        return [Message(self, u"effort-record", DoubleMemberAuthentication(allow_signature_func=self.allow_signature_request, encoding="bin"), PublicResolution(), LastSyncDistribution(synchronization_direction=u"DESC", priority=128, history_size=1), CommunityDestination(node_count=10), EffortRecordPayload(), self.check_effort_record, self.on_effort_record, batch=BatchConfiguration(max_window=4.5)),
                Message(self, u"ping", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PingPayload(), self.check_ping, self.on_ping),
                Message(self, u"pong", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PongPayload(), self.check_pong, self.on_pong),
                Message(self, u"debug-request", MemberAuthentication(), LinearResolution(), DirectDistribution(), CommunityDestination(node_count=32), DebugRequestPayload(), self.check_debug_request, self.on_debug_request),
                Message(self, u"debug-response", MemberAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), DebugResponsePayload(), self.check_debug_response, self.on_debug_response)]

    def _initialize_meta_messages(self):
        super(EffortCommunity, self)._initialize_meta_messages()

        # replace the callbacks for the dispersy-introduction-request and
        # dispersy-introduction-response messages
        meta = self._meta_messages[u"dispersy-introduction-request"]
        self._original_on_introduction_request = meta.handle_callback
        self._meta_messages[meta.name] = Message(meta.community, meta.name, meta.authentication, meta.resolution, meta.distribution, meta.destination, meta.payload, meta.check_callback, self.on_introduction_request, meta.undo_callback, meta.batch)
        assert self._original_on_introduction_request

        meta = self._meta_messages[u"dispersy-introduction-response"]
        self._original_on_introduction_response = meta.handle_callback
        self._meta_messages[meta.name] = Message(meta.community, meta.name, meta.authentication, meta.resolution, meta.distribution, meta.destination, meta.payload, meta.check_callback, self.on_introduction_response, meta.undo_callback, meta.batch)
        assert self._original_on_introduction_response

    def initiate_conversions(self):
        return [DefaultConversion(self), EffortConversion(self)]

    def dispersy_cleanup_community(self, message):
        if __debug__: dprint()
        # remove all data from the local database
        self._database.cleanup()
        # re-classify to prevent loading
        return super(EffortCommunity, self).dispersy_cleanup_community(message)

    def unload_community(self):
        if __debug__: dprint()
        super(EffortCommunity, self).unload_community()

        # cancel outstanding pings
        for ping_candidate in self._slope.itervalues():
            self._dispersy.callback.unregister(ping_candidate.callback_id)
        self._slope = {}

        # store all cached observations
        self._database.executemany(u"INSERT OR REPLACE INTO observation (member, timestamp, effort) VALUES (?, ?, ?)",
                                   [(database_id, history.origin, buffer(history.bytes)) for database_id, history in self._observations.iteritems()])

        # update all up and download values
        self.download_state_callback([])

        # store all cached bandwidth guesses
        self._database.executemany(u"INSERT OR REPLACE INTO bandwidth_guess (ip, member, timestamp, upload, download) VALUES (?, ?, ?, ?, ?)",
                                   [(unicode(ip), guess.member.database_id if guess.member else 0, guess.timestamp, int(guess.upload), int(guess.download)) for ip, guess in self._bandwidth_guesses.iteritems()])

    def _observation(self, candidate, member, now, update_record=True):
        if not isinstance(candidate, BootstrapCandidate):
            # try cache
            history = self._observations.get(member.database_id)
            if not history:
                # fetch from database
                try:
                    timestamp, bytes_ = next(self._database.execute(u"SELECT timestamp, effort FROM observation WHERE member = ?",
                                                                    (member.database_id,)))
                except StopIteration:
                    # first observation: create new history
                    history = EffortHistory(now)
                else:
                    history = EffortHistory(str(bytes_), float(timestamp))

                # store in cache
                self._observations[member.database_id] = history
                if len(self._observations) > self._observations_length:
                    key, value = self._observations.popitem(False)
                    self._database.execute(u"INSERT OR REPLACE INTO observation (member, timestamp, effort) VALUES (?, ?, ?)",
                                           (key, value.origin, buffer(value.bytes)))

            if update_record:
                changed = history.set(now)
                if changed:
                    self.try_adding_to_slope(candidate, member, history)
                if __debug__: dprint("c", int(now / CYCLE_SIZE), " ", candidate)

            return history

    def _get_bandwidth_guess_from_ip(self, ip):
        assert isinstance(ip, basestring), type(ip)
        # try cache
        guess = self._bandwidth_guesses.get(ip)
        if not guess:
            # fetch from database
            try:
                member_database_id, timestamp, upload, download = next(self._database.execute(u"SELECT member, timestamp, upload, download FROM bandwidth_guess WHERE ip = ? LIMIT 1", (ip,)))
            except StopIteration:
                # first seen: create new BandwidthGuess instance
                guess = BandwidthGuess()
            else:
                member = self._dispersy.get_member_from_database_id(member_database_id) if member_database_id > 0 else None
                # note that get_member_from_database_id may also return None
                guess = BandwidthGuess(member, timestamp, float(upload), float(download))

            # store in cache
            self._bandwidth_guesses[ip] = guess
            if len(self._bandwidth_guesses) > self._bandwidth_guesses_length:
                key, value = self._bandwidth_guesses.popitem(False)
                self._database.execute(u"INSERT OR REPLACE INTO bandwidth_guess (ip, member, timestamp, upload, download) VALUES (?, ?, ?, ?, ?)",
                                       (unicode(key), value.member.database_id if value.member else 0, value.timestamp, int(value.upload), int(value.download)))

        return guess

    def _get_bandwidth_guess_from_candidate(self, candidate):
        return self._get_bandwidth_guess_from_ip(candidate.get_destination_address(self._dispersy.wan_address)[0])

    def _try_bandwidth_guess_from_member(self, member):
        try:
            ip, = next(self._database.execute(u"SELECT ip FROM bandwidth_guess WHERE member = ? ORDER BY timestamp DESC LIMIT 1", (member.database_id,)))
        except StopIteration:
            return None
        else:
            return self._get_bandwidth_guess_from_ip(ip)

    def download_state_callback(self, states):
        assert self._dispersy.callback.is_current_thread, "Must be called on the dispersy.callback thread"
        assert isinstance(states, list)
        timestamp = int(time())

        # get all swift downloads that have peers
        active = dict((state.get_download().get_def().get_id(), state)
                      for state
                      in states
                      if state.get_download().get_def().get_def_type() == "swift" and state.get_peerlist())

        # get global up and download for swift
        for state in active.itervalues():
            stats = state.stats["stats"]
            self._swift_raw_bytes_up = stats.rawUpTotal
            self._swift_raw_bytes_down = stats.rawDownTotal

        # OLD is used to determine stopped downloads and peers that left.  NEW will become the next OLD
        old = self._download_states
        new = self._download_states = dict()

        # find downloads that stopped
        for identifier in set(old.iterkeys()).difference(set(active.iterkeys())):
            for ip, (up, down) in old[identifier].iteritems():
                if __debug__: dprint(identifier.encode("HEX"), "] ", ip, " +", up, " +", down)
                guess = self._get_bandwidth_guess_from_ip(ip)
                guess.timestamp = timestamp
                guess.upload += up
                guess.download += down

        for identifier, state in active.iteritems():
            if identifier in old:
                # find peers that left
                for ip in set(old[identifier]).difference(set(peer["ip"] for peer in state.get_peerlist())):
                    up, down = old[identifier][ip]
                    if __debug__: dprint(identifier.encode("HEX"), "] ", ip, " +", up, " +", down)
                    guess = self._get_bandwidth_guess_from_ip(ip)
                    guess.timestamp = timestamp
                    guess.upload += up
                    guess.download += down

            # set OLD for the next call to DOWNLOAD_STATE_CALLBACK
            new[identifier] = dict((peer["ip"], (peer["utotal"], peer["dtotal"])) for peer in state.get_peerlist() if peer["utotal"] > 0.0 or peer["dtotal"] > 0.0)

    def _periodically_cleanup_database(self):
        yield 100.0

        while True:
            # remove all entries when:
            # - dispersy never encountered this node within the last hour
            # - or, the entry is older than 24 hours
            self._database.execute(u"DELETE FROM bandwidth_guess WHERE (member = 0 AND timestamp < ?) OR timestamp < ?",
                                   (time() - 3600, time() - 86400))
            yield 300.0

    def on_introduction_request(self, messages):
        try:
            return self._original_on_introduction_request(messages)
        finally:
            now = time()
            for message in messages:
                self._observation(message.candidate, message.authentication.member, now)
                # associate member to ip
                guess = self._get_bandwidth_guess_from_candidate(message.candidate)
                guess.member = message.authentication.member
                guess.timestamp = now

    def on_introduction_response(self, messages):
        try:
            return self._original_on_introduction_response(messages)
        finally:
            now = time()
            for message in messages:
                self._observation(message.candidate, message.authentication.member, now)
                # associate member to ip
                guess = self._get_bandwidth_guess_from_candidate(message.candidate)
                guess.member = message.authentication.member
                guess.timestamp = now

    def create_effort_record(self, second_member, history):
        """
        Create a dispersy-signature-request that encapsulates an effort-record.
        """
        if __debug__: dprint("asking ", second_member.mid.encode("HEX"), " to sign ", bin(history.long))
        guess = self._try_bandwidth_guess_from_member(second_member)
        if guess:
            first_up = int(guess.upload)
            first_down = int(guess.download)
        else:
            first_up = 0
            first_down = 0

        self._statistic_outgoing_signature_request += 1
        meta = self.get_meta_message(u"effort-record")
        record = meta.impl(authentication=([self._my_member, second_member],),
                           distribution=(self.claim_global_time(),),
                           payload=(history.origin, history.origin, history, first_up, first_down, 0, 0),
                           sign=False)
        return self.create_dispersy_signature_request(record, self.on_signature_response)

    def allow_signature_request(self, message):
        """
        A dispersy-signature-request has been received.

        Return None or a Message.Implementation.
        """
        assert message.name == u"effort-record"
        assert not message.authentication.is_signed
        if __debug__: dprint(message)

        _, first_member = message.authentication.signed_members[0]
        _, second_member = message.authentication.signed_members[1]

        if not second_member == self._my_member:
            # the first_member is us.  meaning that we will get duplicate global times because
            # someone else claimed the global time for us
            if __debug__: dprint("invalid request.  second_member != my_member", level="warning")
            self._statistic_member_ordering_fail += 1
            return None

        first_timestamp = message.payload.first_timestamp
        second_timestamp = message.payload.second_timestamp

        if not first_timestamp == second_timestamp:
            # the initial (unsigned) record must have both time stamps set to the value that
            # FIRST_MEMBER believes to be true.  this will ensure that MESSAGE.payload.history will
            # have FIRST_MEMBERS' choice of origin.
            if __debug__: dprint("invalid request.  first_timestamp != second_timestamp", level="warning")
            self._statistic_initial_timestamp_fail += 1
            return None

        proposed_history = message.payload.history
        local_history = self._observation(message.candidate, message.authentication.member, time())
        second_timestamp = local_history.origin

        if not proposed_history.cycle == local_history.cycle:
            # there is a problem determining the current cycle.  this can be caused by (a)
            # difference in local clock times, (b) record creation during transition between cycles,
            # (c) delay in message processing resulting in issue b.
            if __debug__: dprint("invalid request. cycle mismatch (", proposed_history.cycle, " != ", local_history.cycle, " or ", proposed_history.origin, " != ", local_history.origin, ")", level="warning")
            self._statistic_cycle_fail += 1
            return None

#        if proposed_history.long ^ local_history.long:
#            # there is a mismatch in bits, this should not occur on the DAS4, however, we will need
#            # to repair this once we go into the big bad world
#            bz2log("effort.log", "record-disagreement", reason="invalid bits", identifier=message.payload.identifier)
#            if __debug__: dprint("invalid request. bits mismatch (", bin(proposed_history.long), " != ", bin(local_history.long), ")", level="warning")
#            return None

        # AND between proposed and local history
        merged_history = EffortHistory(proposed_history.long & local_history.long, local_history.origin)

        # the first_member took the initiative this cycle.  prevent us from also taking the
        # initiative and create duplicate records this cycle
        self.remove_from_slope(first_member)

        # get the upload and download counters
        first_up = message.payload.first_up
        first_down = message.payload.first_down
        guess = self._try_bandwidth_guess_from_member(first_member)
        if guess:
            second_up = int(guess.upload)
            second_down = int(guess.download)
        else:
            second_up = 0
            second_down = 0

        self._statistic_incoming_signature_request_success += 1
        # return the modified effort-record we propose
        meta = self.get_meta_message(u"effort-record")
        return meta.impl(authentication=([first_member, second_member],),
                         distribution=(message.distribution.global_time,),
                         payload=(first_timestamp, second_timestamp, merged_history, first_up, first_down, second_up, second_down))

    def on_signature_response(self, cache, new_message, changed):
        """
        A dispersy-signature-response has been received.

        Return True or False to either accept or decline the message.
        """
        if __debug__: dprint(new_message)

        # TODO: we should ensure that new_message is correct (i.e. all checks made above)

        if new_message:
            self._statistic_outgoing_signature_request_success += 1
            self._observation(new_message.candidate, cache.members[0], time())

            assert cache.request.payload.message.meta == new_message.meta
            return True

        else:
            self._statistic_outgoing_signature_request_timeout += 1
            self.remove_from_slope(cache.members[0])
            return False

    def _periodically_create_records(self):
        """
        Periodically initiates signature requests with the current optimal peers on self._SLOPE.

        Each cycle is divided into three phases.  The first phase consists of only hill climbing,
        during the second phase signature requests are made at random intervals, and during the
        third phase hill climbing already start for the next phase, although no signature request
        are made.

        |-----------50%-----------|---------40%--------|-10%-|
                                      record creation
        """
        # WINNERS holds the members that have 'won' this cycle
        winners = set()

        while True:
            now = time()
            start_climb = int(now / CYCLE_SIZE) * CYCLE_SIZE
            start_create = start_climb + CYCLE_SIZE * 0.5
            start_idle = start_climb + CYCLE_SIZE * 0.9
            start_next = start_climb + CYCLE_SIZE

            if start_climb <= now < start_create:
                if __debug__: dprint("c", int(now / CYCLE_SIZE), " first climbing phase.  wait ", start_create - now, " seconds until the next phase")
                yield start_create - now

            elif start_create <= now < start_idle and len(winners) < self._signature_count:
                if __debug__: dprint("c", int(now / CYCLE_SIZE), " record creation phase.  wait ", CYCLE_SIZE * 0.4 / self._signature_count, " seconds until record creation")
                yield (CYCLE_SIZE * 0.4 / self._signature_count) * random()

                # find the best candidate for this cycle
                score = 0
                winner = None
                for member, record_candidate in self._slope.iteritems():
                    if record_candidate.score > score and not member in winners:
                        winner = member

                if winner:
                    if __debug__: dprint("c", int(now / CYCLE_SIZE), " attempt record creation with ", winner.mid.encode("HEX"))
                    record_candidate = self._slope[winner]

                    # prevent this winner to 'win' again in this cycle
                    winners.add(winner)

                    # # TODO: this may be and invalid assumption
                    # # assume that the peer is online
                    # record_candidate.history.set(now)

                    self._dispersy.callback.unregister(record_candidate.callback_id)
                    self.create_effort_record(winner, record_candidate.history)

                else:
                    if __debug__: dprint("c", int(now / CYCLE_SIZE), " no peers available for record creation (", len(self._slope), " peers on slope)")

            else:
                if __debug__: dprint("c", int(now / CYCLE_SIZE), " second climbing phase.  wait ", start_next - now, " seconds until the next phase")
                assert now >= start_idle or len(winners) >= self._signature_count
                for record_candidate in self._slope.itervalues():
                    self._dispersy.callback.unregister(record_candidate.callback_id)
                self._slope = {}
                winners = set()
                yield start_next - now

    def try_adding_to_slope(self, candidate, member, history):
        if not member in self._slope:
            score = bitcount(history.long)
            if (score > 2 and
                (len(self._slope) < self._slope_length or
                 min(ping_candidate.score for ping_candidate in self._slope.itervalues()) < score)):

                callback_id = self._dispersy.callback.register(self._ping, (candidate, member), delay=50.0)
                self._slope[member] = RecordCandidate(self, candidate, history, callback_id)

                if len(self._slope) > self._slope_length:
                    smallest_member = member
                    smallest_score = score

                    for member, ping_candidate in self._slope.iteritems():
                        if ping_candidate.score < smallest_score:
                            smallest_member = member
                            smallest_score = ping_candidate.score

                    self.remove_from_slope(smallest_member)

                return True
        return False

    def remove_from_slope(self, member):
        try:
            ping_candidate = self._slope.pop(member)
        except KeyError:
            pass
        else:
            self._dispersy.callback.unregister(ping_candidate.callback_id)

    def _ping(self, candidate, member):
        meta = self._meta_messages[u"ping"]
        while True:
            cache = PingCache(self, candidate, member)
            identifier = self._dispersy.request_cache.claim(cache)
            ping = meta.impl(distribution=(self._global_time,), destination=(candidate,), payload=(identifier, self._my_member))
            self._dispersy.store_update_forward([ping], False, False, True)

            yield 50.0

    def check_ping(self, messages):
        return messages

    def on_ping(self, messages):
        now = time()
        for message in messages:
            self._observation(message.candidate, message.payload.member, now)

        meta = self._meta_messages[u"pong"]
        responses = [meta.impl(distribution=(self._global_time,), destination=(ping.candidate,), payload=(ping.payload.identifier, self._my_member)) for ping in messages]
        self._dispersy.store_update_forward(responses, False, False, True)

    def check_pong(self, messages):
        for message in messages:
            if not self._dispersy.request_cache.has(message.payload.identifier, PingCache):
                yield DropMessage(message, "invalid response identifier")
                continue

            yield message

    def on_pong(self, messages):
        now = time()
        for message in messages:
            self._observation(message.candidate, message.payload.member, now)
            self._dispersy.request_cache.pop(message.payload.identifier, PingCache)

    def check_effort_record(self, messages):
        # stupidly accept everything...
        return messages

    def on_effort_record(self, messages):
        def ordering(message):
            # print "RAW_RECORD_IN", message.packet.encode("HEX")
            # print \
            #     "RECORD_IN", \
            #     bin(message.payload.history.long), \
            #     message.distribution.global_time, \
            #     int(message.payload.history.origin / CYCLE_SIZE), \
            #     message.payload.first_timestamp, \
            #     message.payload.second_timestamp, \
            #     message.authentication.members[0].mid.encode("HEX"), \
            #     message.authentication.members[1].mid.encode("HEX")

            if message.authentication.members[0].database_id < message.authentication.members[1].database_id:
                return (message.packet_id,
                        message.distribution.global_time,
                        message.authentication.members[0].database_id,
                        message.authentication.members[1].database_id,
                        int(message.payload.first_timestamp),
                        int(message.payload.second_timestamp),
                        buffer(message.payload.history.bytes),
                        message.payload.first_up,
                        message.payload.first_down,
                        message.payload.second_up,
                        message.payload.second_down)

            else:
                return (message.packet_id,
                        message.distribution.global_time,
                        message.authentication.members[1].database_id,
                        message.authentication.members[0].database_id,
                        int(message.payload.second_timestamp),
                        int(message.payload.first_timestamp),
                        buffer(message.payload.history.bytes),
                        message.payload.first_up,
                        message.payload.first_down,
                        message.payload.second_up,
                        message.payload.second_down)

        if __debug__: dprint("storing ", len(messages), " effort records")
        self._database.executemany(u"INSERT OR REPLACE INTO record (sync, global_time, first_member, second_member, first_timestamp, second_timestamp, effort, first_upload, first_download, second_upload, second_download) VALUES (?, ?, ?, ?, ?, ?, ? ,?, ?, ?, ?)",
                                   (ordering(message) for message in messages))

    def create_debug_request(self):
        members = set((self._my_member,))
        for candidate in self._dispersy.yield_candidates(self):
            members.update(candidate.get_members(self))
        members = [member.mid for member in sample(members, min(len(members), 50))]

        meta = self._meta_messages[u"debug-request"]
        request = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,),
                            payload=(self._dispersy.wan_address, members))
        self._dispersy.store_update_forward([request], False, False, True)

    def check_debug_request(self, messages):
        for message in messages:
            # the signed source_address (in the packet payload) must be the same as the UDP source
            # address.  this will still allow spoofing.
            if not message.payload.source_address == message.candidate.wan_address:
                yield DropMessage(message, "Phising attempt")
                continue

            allowed, _ = self._timeline.check(message)
            if not allowed:
                yield DelayMessageByProof(message)
                continue

            yield message

    def on_debug_request(self, messages):
        meta = self._meta_messages[u"debug-response"]

        # store all cached observations
        self._database.executemany(u"INSERT OR REPLACE INTO observation (member, timestamp, effort) VALUES (?, ?, ?)",
                                   [(database_id, history.origin, buffer(history.bytes)) for database_id, history in self._observations.iteritems()])

        # count observations and records in the database
        observations, = next(self._database.execute(u"SELECT COUNT(*) FROM observation"))
        records, = next(self._database.execute(u"SELECT COUNT(*) FROM record"))

        for message in messages:
            now = time()
            views = {}
            for mid in message.payload.members:
                members = self._dispersy.get_members_from_id(mid)
                if len(members) >= 1:
                    history = self._observation(None, members[0], now, update_record=False)
                    # TODO: calculate...
                    views[mid] = (bitcount(history.long), 0)

            response = meta.impl(authentication=(self._my_member,),
                                 distribution=(self.global_time,),
                                 destination=(message.candidate,),
                                 payload=(get_revision(), time(), observations, records, views))
            self._dispersy.store_update_forward([response], False, False, True)

    def check_debug_response(self, messages):
        return messages

    def on_debug_response(self, messages):
        for message in messages:
            payload = message.payload
            print "RAW_DEBUG", message.packet.encode("HEX")
            print "DEBUG", message.authentication.member.mid.encode("HEX"), payload.revision, payload.now, payload.observations, payload.records, " ".join("%s:%d:%d" % (mid.encode("HEX"), view[0], view[1]) for mid, view in payload.views.iteritems())

    def _periodically_push_statistics(self):
        def get_record_entry(_, first_member_id, second_member_id, *args):
            try:
                mid1, = next(self._dispersy.database.execute(u"SELECT HEX(mid) FROM member WHERE id = ?", (first_member_id,)))
                mid1 = str(mid1)
            except StopIteration:
                mid1 = "unavailable"
            try:
                mid2, = next(self._dispersy.database.execute(u"SELECT HEX(mid) FROM member WHERE id = ?", (second_member_id,)))
                mid2 = str(mid2)
            except StopIteration:
                mid2 = "unavailable"

            return (mid1, mid2) + args

        def push(shutdown=False):
            """ Push a portion of the available data """
            observations_in_db, = next(self._database.execute(u"SELECT COUNT(*) FROM observation"))
            bandwidth_guesses_in_db, = next(self._database.execute(u"SELECT COUNT(*) FROM bandwidth_guess"))
            records_in_db, = next(self._database.execute(u"SELECT COUNT(*) FROM record"))

            data = dict(cid=self._cid.encode("HEX"),
                        mid=self._my_member.mid.encode("HEX"),
                        timestamp_start=start,
                        timestamp=time(),
                        lan_address=self._dispersy.lan_address,
                        wan_address=self._dispersy.wan_address,
                        connection_type=self._dispersy.connection_type,
                        dispersy_total_up=self._dispersy.endpoint.total_up,
                        dispersy_total_down=self._dispersy.endpoint.total_down,
                        swift_total_up=self._swift_raw_bytes_up,
                        swift_total_down=self._swift_raw_bytes_down,
                        observations_in_db=observations_in_db,
                        bandwidth_guesses_in_db=bandwidth_guesses_in_db,
                        records_in_db=records_in_db,
                        incoming_signature_request_success=self._statistic_incoming_signature_request_success,
                        outgoing_signature_request=self._statistic_outgoing_signature_request,
                        outgoing_signature_request_success=self._statistic_outgoing_signature_request_success,
                        outgoing_signature_request_timeout=self._statistic_outgoing_signature_request_timeout,
                        member_ordering_fail=self._statistic_member_ordering_fail,
                        initial_timestamp_fail=self._statistic_initial_timestamp_fail,
                        cycle_fail=self._statistic_cycle_fail,
                        shutdown=shutdown)
            yield 0.0

            update_last_record_pushed = False
            if not shutdown:
                last_record_pushed, = next(self._database.execute(u"SELECT value FROM option WHERE key = ?", (u"last_record_pushed",)))
                records = list(self._database.execute(u"""
SELECT sync, first_member, second_member, global_time, first_timestamp, second_timestamp, HEX(effort), first_upload, first_download, second_upload, second_download
FROM record
WHERE sync > ?
ORDER BY sync
LIMIT 1000""", (last_record_pushed,)))
                if records:
                    yield 0.0
                    update_last_record_pushed = True
                    last_record_pushed = records[-1][0]
                    data["records"] = [get_record_entry(*row) for row in records]
                    del records
                    yield 0.0

                else:
                    if __debug__: dprint("no new records to push (post sync.id ", last_record_pushed, ")")

            # one big data string...
            data = dumps(data)
            yield 0.0
            data = compress(data, 9)
            yield 0.0

            try:
                if __debug__: dprint("pushing ", len(data), " bytes (compressed)")
                connection = HTTPConnection("effortreporter.tribler.org")
                # connection.set_debuglevel(1)
                connection.putrequest("POST", "/post/post.py")
                connection.putheader("Content-Type", "application/zip")
                connection.putheader("Content-Length", str(len(data)))
                connection.endheaders()

                if shutdown:
                    connection.send(data)

                else:
                    for offset in xrange(0, len(data), 5120):
                        if __debug__: dprint("sending...")
                        connection.send(data[offset:offset+5120])
                        yield 1.0

                response = connection.getresponse()
                if __debug__: dprint("response: ", response.status, " ", response.reason, " \"", response.read(), "\"")

                connection.close()

            except Exception:
                dprint("unable to push statistics", exception=True, level="error")

            else:
                if response.status == 200:
                    # post successful
                    if update_last_record_pushed:
                        self._database.execute(u"UPDATE option SET value = ? WHERE key = ?", (last_record_pushed, u"last_record_pushed"))
                else:
                    dprint("unable to push statistics.  response: ", response.status, level="error")

        try:
            start = time()
            while True:
                yield 300.0
                for delay in push():
                    assert isinstance(delay, float)
                    yield delay

        except GeneratorExit:
            # shutdown Tribler
            for _ in push(shutdown=True):
                pass
