"""
Example file
"""

import logging
logger = logging.getLogger(__name__)

from Tribler.community.basecommunity import BaseCommunity
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import FullSyncDistribution
from Tribler.dispersy.message import BatchConfiguration, Message, DelayMessageByProof
from Tribler.dispersy.resolution import LinearResolution

# TODO REMOVE BACKWARD COMPATIBILITY: Delete this import
from Tribler.community.template.compatibility import Conversion, TemplateCompatibility

class TemplateCommunity(BaseCommunity):

    def initiate_meta_messages(self):
        self.register_traversal("Text",
                                MemberAuthentication(),
                                LinearResolution(),
                                FullSyncDistribution(enable_sequence_number=False,
                                                     synchronization_direction=u"ASC",
                                                     priority=128),
                                CommunityDestination(node_count=10))

        # TODO REMOVE BACKWARD COMPATIBILITY: Delete deprecated call
        return (super(TemplateCommunity, self).initiate_meta_messages() +
                self.compatibility.deprecated_meta_messages())

    def initiate_conversions(self):
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete this method
        return [DefaultConversion(self), Conversion(self)]

    def __init__(self, *args, **kwargs):
        super(TemplateCommunity, self).__init__(*args, **kwargs)

        # TODO REMOVE BACKWARD COMPATIBILITY: Delete this method
        self.compatibility = TemplateCompatibility(self)
        self.compatibility_mode = True

    def on_basemsg(self, messages):
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete this method

        # Apparently the big switch is happening,
        # start talking newspeak:
        self.compatibility_mode = False
        super(TemplateCommunity, self).on_basemsg(messages)

    def check_text(self, header, message):
        allowed, _ = self._timeline.check(header)
        if allowed:
            yield header
        else:
            yield DelayMessageByProof(header)

    def on_text(self, header, message):
        logger.debug("someone says '%s'", message.text)
