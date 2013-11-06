# Written by Niels Zeilemaker
import sys

from conversion import SocialConversion
from payload import TextPayload
from destination import FOAFDestination
from collections import defaultdict

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
from Tribler.community.privatesemantic.rsa import rsa_encrypt, key_to_bytes
from Tribler.community.privatesemantic.community import PoliForwardCommunity, \
    HForwardCommunity, PForwardCommunity, PING_INTERVAL, ForwardCommunity

from random import choice

ENCRYPTION = True

class SocialCommunity(Community):
    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION):
        super(SocialCommunity, self).__init__(dispersy, master)
        self.encryption = bool(encryption)

        if integrate_with_tribler:
            raise NotImplementedError()
        else:
            self._friend_db = Das4DBStub(dispersy)

    def initiate_meta_messages(self):
        # TODO replace with modified full sync
        return [Message(self, u"text", MemberAuthentication(encoding="bin"), PublicResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128), CandidateDestination(), TextPayload(), self._dispersy._generic_timeline_check, self.on_text),
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
        if self.is_taste_buddy(destination):
            allow_sync = False

        super(SocialCommunity).send_introduction_request(self, destination, introduce_me_to, allow_sync)

    def create_text(self, text, friends):
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
        rsakey = self.db.get_key(dest_friend)

        # convert key into string
        strkey = key_to_bytes(rsakey)

        # encrypt message
        encrypted_message = rsa_encrypt(rsakey, message_str)

        meta = self.get_meta_message(u"encrypted")
        message = meta.impl(distribution=(self.claim_global_time(),),
                            payload=(strkey, encrypted_message))

        self._dispersy.store_update_forward([message], True, False, True)

    def on_encrypted(self, messages):
        decrypted_messages = []

        for message in messages:
            body = message.decrypt([key for key,_ in self._db.get_my_keys()])
            if body:
                decrypted_messages.append((message.candidate, body))
            else:
                # TODO: add to partial sync table
                pass

            log("dispersy.log", "handled-record", type="encrypted", global_time=message._distribution.global_time, could_decrypt=bool(body))

        if decrypted_messages:
            self._dispersy.on_incoming_packets(decrypted_messages, cache=False)
            
    def create_ping_requests(self):
        while True:
            to_maintain = set()
            
            foafs = defaultdict(list)
            my_key_hashes = [keyhash for _,keyhash in self._friend_db.get_my_keys()]
            for tb in self.yield_taste_buddies():
                #if a peer has overlap with any of my key_hashes, its my friend -> maintain connection
                if any(map(tb.does_overlap, my_key_hashes)):
                    to_maintain.append(tb)
                    
                #else add this foaf as a possible candidate to be used as a backup for a friend
                else:
                    for keyhash in tb.overlap:
                        foafs[keyhash].append(tb)
            
            # for each friend we maintain an additional connection to at least one foaf
            # this peer is chosen randomly to attempt to load balance these pings
            for keyhash, tbs in foafs.iteritems():
                to_maintain.append(choice(tbs))
            
            # from the to_maintain list check if we need to send any pings
            tbs = [tb.candidate for tb in to_maintain if tb.time_remaining() < PING_INTERVAL]
            if len(tbs) > 0:
                identifier = self._dispersy.request_cache.claim(ForwardCommunity.PingRequestCache(self, tbs))
                self._create_pingpong(u"ping", tbs, identifier)
            
            yield PING_INTERVAL

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

class Das4DBStub():
    def __init__(self, dispersy):
        self._dispersy = dispersy

        self._keys = {}
        self._mykeys = []

    def set_key(self, friend, key, keyhash):
        self._keys[friend] = (key, keyhash)

    def get_key(self, friend):
        return self._keys[friend]
    
    def get_keys(self):
        return self._keys

    def set_my_key(self, key, keyhash):
        self._mykeys.append((key, keyhash))

    def get_my_keys(self):
        return self._mykeys
