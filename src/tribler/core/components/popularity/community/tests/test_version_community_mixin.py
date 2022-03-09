import os
import sys
from asyncio import Future

from ipv8.community import Community
from ipv8.messaging.serialization import default_serializer
from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8
from tribler_core.components.popularity.community.version_community_mixin import VersionResponse, VersionCommunityMixin
from tribler_core.version import version_id


class VersionCommunity(VersionCommunityMixin, Community):
    community_id = os.urandom(20)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_version_community()


class TestVersionCommunity(TestBase):
    NUM_NODES = 2

    def setUp(self):
        super().setUp()
        self.initialize(VersionCommunity, self.NUM_NODES)

    def create_node(self, *args, **kwargs):
        return MockIPv8("curve25519", VersionCommunity)

    def test_version_response_payload(self):
        """
        Check if the version response is correctly serialized.
        """
        version = "v7.10.0"
        platform = "linux"

        version_response = VersionResponse(version, platform)
        serialized = default_serializer.pack_serializable(version_response)
        deserialized, _ = default_serializer.unpack_serializable(VersionResponse, serialized)

        self.assertEqual(version_response.version, version)
        self.assertEqual(version_response.platform, platform)
        self.assertEqual(deserialized.version, version)
        self.assertEqual(deserialized.platform, platform)

    async def test_request_for_version(self):
        """
        Test whether version request is responded well.
        """
        await self.introduce_nodes()

        on_process_version_response_called = Future()

        def on_process_version_response(peer, version, platform):
            self.assertEqual(peer, self.peer(1))
            self.assertEqual(version, version_id)
            self.assertEqual(platform, sys.platform)
            on_process_version_response_called.set_result(True)

        self.overlay(0).process_version_response = on_process_version_response
        self.overlay(0).send_version_request(self.peer(1))

        return await on_process_version_response_called
