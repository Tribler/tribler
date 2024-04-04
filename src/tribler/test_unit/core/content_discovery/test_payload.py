from __future__ import annotations

from ipv8.test.base import TestBase

from tribler.core.content_discovery.payload import (
    PopularTorrentsRequest,
    RemoteSelectPayload,
    SelectResponsePayload,
    TorrentInfoFormat,
    TorrentsHealthPayload,
    VersionRequest,
    VersionResponse,
)
from tribler.core.torrent_checker.dataclasses import HealthInfo, Source


class TestContentDiscoveryPayloads(TestBase):
    """
    Tests for the various payloads of the ContentDiscoveryCommunity.
    """

    @classmethod
    def setUpClass(cls: TestContentDiscoveryPayloads) -> None:
        """
        Create a test infohash.
        """
        super().setUpClass()
        cls.infohash = b"\x01" * 20

    def test_torrent_info_format(self) -> None:
        """
        Test if TorrentInfoFormat initializes correctly.
        """
        tif = TorrentInfoFormat(self.infohash, 7, 42, 1337)

        self.assertEqual(36, tif.length)
        self.assertEqual(self.infohash, tif.infohash)
        self.assertEqual(7, tif.seeders)
        self.assertEqual(42, tif.leechers)
        self.assertEqual(1337, tif.timestamp)
        self.assertEqual((self.infohash, 7, 42, 1337), tif.to_tuple())

    def test_torrents_health_payload_empty(self) -> None:
        """
        Test if TorrentsHealthPayload initializes correctly without health info.
        """
        thp = TorrentsHealthPayload.create([], [])

        self.assertEqual(1, thp.msg_id)
        self.assertEqual(0, thp.random_torrents_length)
        self.assertEqual(0, thp.torrents_checked_length)
        self.assertEqual([], thp.random_torrents)
        self.assertEqual([], thp.torrents_checked)

    def test_torrents_health_payload_one_random(self) -> None:
        """
        Test if TorrentsHealthPayload initializes correctly with one random health info.
        """
        thp = TorrentsHealthPayload.create([HealthInfo(self.infohash, 1, 2, 3, True, Source.DHT, "tracker")], [])

        self.assertEqual(1, thp.msg_id)
        self.assertEqual(1, thp.random_torrents_length)
        self.assertEqual(0, thp.torrents_checked_length)
        self.assertEqual([(self.infohash, 1, 2, 3)], thp.random_torrents)
        self.assertEqual([], thp.torrents_checked)

    def test_torrents_health_payload_one_checked(self) -> None:
        """
        Test if TorrentsHealthPayload initializes correctly with one checked health info.
        """
        thp = TorrentsHealthPayload.create([], [HealthInfo(self.infohash, 1, 2, 3, True, Source.TRACKER, "tracker")])

        self.assertEqual(1, thp.msg_id)
        self.assertEqual(0, thp.random_torrents_length)
        self.assertEqual(1, thp.torrents_checked_length)
        self.assertEqual([], thp.random_torrents)
        self.assertEqual([(self.infohash, 1, 2, 3)], thp.torrents_checked)

    def test_torrents_health_payload_many(self) -> None:
        """
        Test if TorrentsHealthPayload initializes correctly with more health info.
        """
        thp = TorrentsHealthPayload.create([
            HealthInfo(self.infohash, 1, 2, 3, True, Source.TRACKER, "tracker1"),
            HealthInfo(self.infohash, 4, 5, 6, False, Source.POPULARITY_COMMUNITY, "tracker2")
        ],
                                           [
                                               HealthInfo(self.infohash, 7, 8, 9, True, Source.DHT, "tracker3"),
                                               HealthInfo(self.infohash, 10, 11, 12, False, Source.UNKNOWN, "tracker4")
                                           ])

        self.assertEqual(1, thp.msg_id)
        self.assertEqual(2, thp.random_torrents_length)
        self.assertEqual(2, thp.torrents_checked_length)
        self.assertEqual([(self.infohash, 1, 2, 3), (self.infohash, 4, 5, 6)], thp.random_torrents)
        self.assertEqual([(self.infohash, 7, 8, 9), (self.infohash, 10, 11, 12)], thp.torrents_checked)

    def test_popular_torrents_request(self) -> None:
        """
        Test if PopularTorrentsRequest initializes correctly.
        """
        ptr = PopularTorrentsRequest()

        self.assertEqual(2, ptr.msg_id)

    def test_version_request(self) -> None:
        """
        Test if VersionRequest initializes correctly.
        """
        vr = VersionRequest()

        self.assertEqual(101, vr.msg_id)

    def test_version_response(self) -> None:
        """
        Test if VersionResponse initializes correctly.
        """
        vr = VersionResponse("foo", "bar")

        self.assertEqual(102, vr.msg_id)
        self.assertEqual("foo", vr.version)
        self.assertEqual("bar", vr.platform)

    def test_remote_select_payload(self) -> None:
        """
        Test if RemoteSelectPayload initializes correctly.
        """
        rsp = RemoteSelectPayload(42, b"{}")

        self.assertEqual(201, rsp.msg_id)
        self.assertEqual(42, rsp.id)
        self.assertEqual(b"{}", rsp.json)

    def test_select_response_payload(self) -> None:
        """
        Test if SelectResponsePayload initializes correctly.
        """
        srp = SelectResponsePayload(42, b"foo")

        self.assertEqual(202, srp.msg_id)
        self.assertEqual(42, srp.id)
        self.assertEqual(b"foo", srp.raw_blob)
