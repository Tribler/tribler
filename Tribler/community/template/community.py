"""
Example file
"""

from Tribler.dispersy.logger import get_logger
logger = get_logger(__name__)

from .conversion import Conversion
from .payload import TextPayload

from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import FullSyncDistribution
from Tribler.dispersy.message import BatchConfiguration, Message, DelayMessageByProof
from Tribler.dispersy.resolution import LinearResolution


class TemplateCommunity(Community):

    def initiate_meta_messages(self):
        return [Message(self, u"text", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=128), CommunityDestination(node_count=10), TextPayload(), self.check_text, self.on_text, batch=BatchConfiguration(max_window=5.0))]

    def initiate_conversions(self):
        return [DefaultConversion(self), Conversion(self)]

    def check_text(self, messages):
        for message in messages:
            allowed, _ = self._timeline.check(message)
            if allowed:
                yield message
            else:
                yield DelayMessageByProof(message)

    def on_text(self, messages):
        for message in messages:
            logger.debug("someone says '%s'", message.payload.text)
