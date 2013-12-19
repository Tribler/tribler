import logging
logger = logging.getLogger(__name__)

try:
    # python 2.7 only...
    from collections import OrderedDict
except ImportError:
    from Tribler.dispersy.python27_ordereddict import OrderedDict

from time import time

from .conversion import BarterConversion
from .database import BarterDatabase
from .payload import BarterRecordPayload

from Tribler.dispersy.authentication import DoubleMemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import LastSyncDistribution, GlobalTimePruning
from Tribler.dispersy.message import BatchConfiguration, Message
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


class RecordCandidate(object):

    """
    Container class for a candidate that is on our slope.
    """
    def __init__(self, candidate, callback_id):
        super(RecordCandidate, self).__init__()
        self.candidate = candidate
        self.callback_id = callback_id


class Book(object):

    """
    Container class for all the bookkeeping information per peer.
    """
    def __init__(self, member):
        super(Book, self).__init__()
        self.member = member
        self.timestamp = 0.0
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

    def __init__(self, dispersy, master):
        logger.debug("loading the Barter community")
        super(BarterCommunity, self).__init__(dispersy, master)

        # _DATABASE stores all direct observations and indirect hearsay
        self._database = BarterDatabase(self._dispersy)
        self._database.open()

        options = dict(self._database.execute(u"SELECT key, value FROM option"))
        # _TOTAL_UP and _TOTAL_DOWN contain the total up and down statistics received from swift
        self._total_up = long(str(options.get(u"total-up", 0)))
        self._total_down = long(str(options.get(u"total-down", 0)))

        # _BOOKS cache (reduce _DATABASE access)
        self._books_length = 512
        self._books = OrderedDict()

        # _HAS_BEEN_KILLED makes Tribler remove the community pointer
        self._has_been_killed = False

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
                ]

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

        # store all cached bookkeeping
        self._database.executemany(u"INSERT OR REPLACE INTO book (member, timestamp, upload, download) VALUES (?, ?, ?, ?)",
                                   [(book.member.database_id, book.timestamp, book.upload, book.download) for book in self._books.itervalues()])

        # store bandwidth counters
        self._database.executemany(u"INSERT OR REPLACE INTO option (key, value) VALUES (?, ?)",
                                   [(u"total-up", buffer(str(self._total_up))),
                                    (u"total-down", buffer(str(self._total_down)))])

        # close database
        self._database.close()

    def get_book(self, member):
        # try cache
        book = self._books.get(member.database_id)
        if not book:
            book = Book(member)

            # fetch from database
            try:
                timestamp, upload, download = self._database.execute(u"SELECT timestamp, upload, download FROM book WHERE member = ?",
                                                                     (member.database_id,)).next()
            except StopIteration:
                pass
            else:
                book.timestamp = timestamp
                book.upload = upload
                book.download = download

            # store in cache
            self._books[member.database_id] = book
            if len(self._books) > self._books_length:
                _, old = self._books.popitem(False)
                self._database.execute(u"INSERT OR REPLACE INTO book (member, timestamp, upload, download) VALUES (?, ?, ?)",
                                       (old.member.database_id, old.timestamp, old.upload, old.download))
        return book

    def create_barter_record(self, second_candidate, second_member):
        """
        Create a dispersy-signature-request that encapsulates a barter-record.
        """
        book = self.get_book(second_member)
        upload_first_to_second = book.download
        upload_second_to_first = book.upload
        logger.debug("asking %s to sign self->peer: %d  peer->self: %d",
                     second_member.mid.encode("HEX"),
                     upload_first_to_second,
                     upload_second_to_first)

        meta = self.get_meta_message(u"barter-record")
        record = meta.impl(authentication=([self._my_member, second_member],),
                           distribution=(self.claim_global_time(),),
                           payload=(upload_first_to_second, upload_second_to_first,
                                    # the following parameters are used for debugging only
                                    time(), book.download, book.upload, self._total_up, self._total_down,
                                    0.0, 0, 0, 0, 0,),
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

        # merge bandwidth using MIN/MAX
        upload_first_to_second = min(message.payload.upload_first_to_second, book.upload)
        upload_second_to_first = max(message.payload.upload_second_to_first, book.download)

        # return the modified barter-record we propose
        meta = self.get_meta_message(u"barter-record")
        return meta.impl(authentication=([first_member, second_member],),
                         distribution=(message.distribution.global_time,),
                         payload=(upload_first_to_second, upload_second_to_first,
                                  # the following parameters are used for debugging only
                                  message.payload.first_timestamp,
                                  message.payload.first_upload,
                                  message.payload.first_download,
                                  message.payload.first_total_up,
                                  message.payload.first_total_down,
                                  time(),
                                  book.upload,
                                  book.download,
                                  self._total_up,
                                  self._total_down))

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
            return False

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
                        message.payload.upload_first_to_second,
                        message.payload.upload_second_to_first,
                        # the following debug values are all according to first_member
                        int(message.payload.first_timestamp),
                        message.payload.first_upload,
                        message.payload.first_download,
                        message.payload.first_total_up,
                        message.payload.first_total_down,
                        # the following debug values are all according to second_member
                        int(message.payload.second_timestamp),
                        message.payload.second_upload,
                        message.payload.second_download,
                        message.payload.second_total_up,
                        message.payload.second_total_down)

            else:
                return (message.packet_id,
                        message.authentication.members[1].database_id,
                        message.authentication.members[0].database_id,
                        message.distribution.global_time,
                        message.payload.upload_second_to_first,
                        message.payload.upload_first_to_second,
                        # the following debug values are all according to second_member
                        int(message.payload.second_timestamp),
                        message.payload.second_upload,
                        message.payload.second_download,
                        message.payload.second_total_up,
                        message.payload.second_total_down,
                        # the following debug values are all according to first_member
                        int(message.payload.first_timestamp),
                        message.payload.first_upload,
                        message.payload.first_download,
                        message.payload.first_total_up,
                        message.payload.first_total_down)

        logger.debug("storing %d barter records", len(messages))
        self._database.executemany(u"INSERT OR REPLACE INTO record VALUES (?, ?, ?, ?, ?, ?, ? ,?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (ordering(message) for message in messages))
