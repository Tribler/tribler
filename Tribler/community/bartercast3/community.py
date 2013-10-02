from Tribler.dispersy.logger import get_logger
logger = get_logger(__name__)

try:
    # python 2.7 only...
    from collections import OrderedDict
except ImportError:
    from Tribler.dispersy.python27_ordereddict import OrderedDict

from random import random
from time import time

from .conversion import BarterConversion
from .database import BarterDatabase
from .efforthistory import CYCLE_SIZE, EffortHistory
from .payload import BarterRecordPayload, PingPayload, PongPayload, MemberRequestPayload, MemberResponsePayload

from Tribler.dispersy.callback import Callback
from Tribler.dispersy.authentication import DoubleMemberAuthentication, NoAuthentication, MemberAuthentication
from Tribler.dispersy.candidate import WalkCandidate, BootstrapCandidate, Candidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination, CandidateDestination
from Tribler.dispersy.distribution import LastSyncDistribution, DirectDistribution, GlobalTimePruning
from Tribler.dispersy.message import BatchConfiguration, Message, DropMessage
from Tribler.dispersy.requestcache import Cache
from Tribler.dispersy.resolution import PublicResolution

# generated: Fri Apr 19 17:07:32 2013
# curve: high <<< NID_sect571r1 >>>
# len: 571 bits ~ 144 bytes signature
# pub: 170 3081a7301006072a8648ce3d020106052b8104002703819200040792e72441554e5d5448043bcf516c18d93125cf299244f85fa3bc2c89cdca3029b2f8d832573d337babae5f64ff49dbf70ceca5a0a15e1b13a685c50c4bf285252667e3470b82f90318ac8ee2ad2d09ddabdc140ca879b938921831f0089511321e456b67c3b545ca834f67259e4cf7eff02fbd797c03a2df6db5b945ff3589227d686d6bf593b1372776ece283ab0d
# pub-sha1 4fe1172862c649485c25b3d446337a35f389a2a2
# -----BEGIN PUBLIC KEY-----
# MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQHkuckQVVOXVRIBDvPUWwY2TElzymS
# RPhfo7wsic3KMCmy+NgyVz0ze6uuX2T/Sdv3DOyloKFeGxOmhcUMS/KFJSZn40cL
# gvkDGKyO4q0tCd2r3BQMqHm5OJIYMfAIlREyHkVrZ8O1RcqDT2clnkz37/AvvXl8
# A6LfbbW5Rf81iSJ9aG1r9ZOxNyd27OKDqw0=
# -----END PUBLIC KEY-----
MASTER_MEMBER_PUBLIC_KEY = "3081a7301006072a8648ce3d020106052b8104002703819200040792e72441554e5d5448043bcf516c18d93125cf299244f85fa3bc2c89cdca3029b2f8d832573d337babae5f64ff49dbf70ceca5a0a15e1b13a685c50c4bf285252667e3470b82f90318ac8ee2ad2d09ddabdc140ca879b938921831f0089511321e456b67c3b545ca834f67259e4cf7eff02fbd797c03a2df6db5b945ff3589227d686d6bf593b1372776ece283ab0d".decode("HEX")
MASTER_MEMBER_PUBLIC_KEY_DIGEST = "4fe1172862c649485c25b3d446337a35f389a2a2".decode("HEX")


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
        super(PingCache, self).__init__()
        self.community = community
        self.candidate = candidate
        self.member = member

    def on_timeout(self):
        self.community.remove_from_slope(self.member)
        if isinstance(self.candidate, WalkCandidate):
            self.candidate.obsolete(time())


class MemberRequestCache(Cache):

    def __init__(self, func):
        super(MemberRequestCache, self).__init__()
        self.func = func

    def on_timeout(self):
        logger.warning("unable to find missing member [id:%d]", self.identifier)


class RecordCandidate(object):

    """
    Container class for a candidate that is on our slope.
    """
    def __init__(self, candidate, callback_id):
        super(RecordCandidate, self).__init__()
        self.candidate = candidate
        self.callback_id = callback_id


