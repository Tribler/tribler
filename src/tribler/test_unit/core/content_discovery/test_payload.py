from __future__ import annotations

from ipv8.test.base import TestBase

from tribler.core.content_discovery.community import HEALTH_REQUEST_RANDOM
from tribler.core.content_discovery.payload import (
    HealthFormat,
    HealthPayload,
    HealthRequestPayload,
    RemoteSelectPayload,
    SelectResponsePayload,
    VersionRequest,
    VersionResponse,
)
from tribler.core.torrent_checker.healthdataclasses import HealthInfo, Source


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
        Test if HealthFormat initializes correctly.
        """
        tif = HealthFormat(self.infohash, 7, 42, 1337, "tracker")

        self.assertEqual(self.infohash, tif.infohash)
        self.assertEqual(7, tif.seeders)
        self.assertEqual(42, tif.leechers)
        self.assertEqual(1337, tif.timestamp)
        self.assertEqual("tracker", tif.tracker)

    def test_torrents_health_payload_empty(self) -> None:
        """
        Test if HealthPayload initializes correctly without health info.
        """
        thp = HealthPayload.create(HEALTH_REQUEST_RANDOM, [])

        self.assertEqual(4, thp.msg_id)
        self.assertEqual(HEALTH_REQUEST_RANDOM, thp.response_type)
        self.assertEqual(0, len(thp.torrents))

    def test_torrents_health_payload_one_random(self) -> None:
        """
        Test if HealthPayload initializes correctly with one random health info.
        """
        thp = HealthPayload.create(HEALTH_REQUEST_RANDOM,
                                   [HealthInfo(self.infohash, 1, 2, 3, True, Source.DHT, "tracker")])

        self.assertEqual(4, thp.msg_id)
        self.assertEqual(HEALTH_REQUEST_RANDOM, thp.response_type)
        self.assertEqual(1, len(thp.torrents))

        t = thp.torrents[0]
        self.assertEqual((self.infohash, 1, 2, 3, "tracker"), (t.infohash, t.seeders, t.leechers,
                                                               t.timestamp, t.tracker))

    def test_torrents_health_payload_many(self) -> None:
        """
        Test if HealthPayload initializes correctly with more health info.
        """
        thp = HealthPayload.create(HEALTH_REQUEST_RANDOM, [
            HealthInfo(self.infohash, 1, 2, 3, True, Source.TRACKER, "tracker1"),
            HealthInfo(self.infohash, 4, 5, 6, False, Source.POPULARITY_COMMUNITY, "tracker2"),
            HealthInfo(self.infohash, 7, 8, 9, True, Source.DHT, "tracker3"),
            HealthInfo(self.infohash, 10, 11, 12, False, Source.UNKNOWN, "tracker4")
        ])

        self.assertEqual(4, thp.msg_id)
        self.assertEqual(HEALTH_REQUEST_RANDOM, thp.response_type)
        self.assertEqual(4, len(thp.torrents))

        t1 = thp.torrents[0]
        t2 = thp.torrents[1]
        t3 = thp.torrents[2]
        t4 = thp.torrents[3]
        self.assertEqual((self.infohash, 1, 2, 3, "tracker1"), (t1.infohash, t1.seeders, t1.leechers,
                                                                t1.timestamp, t1.tracker))
        self.assertEqual((self.infohash, 4, 5, 6, "tracker2"), (t2.infohash, t2.seeders, t2.leechers,
                                                                t2.timestamp, t2.tracker))
        self.assertEqual((self.infohash, 7, 8, 9, "tracker3"), (t3.infohash, t3.seeders, t3.leechers,
                                                                t3.timestamp, t3.tracker))
        self.assertEqual((self.infohash, 10, 11, 12, "tracker4"), (t4.infohash, t4.seeders, t4.leechers,
                                                                   t4.timestamp, t4.tracker))

    def test_popular_torrents_request(self) -> None:
        """
        Test if HealthRequestPayload initializes correctly.
        """
        ptr = HealthRequestPayload(HEALTH_REQUEST_RANDOM)

        self.assertEqual(3, ptr.msg_id)

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
