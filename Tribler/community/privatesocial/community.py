# Written by Niels Zeilemaker
import sys

from conversion import SocialConversion
from payload import TextPayload
from collections import defaultdict
from hashlib import sha1

from Tribler.dispersy.authentication import MemberAuthentication, \
    NoAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import FullSyncDistribution
from Tribler.dispersy.message import Message
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.tool.lencoder import log
from Tribler.community.privatesocial.payload import EncryptedPayload
from Tribler.community.privatesemantic.rsa import rsa_encrypt, rsa_sign, rsa_verify
from Tribler.community.privatesemantic.community import PoliForwardCommunity, \
    HForwardCommunity, PForwardCommunity, PING_INTERVAL, ForwardCommunity

from random import choice
from Tribler.dispersy.member import Member
from database import FriendDatabase

ENCRYPTION = True

class SocialCommunity(Community):
    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION):
        super(SocialCommunity, self).__init__(dispersy, master)
        self.encryption = bool(encryption)

        self._friend_db = FriendDatabase(dispersy)
        self._friend_db.open()

    def unload_community(self):
        super(SocialCommunity, self).unload_community()
        self._friend_db.close()

    def initiate_meta_messages(self):
        # TODO replace with modified full sync
        return [Message(self, u"text", MemberAuthentication(encoding="sha1"), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128), CandidateDestination(), TextPayload(), self._dispersy._generic_timeline_check, self.on_text),
                Message(self, u"encrypted", NoAuthentication(), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128), CandidateDestination(), EncryptedPayload(), self._dispersy._generic_timeline_check, self.on_encrypted)]

    def initiate_conversions(self):
        return [DefaultConversion(self), SocialConversion(self)]

    @property
    def dispersy_sync_skip_enable(self):
        return False

    @property
    def dispersy_sync_cache_enable(self):
        return False

    def dispersy_claim_sync_bloom_filter(self, request_cache):
        # TODO change with only shared friend sync
        return Community.dispersy_claim_sync_bloom_filter(self, request_cache)

    def send_introduction_request(self, destination, introduce_me_to=None, allow_sync=True):
        # never sync with a non-friend
        if not self.is_taste_buddy(destination):
            allow_sync = False

        super(SocialCommunity).send_introduction_request(self, destination, introduce_me_to, allow_sync)

    def _select_and_fix(self, syncable_messages, global_time, to_select, higher=True):
        # first select_and_fix based on friendsync table
        if higher:
            data = list(self._friend_db.execute(u"SELECT global_time, sync_id FROM friendsync WHERE global_time > ? ORDER BY global_time ASC LIMIT ?",
                                                    (global_time, to_select + 1)))
        else:
            data = list(self._friend_db.execute(u"SELECT global_time, sync_id FROM friendsync WHERE global_time < ? ORDER BY global_time DESC LIMIT ?",
                                                    (global_time, to_select + 1)))

        fixed = False
        if len(data) > to_select:
            fixed = True

            # if last 2 packets are equal, then we need to drop those
            global_time = data[-1][0]
            del data[-1]
            while data and data[-1][0] == global_time:
                del data[-1]

        # next get actual packets from sync table, friendsync does not contain any non-syncable_messages hence this variable isn't used
        sync_ids = tuple(sync_id for _, sync_id in data)
        if higher:
            data = list(self._dispersy._database.execute(u"SELECT global_time, packet FROM sync WHERE undone = 0 AND id IN (" + ", ".join("?" * len(sync_ids)) + ") ORDER BY global_time ASC", sync_ids))
        else:
            data = list(self._dispersy._database.execute(u"SELECT global_time, packet FROM sync WHERE undone = 0 AND id IN (" + ", ".join("?" * len(sync_ids)) + ") ORDER BY global_time DESC", sync_ids))

        if not higher:
            data.reverse()

        return data, fixed

    def _dispersy_claim_sync_bloom_filter_modulo(self):
        raise NotImplementedError()

    def create_text(self, text, friends):
        assert all(isinstance(friend, str) for friend in friends)

        meta = self.get_meta_message(u"text")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.claim_global_time(),),
                            payload=(text,))

        for friend in friends:
            self.create_encrypted(message.packet, friend)

        self._dispersy.store_update_forward([message], True, True, False)

    def on_text(self, messages):
        for message in messages:
            log("dispersy.log", "handled-record", type="text", global_time=message._distribution.global_time)

    def create_encrypted(self, message_str, dest_friend):
        # get rsa key
        rsakey, keyhash = self._friend_db.get_friend(dest_friend)

        # encrypt message
        encrypted_message = rsa_encrypt(rsakey, message_str)

        meta = self.get_meta_message(u"encrypted")
        message = meta.impl(distribution=(self.claim_global_time(),),
                            payload=(keyhash, encrypted_message))

        self._dispersy.store_update_forward([message], True, False, True)

    def on_encrypted(self, messages):
        decrypted_messages = []

        for message in messages:
            body = message.decrypt(self._db.get_my_keys())
            if body:
                decrypted_messages.append((message.candidate, body))
            else:
                self._friend_db.add_message(message.packet_id, message._distribution.global_time, message.payload.pubkey)

            log("dispersy.log", "handled-record", type="encrypted", global_time=message._distribution.global_time, could_decrypt=bool(body))

        if decrypted_messages:
            self._dispersy.on_incoming_packets(decrypted_messages, cache=False)

    def create_ping_requests(self):
        while True:
            to_maintain = self.filter_tb(self.yield_taste_buddies())

            # from the to_maintain list check if we need to send any pings
            tbs = [tb.candidate for tb in to_maintain if tb.time_remaining() < PING_INTERVAL]
            if len(tbs) > 0:
                identifier = self._dispersy.request_cache.claim(ForwardCommunity.PingRequestCache(self, tbs))
                self._create_pingpong(u"ping", tbs, identifier)

            yield PING_INTERVAL

    def get_tbs_from_peercache(self, nr):
        peers = super(SocialCommunity).get_tbs_from_peercache(nr)
        return self.filter_tb(peers)

    def filter_tb(self, tbs):
        to_maintain = set()

        foafs = defaultdict(list)
        my_key_hashes = [keyhash for _, keyhash in self._friend_db.get_my_keys()]
        for tb in tbs:
            # if a peer has overlap with any of my_key_hashes, its my friend -> maintain connection
            if any(map(tb.does_overlap, my_key_hashes)):
                to_maintain.add(tb)

            # else add this foaf as a possible candidate to be used as a backup for a friend
            else:
                for keyhash in tb.overlap:
                    foafs[keyhash].append(tb)

        # for each friend we maintain an additional connection to at least one foaf
        # this peer is chosen randomly to attempt to load balance these pings
        for keyhash, tbs in foafs.iteritems():
            to_maintain.add(choice(tbs))

        print >> sys.stderr, "Should maintain", len(to_maintain), "connections instead of", len(tbs)

        return to_maintain

    def get_rsa_member(self):
        rsakey = self._friend_db.get_my_keys()[-1]
        return RSAMember(rsakey)

