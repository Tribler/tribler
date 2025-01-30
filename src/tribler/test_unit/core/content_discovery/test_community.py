from __future__ import annotations

import os
import sys
from binascii import hexlify
from typing import TYPE_CHECKING, cast
from unittest import skipIf
from unittest.mock import AsyncMock, Mock, patch

from ipv8.messaging.payload import IntroductionRequestPayload, NewIntroductionRequestPayload
from ipv8.test.base import TestBase
from ipv8.test.mocking.endpoint import MockEndpointListener

import tribler
from tribler.core.content_discovery.community import ContentDiscoveryCommunity, ContentDiscoverySettings
from tribler.core.content_discovery.payload import (
    PopularTorrentsRequest,
    SelectResponsePayload,
    TorrentsHealthPayload,
    VersionRequest,
    VersionResponse,
)
from tribler.core.database.orm_bindings.torrent_metadata import LZ4_EMPTY_ARCHIVE
from tribler.core.database.serialization import REGULAR_TORRENT
from tribler.core.notifier import Notification, Notifier
from tribler.core.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.torrent_checker.torrentchecker_session import HealthInfo

if TYPE_CHECKING:
    from ipv8.community import CommunitySettings
    from ipv8.test.mocking.ipv8 import MockIPv8


class MockTorrentChecker(TorrentChecker):
    """
    A mocked TorrentChecker.
    """

    infohash = b"\x01" * 20

    def __init__(self) -> None:
        """
        Create a new mocked TorrentChecker.
        """
        super().__init__(None, None, None, None, None)
        self._torrents_checked = {self.infohash: HealthInfo(self.infohash, 7, 42, 1337)}

    def set_torrents_checked(self, value: dict[bytes, HealthInfo]) -> None:
        """
        Overwrite the default test value for torrents_checked.
        """
        self._torrents_checked = value


