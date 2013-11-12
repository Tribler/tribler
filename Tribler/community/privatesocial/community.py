# Written by Niels Zeilemaker
import sys

from conversion import SocialConversion
from payload import TextPayload
from collections import defaultdict
from hashlib import sha1
from binascii import hexlify

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
    HForwardCommunity, PForwardCommunity, PING_INTERVAL, ForwardCommunity, \
    TasteBuddy

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

        self._orig_get_members_from_id = self._dispersy.get_members_from_id
        self._dispersy.get_members_from_id = self.get_rsa_members_from_id
        
        # never sync while taking a step, only sync with friends
        self._orig_send_introduction_request = self.send_introduction_request
        self.send_introduction_request = lambda destination, introduce_me_to=None, allow_sync=True, advice=True: self._orig_send_introduction_request(destination, introduce_me_to, False, True)
        
        self._dispersy.callback.register(self.sync_with_friends)

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

    def sync_with_friends(self):
        while True:
            tbs = list(self.yield_taste_buddies())
            if tbs:
                interval = max(300 / float(len(tbs)), 5.0)
                for tb in tbs:
                    self._orig_send_introduction_request(tb.candidate, None, True, False)
                    yield interval
            else:
                yield 15.0

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
        peers = [TasteBuddy(overlap, (ip, port)) for overlap, ip, port in self._peercache.get_peers()[:nr]]
        return self.filter_tb(peers)

    def filter_tb(self, tbs):
        _tbs = list(tbs)

        to_maintain = set()

        foafs = defaultdict(list)
        my_key_hashes = [keyhash for _, keyhash in self._friend_db.get_my_keys()]
        for tb in _tbs:
            # if a peer has overlap with any of my_key_hashes, its my friend -> maintain connection
            if any(map(tb.does_overlap, my_key_hashes)):
                to_maintain.add(tb)

            # else add this foaf as a possible candidate to be used as a backup for a friend
            else:
                for keyhash in tb.overlap:
                    foafs[keyhash].append(tb)

        # for each friend we maintain an additional connection to at least one foaf
        # this peer is chosen randomly to attempt to load balance these pings
        for keyhash, f_tbs in foafs.iteritems():
            to_maintain.add(choice(f_tbs))

        print >> sys.stderr, "Should maintain", len(to_maintain), "connections instead of", len(_tbs)

        return to_maintain

    def add_possible_taste_buddies(self):
        my_key_hashes = [keyhash for _, keyhash in self._friend_db.get_my_keys()]
        def prefer_my_friends(a, b):
            if a.does_overlap(my_key_hashes):
                return 1
            if b.does_overlap(my_key_hashes):
                return -1
            return cmp(a, b)

        self.possible_taste_buddies.sort(cmp=prefer_my_friends, reverse=True)

        print >> sys.stderr, "After sorting", map(str, self.possible_taste_buddies), [tb.does_overlap(my_key_hashes) for tb in self.possible_taste_buddies]

    def get_rsa_members_from_id(self, mid):
        try:
            # dispersy uses the sha digest, we use a sha hexdigest converted into long
            # convert it to our long format
            keyhash = long(hexlify(mid), 16)

            rsakey = self._friend_db.get_friend_by_hash(keyhash)
            return RSAMember(rsakey)
        except:
            return self._orig_get_members_from_id(mid)

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

