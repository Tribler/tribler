from __future__ import annotations

import json

from ipv8.messaging.serialization import default_serializer
from ipv8.test.base import TestBase

from tribler.core.recommender.payload import Crawl, CrawlInfo, CrawlResponse


class TestContentDiscoveryPayloads(TestBase):
    """
    Tests for the various payloads of the RecommenderCommunity.
    """

    def test_crawl_info(self) -> None:
        """
        Test if CrawlInfo initializes correctly.
        """
        ci = CrawlInfo(b"\x01" * 20, b"unknown")

        self.assertEqual(0, ci.msg_id)
        self.assertEqual(b"\x01" * 20, ci.mid)
        self.assertEqual(b"unknown", ci.unknown)

    def test_crawl_info_unpack(self) -> None:
        """
        Test if CrawlInfo unpacks correctly.
        """
        packed = b'\x01' * 20 + b'unknown'
        ci, _ = default_serializer.unpack_serializable(CrawlInfo, packed)

        self.assertEqual(0, ci.msg_id)
        self.assertEqual(b"\x01" * 20, ci.mid)
        self.assertEqual(b"unknown", ci.unknown)

    def test_crawl(self) -> None:
        """
        Test if a Crawl message initializes correctly.
        """
        c = Crawl(b"\x01" * 20, json.dumps({"key": "value"}).encode(), b"unknown")

        self.assertEqual(1, c.msg_id)
        self.assertEqual(b"\x01" * 20, c.mid)
        self.assertDictEqual({"key": "value"}, c.json())
        self.assertEqual(b"unknown", c.unknown)

    def test_crawl_unpack(self) -> None:
        """
        Test if a Crawl message unpacks correctly.
        """
        packed = b'\x01' * 20 + b'\x00\x0F{"key":"value"}unknown'
        c, _ = default_serializer.unpack_serializable(Crawl, packed)

        self.assertEqual(1, c.msg_id)
        self.assertEqual(b"\x01" * 20, c.mid)
        self.assertDictEqual({"key": "value"}, c.json())
        self.assertEqual(b"unknown", c.unknown)

    def test_crawl_response(self) -> None:
        """
        Test if a CrawlResponse initializes correctly.
        """
        cr = CrawlResponse(b"\x01" * 20, json.dumps({"key": "value"}).encode(), b"unknown")

        self.assertEqual(2, cr.msg_id)
        self.assertEqual(b"\x01" * 20, cr.mid)
        self.assertDictEqual({"key": "value"}, cr.json())
        self.assertEqual(b"unknown", cr.unknown)

    def test_crawl_response_unpack(self) -> None:
        """
        Test if a CrawlResponse unpacks correctly.
        """
        packed = b'\x01' * 20 + b'\x00\x0F{"key":"value"}unknown'
        cr, _ = default_serializer.unpack_serializable(CrawlResponse, packed)

        self.assertEqual(2, cr.msg_id)
        self.assertEqual(b"\x01" * 20, cr.mid)
        self.assertDictEqual({"key": "value"}, cr.json())
        self.assertEqual(b"unknown", cr.unknown)