class TestContentDiscoveryCommunity(TestBase[ContentDiscoveryCommunity]):
    """
    Tests for the ContentDiscoveryCommunity.
    """

    def setUp(self) -> None:
        """
        Create a new pair of ContentDiscoveryCommunities.
        """
        super().setUp()
        self.initialize(ContentDiscoveryCommunity, 2)

    def create_node(self, settings: CommunitySettings | None = None, create_dht: bool = False,
                    enable_statistics: bool = False) -> MockIPv8:
        """
        Create an inert version of the ContentDiscoveryCommunity.
        """
        overwrite_settings = ContentDiscoverySettings(
            torrent_checker=MockTorrentChecker(),
            metadata_store=Mock(get_entries_threaded=AsyncMock(), process_compressed_mdblob_threaded=AsyncMock())
        )
        out = super().create_node(overwrite_settings, create_dht, enable_statistics)
        out.overlay.cancel_all_pending_tasks()
        return out

    def torrent_checker(self, i: int) -> MockTorrentChecker:
        """
        Get the torrent checker of node i.
        """
        return cast(MockTorrentChecker, self.overlay(i).composition.torrent_checker)

    async def test_torrents_health_gossip(self) -> None:
        """
        Test whether torrent health information is periodically gossiped around.
        """
        with self.assertReceivedBy(1, [TorrentsHealthPayload], message_filter=[TorrentsHealthPayload]):
            self.overlay(0).gossip_random_torrents_health()
            await self.deliver_messages()

    async def test_torrents_health_gossip_no_checker(self) -> None:
        """
        Test whether no torrent health information is spread without a torrent checker.
        """
        self.overlay(0).composition.torrent_checker = None

        with self.assertReceivedBy(1, []):
            self.overlay(0).gossip_random_torrents_health()
            await self.deliver_messages()

    async def test_torrents_health_gossip_no_live(self) -> None:
        """
        Test whether torrent health information is spread when no live torrents are known.
        """
        with self.assertReceivedBy(1, [TorrentsHealthPayload],
                                   message_filter=[TorrentsHealthPayload]) as received:
            self.overlay(0).gossip_random_torrents_health()
            await self.deliver_messages()
        message, = received

        self.assertEqual(1, message.random_torrents_length)
        self.assertEqual(0, message.torrents_checked_length)

    def test_get_alive_torrents(self) -> None:
        """
        Test if get_alive_checked_torrents returns a known alive torrent.
        """
        self.assertEqual([HealthInfo(MockTorrentChecker.infohash, 7, 42, 1337)],
                         self.overlay(0).get_alive_checked_torrents())

    def test_get_alive_torrents_no_seeders(self) -> None:
        """
        Test if get_alive_checked_torrents does not return torrents without seeders.
        """
        self.torrent_checker(0).set_torrents_checked({
            MockTorrentChecker.infohash: HealthInfo(MockTorrentChecker.infohash, 0, 42, 1337)
        })

        self.assertEqual([], self.overlay(0).get_alive_checked_torrents())

    def test_get_alive_torrents_no_leechers(self) -> None:
        """
        Test if get_alive_checked_torrents does return torrents without leechers.
        """
        health_info = HealthInfo(MockTorrentChecker.infohash, 7, 0, 1337)
        self.torrent_checker(0).set_torrents_checked({MockTorrentChecker.infohash: health_info})

        self.assertEqual([health_info], self.overlay(0).get_alive_checked_torrents())

    def test_get_alive_torrents_no_checker(self) -> None:
        """
        Test if get_alive_checked_torrents returns nothing without a torrent checker.
        """
        self.overlay(0).composition.torrent_checker = None

        self.assertEqual([], self.overlay(0).get_alive_checked_torrents())

    async def test_popularity_search(self) -> None:
        """
        Test searching several nodes for metadata entries based on title text.
        """
        notifications = {}
        self.overlay(0).composition.notifier = Notifier()
        self.overlay(0).composition.notifier.add(Notification.remote_query_results, notifications.update)

        uuid, peers = self.overlay(0).send_search_request(txt_filter="ubuntu*")
        await self.deliver_messages()

        self.assertEqual(str(uuid), notifications["uuid"])
        self.assertEqual([], notifications["results"])
        self.assertEqual(hexlify(peers[0].mid).decode(), notifications["peer"])

    async def test_popularity_search_deprecated(self) -> None:
        """
        Test searching several nodes for metadata entries with a deprecated parameter.
        """
        notifications = {}
        self.overlay(0).composition.notifier = Notifier()
        self.overlay(0).composition.notifier.add(Notification.remote_query_results, notifications.update)

        uuid, peers = self.overlay(0).send_search_request(txt_filter="ubuntu*", hide_xxx="1",
                                                          metadata_type=REGULAR_TORRENT, exclude_deleted="1")
        await self.deliver_messages()

        self.assertEqual(str(uuid), notifications["uuid"])
        self.assertEqual([], notifications["results"])
        self.assertEqual(hexlify(peers[0].mid).decode(), notifications["peer"])

    async def test_popularity_search_unparsed_metadata_type(self) -> None:
        """
        Test searching several nodes for metadata entries with the metadata type passed as a string.
        """
        notifications = {}
        self.overlay(0).composition.notifier = Notifier()
        self.overlay(0).composition.notifier.add(Notification.remote_query_results, notifications.update)

        uuid, peers = self.overlay(0).send_search_request(txt_filter="ubuntu*", hide_xxx="1",
                                                          metadata_type=str(REGULAR_TORRENT), exclude_deleted="1")
        await self.deliver_messages()

        self.assertEqual(str(uuid), notifications["uuid"])
        self.assertEqual([], notifications["results"])
        self.assertEqual(hexlify(peers[0].mid).decode(), notifications["peer"])

    async def test_request_for_version(self) -> None:
        """
        Test if a version request is responded to.
        """
        with self.assertReceivedBy(0, [VersionResponse]) as received:
            self.overlay(0).ez_send(self.peer(1), VersionRequest())
            await self.deliver_messages()
        message, = received

        self.assertEqual(sys.platform, message.platform)
        self.assertEqual("Tribler git", message.version)

    async def test_request_for_version_build(self) -> None:
        """
        Test if a build version request is responded to.
        """
        with patch.dict(tribler.core.content_discovery.community.__dict__, {"version": lambda _: "1.2.3"}), \
                self.assertReceivedBy(0, [VersionResponse]) as received:
            self.overlay(0).ez_send(self.peer(1), VersionRequest())
            await self.deliver_messages()
        message, = received

        self.assertEqual(sys.platform, message.platform)
        self.assertEqual("Tribler 1.2.3", message.version)

    async def test_process_rpc_query(self) -> None:
        """
        Test if process_rpc_query searches the TriblerDB and MetadataStore.
        """
        async_mock = AsyncMock()
        self.overlay(0).composition.tribler_db = Mock(instance=Mock(return_value={"01" * 20}))
        self.overlay(0).composition.metadata_store.get_entries_threaded = async_mock

        await self.overlay(0).process_rpc_query({'first': 0, 'infohash_set': None, 'last': 100})

        self.assertEqual(0, async_mock.call_args.kwargs["first"])
        self.assertEqual(100, async_mock.call_args.kwargs["last"])

    async def test_remote_select(self) -> None:
        """
        Test querying metadata entries from a remote machine.
        """
        kwargs_dict = {"txt_filter": "ubuntu*", "metadata_type": REGULAR_TORRENT}
        mock_callback = Mock()
        self.overlay(1).send_remote_select(self.peer(0), **kwargs_dict, processing_callback=mock_callback)

        with self.assertReceivedBy(1, [SelectResponsePayload]):
            await self.deliver_messages()

        select_request = mock_callback.call_args[0][0]
        self.assertTrue(select_request.peer_responded)

    async def test_remote_select_deprecated(self) -> None:
        """
        Test deprecated search keys receiving an empty archive response.
        """
        with self.assertReceivedBy(0, [SelectResponsePayload]) as responses:
            self.overlay(0).send_remote_select(self.peer(1), subscribed=1)
            await self.deliver_messages()
        response, = responses

        assert response.raw_blob == LZ4_EMPTY_ARCHIVE

    def test_sanitize_query(self) -> None:
        """
        Test if queries are properly sanitized.
        """
        req_response_list = [
            ({"first": None, "last": None}, {"first": 0, "last": 100}),
            ({"first": 123, "last": None}, {"first": 123, "last": 223}),
            ({"first": None, "last": 1000}, {"first": 0, "last": 100}),
            ({"first": 100, "last": None}, {"first": 100, "last": 200}),
            ({"first": 123}, {"first": 123, "last": 223}),
            ({"last": 123}, {"first": 0, "last": 100}),
            ({}, {"first": 0, "last": 100}),
        ]
        for req, resp in req_response_list:
            self.assertEqual(resp, self.overlay(0).sanitize_query(req))

    def test_sanitize_query_binary_fields(self) -> None:
        """
        Test if binary fields are properly sanitized.
        """
        for field in ("infohash", "channel_pk"):
            field_in_b = b'0' * 20
            field_in_hex = hexlify(field_in_b).decode()
            self.assertEqual(field_in_b, self.overlay(0).sanitize_query({field: field_in_hex})[field])

    async def test_process_rpc_query_match_none(self) -> None:
        """
        Check if a correct query with no match in our database returns no result.
        """
        results = await self.overlay(0).process_rpc_query({})

        self.assertEqual(0, len(results))

    @skipIf(int(os.environ.get("TEST_IPV8_WITH_IPV6", "0")), "IPv4-only test")
    async def test_ping(self) -> None:
        """
        Test if the keep-alive message works.

        Note: assertReceivedBy is illegal here because a ping is a GlobalTimeDistribution + IntroductionRequest!
        """
        ep_listener = MockEndpointListener(self.endpoint(1))

        self.overlay(0).send_ping(self.peer(1))
        await self.deliver_messages()

        self.assertEqual(1, len(ep_listener.received_packets))
        self.assertEqual(IntroductionRequestPayload.msg_id, ep_listener.received_packets[0][1][22])

    @skipIf(not int(os.environ.get("TEST_IPV8_WITH_IPV6", "0")), "IPv6-only test")
    async def test_ping_ipv6(self) -> None:
        """
        Test if the keep-alive message works when dealing with IPv6 addresses.

        Note: assertReceivedBy is illegal here because a ping is a GlobalTimeDistribution + NewIntroductionRequest!
        """
        ep_listener = MockEndpointListener(self.endpoint(1))

        self.overlay(0).send_ping(self.peer(1))
        await self.deliver_messages()

        self.assertEqual(1, len(ep_listener.received_packets))
        self.assertEqual(NewIntroductionRequestPayload.msg_id, ep_listener.received_packets[0][1][22])

    async def test_deprecated_popular_torrents_request_no_live(self) -> None:
        """
        The new protocol no longer uses PopularTorrentsRequest but still supports it.
        """
        with self.assertReceivedBy(0, [TorrentsHealthPayload],
                                   message_filter=[TorrentsHealthPayload]) as received:
            self.overlay(0).ez_send(self.peer(1), PopularTorrentsRequest())
            await self.deliver_messages()
        message, = received

        self.assertEqual(0, message.random_torrents_length)
        self.assertEqual(1, message.torrents_checked_length)
        self.assertEqual([], message.random_torrents)
        self.assertEqual((b"\x01" * 20, 7, 42, 1337), message.torrents_checked[0])

    async def test_deprecated_popular_torrents_request_live(self) -> None:
        """
        The new protocol no longer uses PopularTorrentsRequest but still supports it.
        """
        with self.assertReceivedBy(0, [TorrentsHealthPayload], message_filter=[TorrentsHealthPayload]) as received:
            self.overlay(0).ez_send(self.peer(1), PopularTorrentsRequest())
            await self.deliver_messages()
        message, = received

        self.assertEqual(0, message.random_torrents_length)
        self.assertEqual(1, message.torrents_checked_length)
        self.assertEqual([], message.random_torrents)
        self.assertEqual((b'\x01'*20, 7, 42, message.torrents_checked[0][3]), message.torrents_checked[0])