class NoFSocialCommunity(HForwardCommunity, SocialCommunity):

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

    def unload_community(self):
        HForwardCommunity.unload_community(self)
        SocialCommunity.unload_community(self)

    def add_possible_taste_buddies(self, possibles):
        HForwardCommunity.add_possible_taste_buddies(self, possibles)
        SocialCommunity.add_possible_taste_buddies(self)

    def create_ping_requests(self):
        return SocialCommunity.create_ping_requests(self)

    def get_tbs_from_peercache(self, nr):
        return SocialCommunity.get_tbs_from_peercache(self, nr)

    def _dispersy_claim_sync_bloom_filter_modulo(self):
        return SocialCommunity._dispersy_claim_sync_bloom_filter_modulo(self)

    def _select_and_fix(self, syncable_messages, global_time, to_select, higher=True):
        return SocialCommunity._select_and_fix(self, syncable_messages, global_time, to_select, higher)

    def send_introduction_request(self, destination, introduce_me_to=None, allow_sync=True):
        return HForwardCommunity.send_introduction_request(self, *SocialCommunity.send_introduction_request(self, destination, introduce_me_to, allow_sync))

class PSocialCommunity(PForwardCommunity, SocialCommunity):

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

    def unload_community(self):
        PForwardCommunity.unload_community(self)
        SocialCommunity.unload_community(self)

    def create_ping_requests(self):
        return SocialCommunity.create_ping_requests(self)

    def get_tbs_from_peercache(self, nr):
        return SocialCommunity.get_tbs_from_peercache(self, nr)

    def _dispersy_claim_sync_bloom_filter_modulo(self):
        return SocialCommunity._dispersy_claim_sync_bloom_filter_modulo(self)

    def _select_and_fix(self, syncable_messages, global_time, to_select, higher=True):
        return SocialCommunity._select_and_fix(self, syncable_messages, global_time, to_select, higher)

    def send_introduction_request(self, destination, introduce_me_to=None, allow_sync=True):
        return PForwardCommunity.send_introduction_request(self, *SocialCommunity.send_introduction_request(self, destination, introduce_me_to, allow_sync))

class HSocialCommunity(HForwardCommunity, SocialCommunity):

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

    def unload_community(self):
        HForwardCommunity.unload_community(self)
        SocialCommunity.unload_community(self)

    def add_possible_taste_buddies(self, possibles):
        HForwardCommunity.add_possible_taste_buddies(self, possibles)
        SocialCommunity.add_possible_taste_buddies(self)

    def create_ping_requests(self):
        return SocialCommunity.create_ping_requests(self)

    def get_tbs_from_peercache(self, nr):
        return SocialCommunity.get_tbs_from_peercache(self, nr)

    def _dispersy_claim_sync_bloom_filter_modulo(self):
        return SocialCommunity._dispersy_claim_sync_bloom_filter_modulo(self)

    def _select_and_fix(self, syncable_messages, global_time, to_select, higher=True):
        return SocialCommunity._select_and_fix(self, syncable_messages, global_time, to_select, higher)

    def send_introduction_request(self, destination, introduce_me_to=None, allow_sync=True):
        return HForwardCommunity.send_introduction_request(self, *SocialCommunity.send_introduction_request(self, destination, introduce_me_to, allow_sync))

class PoliSocialCommunity(PoliForwardCommunity, SocialCommunity):

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

    def unload_community(self):
        PoliForwardCommunity.unload_community(self)
        SocialCommunity.unload_community(self)

    def add_possible_taste_buddies(self, possibles):
        PoliForwardCommunity.add_possible_taste_buddies(self, possibles)
        SocialCommunity.add_possible_taste_buddies(self)

    def create_ping_requests(self):
        return SocialCommunity.create_ping_requests(self)

    def get_tbs_from_peercache(self, nr):
        return SocialCommunity.get_tbs_from_peercache(self, nr)

    def _dispersy_claim_sync_bloom_filter_modulo(self):
        return SocialCommunity._dispersy_claim_sync_bloom_filter_modulo(self)

    def _select_and_fix(self, syncable_messages, global_time, to_select, higher=True):
        return SocialCommunity._select_and_fix(self, syncable_messages, global_time, to_select, higher)

    def send_introduction_request(self, destination, introduce_me_to=None, allow_sync=True):
        return PoliForwardCommunity.send_introduction_request(self, *SocialCommunity.send_introduction_request(self, destination, introduce_me_to, allow_sync))