class Association(object):

    def __init__(self):
        self.timestamp = 0.0
        self.member = None

    def retrieve(self):
        """
        Returns True when this association may be updated again.
        """
        now = time()
        if now - self.timestamp > 60.0:
            self.timestamp = now
            return True

        return False


class Book(object):

    """
    Container class for all the bookkeeping information per peer.
    """
    def __init__(self, member):
        super(Book, self).__init__()
        self.member = member
        self.cycle = 0
        self.effort = None
        self.upload = 0
        self.download = 0

    @property
    def score(self):
        """
        Score is used to order members by how useful it is to make a (new) record with them.
        """
        # how much this member contributed - how much this member consumed
        return self.upload - self.download


class BarterCommunity(Community):

    @classmethod
    def get_master_members(cls, dispersy):
        return [dispersy.get_member(MASTER_MEMBER_PUBLIC_KEY)]

    @classmethod
    def load_community(cls, dispersy, master, *args, **kargs):
        try:
            # test if this community already exists
            classification, = next(dispersy.database.execute(u"SELECT classification FROM community WHERE master = ?", (master.database_id,)))
        except StopIteration:
            # join the community with a new my_member, using a cheap cryptography key
            return cls.join_community(dispersy, master, dispersy.get_new_member(u"NID_secp160r1"), *args, **kargs)
        else:
            if classification == cls.get_classification():
                return super(BarterCommunity, cls).load_community(dispersy, master, *args, **kargs)
            else:
                raise RuntimeError("Unable to load an BarterCommunity that has been killed")

    def __init__(self, dispersy, master, swift_process):
        logger.debug("loading the Barter community")

        # original walker callbacks (will be set during super(...).__init__)
        self._original_on_introduction_request = None
        self._original_on_introduction_response = None

        super(BarterCommunity, self).__init__(dispersy, master)

        # _SWIFT is a SwiftProcess instance (allowing us to schedule CLOSE_EVENT callbacks)
        self._swift = swift_process
        self._swift.set_subscribe_channel_close("ALL", True, self.i2ithread_channel_close)

        # _DATABASE stores all direct observations and indirect hearsay
        self._database = BarterDatabase(self._dispersy)
        self._database.open()

        options = dict(self._database.execute(u"SELECT key, value FROM option"))
        # _TOTAL_UP and _TOTAL_DOWN contain the total up and down statistics received from swift
        self._total_up = long(str(options.get(u"total-up", 0)))
        self._total_down = long(str(options.get(u"total-down", 0)))
        # _UNKNOWN_UP and _UNKNOWN_DOWN contain the total up and down statistics received from swift
        # where we were able to associate to a Dispersy member
        self._associated_up = long(str(options.get(u"associated-up", 0)))
        self._associated_down = long(str(options.get(u"associated-down", 0)))

        # _BOOKS cache (reduce _DATABASE access)
        self._books_length = 512
        self._books = OrderedDict()

        # _ADDRESS_ASSOCIATION containing address:Association pairs
        self._address_association_length = 512
        self._address_association = OrderedDict()

        # _DOWNLOAD_STATES contains all peers that are currently downloading.  when we determine
        # that a peer is missing, we will update its bandwidth statistics
        self._download_states = dict()

        # _SLOPE contains the promising members as Member:RecordCandidate
        self._slope_length = 10
        self._slope = {}

        # _SIGNATURE_COUNT is the number of members that will be asked to sign
        self._signature_count = 5

        # _HAS_BEEN_KILLED makes Tribler remove the community pointer
        self._has_been_killed = False

        # wait till next time we can create records with the candidates on our slope
        self._pending_callbacks.append(self._dispersy.callback.register(self._periodically_create_records))

    @property
    def database(self):
        return self._database

    @property
    def has_been_killed(self):
        return self._has_been_killed

    @property
    def dispersy_sync_response_limit(self):
        return 5 * 1024

    @property
    def dispersy_sync_bloom_filter_strategy(self):
        return self._dispersy_claim_sync_bloom_filter_modulo

    def initiate_meta_messages(self):
        pruning = GlobalTimePruning(10000, 11000)
        return [Message(self, u"barter-record", DoubleMemberAuthentication(allow_signature_func=self.allow_signature_request, encoding="bin"), PublicResolution(), LastSyncDistribution(synchronization_direction=u"DESC", priority=128, history_size=1, pruning=pruning), CommunityDestination(node_count=10), BarterRecordPayload(), self.check_barter_record, self.on_barter_record, batch=BatchConfiguration(max_window=4.5)),
                Message(self, u"ping", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PingPayload(), self.check_ping, self.on_ping),
                Message(self, u"pong", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PongPayload(), self.check_pong, self.on_pong),
                Message(self, u"member-request", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), MemberRequestPayload(), self.check_member_request, self.on_member_request),
                Message(self, u"member-response", MemberAuthentication(encoding="bin"), PublicResolution(), DirectDistribution(), CandidateDestination(), MemberResponsePayload(), self.check_member_response, self.on_member_response),
                ]

    def _initialize_meta_messages(self):
        super(BarterCommunity, self)._initialize_meta_messages()

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
        return [DefaultConversion(self), BarterConversion(self)]

    def dispersy_cleanup_community(self, message):
        self._has_been_killed = True
        # remove all data from the local database
        self._database.cleanup()
        # re-classify to prevent loading
        return super(BarterCommunity, self).dispersy_cleanup_community(message)

    def unload_community(self):
        logger.debug("unloading the Barter community")
        super(BarterCommunity, self).unload_community()

        self._swift.set_subscribe_channel_close("ALL", False, self.i2ithread_channel_close)

        # cancel outstanding pings
        for record_candidate in self._slope.itervalues():
            self._dispersy.callback.unregister(record_candidate.callback_id)
        self._slope = {}

        # update all up and download values
        self.download_state_callback([], False)

        # store all cached bookkeeping
        self._database.executemany(u"INSERT OR REPLACE INTO book (member, cycle, effort, upload, download) VALUES (?, ?, ?, ?, ?)",
                                   [(book.member.database_id, book.cycle, buffer(book.effort.bytes), book.upload, book.download) for book in self._books.itervalues()])

        # store bandwidth counters
        self._database.executemany(u"INSERT OR REPLACE INTO option (key, value) VALUES (?, ?)",
                                   [(u"total-up", buffer(str(self._total_up))),
                                    (u"total-down", buffer(str(self._total_down))),
                                    (u"associated-up", buffer(str(self._associated_up))),
                                    (u"associated-down", buffer(str(self._associated_down)))])

        # close database
        self._database.close()

    def get_book(self, member):
        # try cache
        book = self._books.get(member.database_id)
        if not book:
            book = Book(member)

            # fetch from database
            try:
                cycle, effort, upload, download = self._database.execute(u"SELECT cycle, effort, upload, download FROM book WHERE member = ?",
                                                                         (member.database_id,)).next()
            except StopIteration:
                now = time()
                book.cycle = int(now / CYCLE_SIZE)
                book.effort = EffortHistory(now)
            else:
                book.cycle = cycle
                book.effort = EffortHistory(str(effort), float(cycle * CYCLE_SIZE))
                book.upload = upload
                book.download = download

            # store in cache
            self._books[member.database_id] = book
            if len(self._books) > self._books_length:
                _, old = self._books.popitem(False)
                self._database.execute(u"INSERT OR REPLACE INTO book (member, cycle, effort, upload, download) VALUES (?, ?, ?, ?)",
                                       (old.member.database_id, old.cycle, buffer(old.effort.bytes), old.upload, old.download))
        return book

    def update_book_from_address(self, swift_address, timestamp, bytes_up, bytes_down, delayed=True):
        """
        Updates the book associated with SWIFT_ADDRESS.

        When we do not yet know the book associated with SWIFT_ADDRESS we will attempt to retrieve
        this information, the update will only occur when this is successful.
        """
        assert self._dispersy.callback.is_current_thread, "Must be called on the dispersy.callback thread"

        def _update(member):
            if member:
                book = self.get_book(member)
                book.cycle = max(book.cycle, int(timestamp / CYCLE_SIZE))
                book.upload += bytes_up
                book.download += bytes_down
                logger.debug("update book for %s +%d -%d", member.mid.encode("HEX"), book.upload, book.download)

                # associated_{up,down} is from our viewpoint while bytes_{up,down} is from the other
                # peers' viewpoint
                self._associated_up += bytes_down
                self._associated_down += bytes_up
                return True
            return False

        def _delayed_update(response):
            member = response.authentication.member
            logger.debug("retrieved member %s from swift address %s:%d [id:%d]",
                         member.mid.encode("HEX"),
                         swift_address[0],
                         swift_address[1],
                         identifier)
            association = self._address_association.setdefault(swift_address, Association())
            association.member = member
            if len(self._address_association) > self._address_association_length:
                self._address_association.popitem(False)
            return _update(response.authentication.member)

        # total_{up,down} is from our viewpoint while bytes_{up,down} is from the other peers'
        # viewpoint
        self._total_up += bytes_down
        self._total_down += bytes_up

        association = self._address_association.setdefault(swift_address, Association())
        if association.member:
            _update(association.member)

        elif delayed and association.retrieve():
            # we do not have the member associated to the address, we will attempt to retrieve it
            cache = MemberRequestCache(_delayed_update)
            identifier = self._dispersy.request_cache.claim(cache)
            meta = self._meta_messages[u"member-request"]
            request = meta.impl(distribution=(self.global_time,),
                                destination=(Candidate(swift_address, True),),  # assume tunnel=True
                                payload=(identifier,))
            logger.debug("trying to obtain member from swift address %s:%d [id:%d]",
                         swift_address[0],
                         swift_address[1],
                         identifier)
            self._dispersy.store_update_forward([request], False, False, True)

        # else:
        #     logger.debug("not yet allowed to obtain member from swift address %s:%d",
        #                  swift_address[0],
        #                  swift_address[1])

    def i2ithread_channel_close(self, *args):
        self._dispersy.callback.register(self._channel_close, args)

    def _channel_close(self, roothash_hex, address, raw_bytes_up, raw_bytes_down, cooked_bytes_up, cooked_bytes_down):
        assert isinstance(roothash_hex, str), type(roothash_hex)
        assert isinstance(address, tuple), type(address)
        assert isinstance(raw_bytes_up, (int, long)), type(raw_bytes_up)
        assert isinstance(raw_bytes_down, (int, long)), type(raw_bytes_down)
        assert isinstance(cooked_bytes_up, (int, long)), type(cooked_bytes_up)
        assert isinstance(cooked_bytes_down, (int, long)), type(cooked_bytes_down)
        assert self._dispersy.callback.is_current_thread, "Must be called on the dispersy.callback thread"
        if cooked_bytes_up or cooked_bytes_down:
            logger.debug("swift channel close %s:%d with +%d -%d", address[0], address[1], cooked_bytes_up, cooked_bytes_down)
            self.update_book_from_address(address, time(), cooked_bytes_up, cooked_bytes_down, delayed=True)

    def download_state_callback(self, states, delayed):
        assert self._dispersy.callback.is_current_thread, "Must be called on the dispersy.callback thread"
        assert isinstance(states, list), type(states)
        assert isinstance(delayed, bool), type(delayed)
        timestamp = int(time())

        # get all swift downloads that have peers
        active = dict((state.get_download().get_def().get_id(), state)
                      for state
                      in states
                      if state.get_download().get_def().get_def_type() == "swift" and state.get_peerlist())

        # OLD is used to determine stopped downloads and peers that left.  NEW will become the next OLD
        old = self._download_states
        new = self._download_states = dict()

        # find downloads that stopped
        for identifier in set(old.iterkeys()).difference(set(active.iterkeys())):
            for address, (up, down) in old[identifier].iteritems():
                logger.debug("%s]  %s:%d  +%d   -%d", identifier.encode("HEX"), address[0], address[1], up, down)
                self.update_book_from_address(address, timestamp, up, down, delayed=delayed)

        for identifier, state in active.iteritems():
            if identifier in old:
                # find peers that left
                for address in set(old[identifier]).difference(set((peer["ip"], peer["port"]) for peer in state.get_peerlist())):
                    up, down = old[identifier][address]
                    logger.debug("%s]  %s:%d  +%d   -%d", identifier.encode("HEX"), address[0], address[1], up, down)
                    self.update_book_from_address(address, timestamp, up, down, delayed=delayed)

            # set OLD for the next call to DOWNLOAD_STATE_CALLBACK
            new[identifier] = dict(((str(peer["ip"]), peer["port"]),
                                    (long(peer["utotal"] * 1024), long(peer["dtotal"] * 1024)))
                                   for peer
                                   in state.get_peerlist()
                                   if peer["utotal"] > 0.0 or peer["dtotal"] > 0.0)

    def on_introduction_request(self, messages):
        try:
            return self._original_on_introduction_request(messages)
        finally:
            cycle = int(time() / CYCLE_SIZE)
            for message in messages:
                if not isinstance(message.candidate, BootstrapCandidate):
                    # logger.debug("received introduction-request message from %s", message.candidate)

                    book = self.get_book(message.authentication.member)
                    if book.cycle < cycle:
                        book.cycle = cycle
                        book.effort.set(cycle * CYCLE_SIZE)

                    self.try_adding_to_slope(message.candidate, book.member)

    def on_introduction_response(self, messages):
        try:
            return self._original_on_introduction_response(messages)
        finally:
            cycle = int(time() / CYCLE_SIZE)
            for message in messages:
                if not isinstance(message.candidate, BootstrapCandidate):
                    # logger.debug("received introduction-response message from %s", message.candidate)

                    book = self.get_book(message.authentication.member)
                    if book.cycle < cycle:
                        book.cycle = cycle
                        book.effort.set(cycle * CYCLE_SIZE)

                    self.try_adding_to_slope(message.candidate, book.member)

    def create_barter_record(self, second_candidate, second_member):
        """
        Create a dispersy-signature-request that encapsulates a barter-record.
        """
        book = self.get_book(second_member)
        upload_first_to_second = book.download
        upload_second_to_first = book.upload
        logger.debug("asking %s to sign effort: %s  self->peer: %d  peer->self: %d",
                     second_member.mid.encode("HEX"),
                     bin(book.effort.long),
                     upload_first_to_second,
                     upload_second_to_first)

        meta = self.get_meta_message(u"barter-record")
        record = meta.impl(authentication=([self._my_member, second_member],),
                           distribution=(self.claim_global_time(),),
                           payload=(book.cycle, book.effort, upload_first_to_second, upload_second_to_first,
                                    # the following parameters are used for debugging only
                                    time(), book.download, book.upload, self._total_up, self._total_down, self._associated_up, self._associated_down,
                                    time(), 0, 0, 0, 0, 0, 0),
                           sign=False)
        return self.create_dispersy_signature_request(second_candidate, record, self.on_signature_response)

    def allow_signature_request(self, message):
        """
        A dispersy-signature-request has been received.

        Return None or a Message.Implementation.
        """
        assert message.name == u"barter-record"
        assert not message.authentication.is_signed
        logger.debug("%s", message)

        _, first_member = message.authentication.signed_members[0]
        _, second_member = message.authentication.signed_members[1]

        if not second_member == self._my_member:
            # the first_member is us.  meaning that we will get duplicate global times because
            # someone else claimed the global time for us
            logger.warning("invalid request.  second_member != my_member")
            return None

        book = self.get_book(first_member)
        proposed_effort = message.payload.effort
        local_effort = book.effort

        if not (message.payload.cycle == proposed_effort.cycle == local_effort.cycle):
            # there is a problem determining the current cycle.  this can be caused by (a)
            # difference in local clock times, (b) record creation during transition between cycles,
            # (c) delay in message processing resulting in issue b.
            logger.warning("invalid request. cycle mismatch (%d ?= %d ?= %d)", message.payload.cycle, proposed_effort.cycle, local_effort.cycle)
            return None
        cycle = message.payload.cycle

        if proposed_effort.long ^ local_effort.long:
            # there is a mismatch in bits, this should not occur on the DAS4, however, we will need
            # to repair this once we go into the big bad world
            logger.warning("bits mismatch. using AND merge (%s != %s)", bin(proposed_effort.long), bin(local_effort.long))

        # merge effort using AND
        effort = EffortHistory(proposed_effort.long & local_effort.long, cycle * CYCLE_SIZE)

        # merge bandwidth using MIN/MAX
        upload_first_to_second = min(message.payload.upload_first_to_second, book.upload)
        upload_second_to_first = max(message.payload.upload_second_to_first, book.download)

        # the first_member took the initiative this cycle.  prevent us from also taking the
        # initiative and create duplicate records this cycle
        self.remove_from_slope(first_member)

        # return the modified barter-record we propose
        meta = self.get_meta_message(u"barter-record")
        return meta.impl(authentication=([first_member, second_member],),
                         distribution=(message.distribution.global_time,),
                         payload=(cycle, effort, upload_first_to_second, upload_second_to_first,
                                  # the following parameters are used for debugging only
                                  message.payload.first_timestamp,
                                  message.payload.first_upload,
                                  message.payload.first_download,
                                  message.payload.first_total_up,
                                  message.payload.first_total_down,
                                  message.payload.first_associated_up,
                                  message.payload.first_associated_down,
                                  time(),
                                  book.upload,
                                  book.download,
                                  self._total_up,
                                  self._total_down,
                                  self._associated_up,
                                  self._associated_down))

    def on_signature_response(self, cache, new_message, changed):
        """
        A dispersy-signature-response has been received.

        Return True or False to either accept or decline the message.
        """
        logger.debug("new message: %s", new_message)

        # TODO: we should ensure that new_message is correct (i.e. all checks made above)

        if new_message:
            # self._observation(new_message.candidate, cache.members[0], time())
            assert cache.request.payload.message.meta == new_message.meta
            return True

        else:
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
                logger.debug("cycle %d.  first climbing phase.  wait %.2f seconds until the next phase",
                             now / CYCLE_SIZE, start_create - now)
                yield start_create - now

            elif start_create <= now < start_idle and len(winners) < self._signature_count:
                logger.debug("cycle %d.  record creation phase.  wait %.2f seconds until record creation",
                             now / CYCLE_SIZE, CYCLE_SIZE * 0.4 / self._signature_count)
                yield (CYCLE_SIZE * 0.4 / self._signature_count) * random()

                # find the best candidate for this cycle
                score = 0
                winner = None
                for member in self._slope.iterkeys():
                    book = self.get_book(member)
                    if book.score > score and not member in winners:
                        winner = member

                if winner:
                    logger.debug("cycle %d.  attempt record creation with %d",
                                 now / CYCLE_SIZE, winner.mid.encode("HEX"))
                    record_candidate = self._slope[winner]

                    # prevent this winner to 'win' again in this cycle
                    winners.add(winner)

                    # TODO: this may be and invalid assumption
                    # assume that the peer is online
                    # record_candidate.history.set(now)

                    self._dispersy.callback.unregister(record_candidate.callback_id)
                    self.create_barter_record(record_candidate.candidate, winner)

                else:
                    logger.debug("cycle %d.  no peers available for record creation (%d peers on slope)",
                                 int(now / CYCLE_SIZE), len(self._slope))

            else:
                logger.debug("cycle %d.  second climbing phase.  wait %.2f seconds until the next phase",
                             now / CYCLE_SIZE, start_next - now)
                assert now >= start_idle or len(winners) >= self._signature_count
                for record_candidate in self._slope.itervalues():
                    self._dispersy.callback.unregister(record_candidate.callback_id)
                self._slope = {}
                winners = set()
                yield start_next - now

    def try_adding_to_slope(self, candidate, member):
        if not member in self._slope:
            book = self.get_book(member)
            # logger.debug("attempt to add %s with score %f", member, book.score)
            if (book.score > 0 and
                (len(self._slope) < self._slope_length or
                 min(self.get_book(mbr).score for mbr in self._slope.iterkeys()) < book.score)):

                logger.debug("add %s with score %f", member, book.score)
                callback_id = self._dispersy.callback.register(self._ping, (candidate, member), delay=50.0)
                self._slope[member] = RecordCandidate(candidate, callback_id)

                if len(self._slope) > self._slope_length:
                    smallest_member = member
                    smallest_score = book.score

                    for member in self._slope.iterkeys():
                        candidate_book = self.get_book(member)
                        if candidate_book.score < smallest_score:
                            smallest_member = member
                            smallest_score = candidate_book.score

                    self.remove_from_slope(smallest_member)

                return True
        return False

    def remove_from_slope(self, member):
        try:
            record_candidate = self._slope.pop(member)
        except KeyError:
            pass
        else:
            self._dispersy.callback.unregister(record_candidate.callback_id)

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
        cycle = int(time() / CYCLE_SIZE)
        for message in messages:
            book = self.get_book(message.payload.member)
            if book.cycle < cycle:
                book.cycle = cycle
                book.effort.set(cycle * CYCLE_SIZE)

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
        cycle = int(time() / CYCLE_SIZE)
        for message in messages:
            self._dispersy.request_cache.pop(message.payload.identifier, PingCache)
            book = self.get_book(message.payload.member)
            if book.cycle < cycle:
                book.cycle = cycle
                book.effort.set(cycle * CYCLE_SIZE)

    def check_barter_record(self, messages):
        # stupidly accept everything...
        return messages

    def on_barter_record(self, messages):
        def ordering(message):
            if message.authentication.members[0].database_id < message.authentication.members[1].database_id:
                return (message.packet_id,
                        message.authentication.members[0].database_id,
                        message.authentication.members[1].database_id,
                        message.distribution.global_time,
                        message.payload.cycle,
                        buffer(message.payload.effort.bytes),
                        message.payload.upload_first_to_second,
                        message.payload.upload_second_to_first,
                        # the following debug values are all according to first_member
                        int(message.payload.first_timestamp),
                        message.payload.first_upload,
                        message.payload.first_download,
                        message.payload.first_total_up,
                        message.payload.first_total_down,
                        message.payload.first_associated_up,
                        message.payload.first_associated_down,
                        # the following debug values are all according to second_member
                        int(message.payload.second_timestamp),
                        message.payload.second_upload,
                        message.payload.second_download,
                        message.payload.second_total_up,
                        message.payload.second_total_down,
                        message.payload.second_associated_up,
                        message.payload.second_associated_down)

            else:
                return (message.packet_id,
                        message.authentication.members[1].database_id,
                        message.authentication.members[0].database_id,
                        message.distribution.global_time,
                        message.payload.cycle,
                        buffer(message.payload.effort.bytes),
                        message.payload.upload_second_to_first,
                        message.payload.upload_first_to_second,
                        # the following debug values are all according to second_member
                        int(message.payload.second_timestamp),
                        message.payload.second_upload,
                        message.payload.second_download,
                        message.payload.second_total_up,
                        message.payload.second_total_down,
                        message.payload.second_associated_up,
                        message.payload.second_associated_down,
                        # the following debug values are all according to first_member
                        int(message.payload.first_timestamp),
                        message.payload.first_upload,
                        message.payload.first_download,
                        message.payload.first_total_up,
                        message.payload.first_total_down,
                        message.payload.first_associated_up,
                        message.payload.first_associated_down)

        logger.debug("storing %d barter records", len(messages))
        self._database.executemany(u"INSERT OR REPLACE INTO record VALUES (?, ?, ?, ?, ?, ?, ? ,?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (ordering(message) for message in messages))

    def check_member_request(self, messages):
        # stupidly accept everything...
        return messages

    def on_member_request(self, messages):
        meta = self._meta_messages[u"member-response"]
        responses = [meta.impl(authentication=(self._my_member,),
                               distribution=(self._global_time,),
                               destination=(request.candidate,),
                               payload=(request.payload.identifier,))
                     for request
                     in messages]
        self._dispersy.store_update_forward(responses, False, False, True)

    def check_member_response(self, messages):
        # stupidly accept everything...
        return messages

    def on_member_response(self, messages):
        for message in messages:
            cache = self._dispersy.request_cache.pop(message.payload.identifier, MemberRequestCache)
            if cache:
                cache.func(message)
