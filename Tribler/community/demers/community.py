# Written by Niels Zeilemaker

from Tribler.community.basecommunity import BaseCommunity
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import FullSyncDistribution
from Tribler.dispersy.message import Message, DelayMessageByProof
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.tool.lencoder import log

# TODO REMOVE BACKWARD COMPATIBILITY: Delete this import
from Tribler.community.demers.compatibility import DemersCompatibility, DemersConversion


class DemersTest(BaseCommunity):

    def initiate_meta_messages(self):
        self.register_traversal("Text",
                                MemberAuthentication(),
                                PublicResolution(),
                                FullSyncDistribution(enable_sequence_number=False,
                                                     synchronization_direction=u"DESC",
                                                     priority=128),
                                CommunityDestination(node_count=10))

        # TODO REMOVE BACKWARD COMPATIBILITY: Delete deprecated call
        return (super(DemersTest, self).initiate_meta_messages() +
                self.compatibility.deprecated_meta_messages())

    def initiate_conversions(self):
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete this method
        return [DefaultConversion(self), DemersConversion(self)]

    def __init__(self, *args, **kwargs):
        super(DemersTest, self).__init__(*args, **kwargs)

        # TODO REMOVE BACKWARD COMPATIBILITY: Delete this method
        self.compatibility = DemersCompatibility(self)
        self.compatibility_mode = True

    def on_basemsg(self, messages):
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete this method

        # Apparently the big switch is happening,
        # start talking newspeak:
        self.compatibility_mode = False
        super(DemersTest, self).on_basemsg(messages)

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
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete if statement and positive case
        if self.compatibility_mode:
            meta = self.get_meta_message(u"text")
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.claim_global_time(),),
                                payload=(text,))
            self._dispersy.store_update_forward([message], store, update, forward)
        else:
            options = self.get_traversal("Text", auth=(self._my_member,),
                                         dist=(self.claim_global_time(),))
            self.store_update_forward(options, "demers.Text", store, update, forward, text)

    def check_text(self, header, message):
        allowed, _ = self._timeline.check(header)
        if allowed:
            yield header
        else:
            yield DelayMessageByProof(header)

    def on_text(self, header, message):
        log("dispersy.log", "handled-record", type="text", global_time=header._distribution.global_time)