class RSAMember(Member):
    def __init__(self, dispersy, key):
        self._key = key
        self._mid = sha1(self._key).digest()
        self._signature_length = key.size / 8
        self._tags = []

    def has_identity(self, community):
        return True

    def verify(self, data, signature, offset=0, length=0):
        assert isinstance(data, str)
        assert isinstance(signature, str)
        assert isinstance(offset, (int, long))
        assert isinstance(length, (int, long))
        assert len(signature) == self._signature_length

        message = data[offset:offset + (length or len(data))]
        return rsa_verify(self._key, message, signature)

    def sign(self, data, offset=0, length=0):
        assert isinstance(data, str)
        assert isinstance(offset, (int, long))
        assert isinstance(length, (int, long))

        message = data[offset:offset + (length or len(data))]
        return rsa_sign(self._key, message)

class NoFSocialCommunity(SocialCommunity, HForwardCommunity):

    @classmethod
    def load_community(cls, dispersy, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None, use_cardinality=True):
        dispersy_database = dispersy.database
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(dispersy, master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)
        else:
            return super(NoFSocialCommunity, cls).load_community(dispersy, master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)

    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None, use_cardinality=True):
        SocialCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption)
        HForwardCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption, 0, max_prefs, max_fprefs, max_taste_buddies=sys.maxint)

    def initiate_conversions(self):
        return HForwardCommunity.initiate_conversions(self) + [SocialConversion(self)]

    def initiate_meta_messages(self):
        return HForwardCommunity.initiate_meta_messages(self) + SocialCommunity.initiate_meta_messages(self)

class PSocialCommunity(SocialCommunity, PForwardCommunity):

    @classmethod
    def load_community(cls, dispersy, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None, use_cardinality=True):
        dispersy_database = dispersy.database
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(dispersy, master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)
        else:
            return super(PSocialCommunity, cls).load_community(dispersy, master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)

    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None, use_cardinality=True):
        SocialCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption)
        PForwardCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs, max_taste_buddies=sys.maxint)

    def initiate_conversions(self):
        return PForwardCommunity.initiate_conversions(self) + [SocialConversion(self)]

    def initiate_meta_messages(self):
        return PForwardCommunity.initiate_meta_messages(self) + SocialCommunity.initiate_meta_messages(self)

class HSocialCommunity(SocialCommunity, HForwardCommunity):

    @classmethod
    def load_community(cls, dispersy, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None, use_cardinality=True):
        dispersy_database = dispersy.database
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(dispersy, master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)
        else:
            return super(HSocialCommunity, cls).load_community(dispersy, master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs)

    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None, use_cardinality=True):
        SocialCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption)
        HForwardCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs, max_taste_buddies=sys.maxint)

    def initiate_conversions(self):
        return HForwardCommunity.initiate_conversions(self) + [SocialConversion(self)]

    def initiate_meta_messages(self):
        return HForwardCommunity.initiate_meta_messages(self) + SocialCommunity.initiate_meta_messages(self)

class PoliSocialCommunity(SocialCommunity, PoliForwardCommunity):

    @classmethod
    def load_community(cls, dispersy, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None, use_cardinality=True):
        dispersy_database = dispersy.database
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(dispersy, master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs, use_cardinality=use_cardinality)
        else:
            return super(PoliSocialCommunity, cls).load_community(dispersy, master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, max_prefs=max_prefs, max_fprefs=max_fprefs, use_cardinality=use_cardinality)

    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION, max_prefs=None, max_fprefs=None, use_cardinality=True):
        SocialCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption)
        PoliForwardCommunity.__init__(self, dispersy, master, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs, max_taste_buddies=sys.maxint, use_cardinality=use_cardinality)

    def initiate_conversions(self):
        return PoliForwardCommunity.initiate_conversions(self) + [SocialConversion(self)]

    def initiate_meta_messages(self):
        return PoliForwardCommunity.initiate_meta_messages(self) + SocialCommunity.initiate_meta_messages(self)
