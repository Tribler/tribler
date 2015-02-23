# Written by Niels Zeilemaker
from conversion import DemersConversion
from payload import TextPayload

from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import FullSyncDistribution
from Tribler.dispersy.message import Message, DelayMessageByProof
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.tool.lencoder import log


class DemersTest(Community):

    def initiate_meta_messages(self):
        return super(DemersTest, self).initiate_meta_messages() + [
            Message(self, u"text",
                    MemberAuthentication(),
                    PublicResolution(),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128),
                    CommunityDestination(node_count=10), TextPayload(),
                    self.check_text,
                    self.on_text)
        ]

    def initiate_conversions(self):
        return [DefaultConversion(self), DemersConversion(self)]

    @property
    def dispersy_sync_response_limit(self):
        return 1

    @property
    def dispersy_sync_skip_enable(self):
        return False

    @property
    def dispersy_sync_cache_enable(self):
        return False

    def create_text(self, text, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"text")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.claim_global_time(),),
                            payload=(text,))
        self._dispersy.store_update_forward([message], store, update, forward)

    def check_text(self, messages):
        for message in messages:
            allowed, _ = self._timeline.check(message)
            if allowed:
                yield message
            else:
                yield DelayMessageByProof(message)

    def on_text(self, messages):
        for message in messages:
            log("dispersy.log", "handled-record", type="text", global_time=message._distribution.global_time)
