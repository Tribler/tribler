import sys

from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from tribler_core.version import version_id


@vp_compile
class VersionRequest(VariablePayload):
    msg_id = 101


@vp_compile
class VersionResponse(VariablePayload):
    msg_id = 102
    format_list = ['varlenI', 'varlenI']
    names = ['version', 'platform']

    def fix_pack_version(self, value):
        return value.encode('utf-8')

    def fix_pack_platform(self, value):
        return value.encode('utf-8')

    @classmethod
    def fix_unpack_version(cls, value):
        return value.decode('utf-8')

    @classmethod
    def fix_unpack_platform(cls, value):
        return value.decode('utf-8')


class VersionCommunityMixin:
    """
    This mixin add the protocol messages to ask and receive version of Tribler and community the
    peer is currently running.

    Knowing the version of Tribler or the individual community is not critical for normal operation
    of Tribler but is useful in doing network experiments and monitoring of the network behavior
    because of a new feature/algorithm deployment.
    """

    def init_version_community(self):
        self.add_message_handler(VersionRequest, self.on_version_request)
        self.add_message_handler(VersionResponse, self.on_version_response)

    def send_version_request(self, peer):
        self.logger.info(f"Sending version request to {peer.address}")
        self.ez_send(peer, VersionRequest())

    @lazy_wrapper(VersionRequest)
    async def on_version_request(self, peer, _):
        self.logger.info(f"Received version request from {peer.address}")
        version_response = VersionResponse(version_id, sys.platform)
        self.ez_send(peer, version_response)

    @lazy_wrapper(VersionResponse)
    async def on_version_response(self, peer, payload):
        self.logger.info(f"Received version response from {peer.address}")
        self.process_version_response(peer, payload.version, payload.platform)

    def process_version_response(self, peer, version, platform):
        """
        This is the method the implementation community or the experiment will implement
        to process the version and platform information.
        """
