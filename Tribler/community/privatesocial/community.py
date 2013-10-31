# Written by Niels Zeilemaker
import sys

from conversion import SocialConversion
from payload import TextPayload
from destination import FOAFDestination

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
from Tribler.community.privatesemantic.community import PoliForwardCommunity

ENCRYPTION = True

class SocialCommunity(Community):
    def __init__(self, dispersy, master, integrate_with_tribler=True, encryption=ENCRYPTION):
        super(SocialCommunity, self).__init__(dispersy, master)
        self.encryption = bool(encryption)

        self._dispersy_sync_skip_enable = False

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

    def dispersy_claim_sync_bloom_filter(self, request_cache):
        # TODO change with only shared friend sync
        return Community.dispersy_claim_sync_bloom_filter(self, request_cache)

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
            body = message.decrypt(self._db.get_my_keys())
            if body:
                decrypted_messages.append((message.candidate, body))
            else:
                # TODO: add to partial sync table
                pass

            log("dispersy.log", "handled-record", type="encrypted", global_time=message._distribution.global_time, could_decrypt=bool(body))

        if decrypted_messages:
            self._dispersy.on_incoming_packets(decrypted_messages, cache=False)

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

    def set_key(self, friend, key):
        self._keys[friend] = key

    def get_key(self, friend):
        return self._keys[friend]

    def set_my_key(self, key):
        self._mykeys.append(key)

    def get_my_keys(self):
        return self._mykeys
