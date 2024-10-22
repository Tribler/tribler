from __future__ import annotations

import dataclasses
import json
from typing import cast
from unittest.mock import patch

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8

from tribler.core.recommender.community import (
    RecommenderCommunity,
    RecommenderCommunityCrawler,
    RecommenderSettings,
    ResultItem,
)
from tribler.core.recommender.payload import CrawlResponse


class StubRecommenderCommunityCrawler(RecommenderCommunityCrawler):
    """
    Stub class that avoids file I/O.
    """

    def init_crawl_history(self) -> None:
        """
        Don't load from disk.
        """

    def finalize_query(self, peer: Peer, query_id: int, query: str, chosen_index: int,
                       timestamp: int,results: list[ResultItem]) -> None:
        """
        Don't write to disk.
        """
        size, missing = self.crawl_history.get(peer.mid, (0, set()))
        missing.remove(query_id)
        self.crawl_history[peer.mid] = (size, missing)


class MockManager:
    """
    Using a memory-based mock is even faster than ``Manager(":memory:")``, tested in ``test_manager``.
    """

    @dataclasses.dataclass
    class MockQuery:
        """
        A database-equivalent for a Query.
        """

        rowid: int
        version: int
        json: str

    def __init__(self) -> None:
        """
        Don't do any database stuff.
        """
        self.queries = []

    def get_total_queries(self) -> int:
        """
        Get the total number of queries that we know of.
        """
        return len(self.queries)

    def get_query(self, query_id: int) -> MockQuery:
        """
        Get the Query with a given id.
        """
        return self.queries[query_id - 1]

    def add_query(self, json_data: str) -> None:
        """
        Inject data into our database.
        """
        self.queries += [self.MockQuery(len(self.queries) + 1, 0, json_data)]


class TestRecommenderCommunity(TestBase[RecommenderCommunity]):
    """
    Tests for the recommender community.
    """

    def setUp(self) -> None:
        """
        Create a new memory-based manager.
        """
        self.node_id = 0
        self.crawler_peer = Peer(default_eccrypto.generate_key("curve25519"))
        self.initialize(RecommenderCommunity, 2)

    def create_node(self, settings: RecommenderSettings | None = None, create_dht: bool = False,
                    enable_statistics: bool = False) -> MockIPv8:
        """
        Create a new memory-based community.
        """
        community_class = RecommenderCommunity if self.node_id == 0 else StubRecommenderCommunityCrawler
        self.node_id += 1
        settings = RecommenderSettings(manager=MockManager(), crawler_mid=self.crawler_peer.mid)
        return MockIPv8("low" if self.node_id==1 else self.crawler_peer, community_class, settings, create_dht,
                        enable_statistics)

    def crawler_overlay(self) -> StubRecommenderCommunityCrawler:
        """
        Get the overlay of the crawler (peer id 1).
        """
        return cast(StubRecommenderCommunityCrawler, self.overlay(1))

    async def test_crawl_table_empty(self) -> None:
        """
        Test if an empty table can be crawled.
        """
        with self.assertReceivedBy(1, [CrawlResponse]) as messages:
            self.crawler_overlay().crawl_next(self.peer(0))
            await self.deliver_messages()

        response = json.loads(messages[0].data)
        self.assertEqual(0, response["version"])
        self.assertEqual("table_size", response["type"])
        self.assertEqual(0, response["total_queries"])

    async def test_crawl_query_v0(self) -> None:
        """
        Test if a single query can be crawled.
        """
        self.overlay(0).manager.add_query('{"query": "test query", "chosen_index": 2, "results": ['
                                          f'{{"infohash": "{"01" * 20}", "seeders": 1, "leechers": 2}}, '
                                          f'{{"infohash": "{"02" * 20}", "seeders": 3, "leechers": 4}}, '
                                          f'{{"infohash": "{"03" * 20}", "seeders": 5, "leechers": 6}}'
                                          ']}')

        with self.assertReceivedBy(1, [CrawlResponse, CrawlResponse, CrawlResponse]) as messages:
            self.crawler_overlay().crawl_next(self.peer(0))
            await self.deliver_messages()

        response1 = json.loads(messages[0].data)
        response2 = json.loads(messages[1].data)
        response3 = json.loads(messages[2].data)
        self.assertEqual("table_size", response1["type"])
        self.assertEqual("query_info", response2["type"])
        self.assertEqual(1, response2["query_id"])
        self.assertEqual("query_fragment", response3["type"])
        self.assertEqual(1, response3["query_id"])
        self.assertListEqual(["01" * 20, "02" * 20, "03" * 20], response3["infohashes"])
        self.assertListEqual([1, 3, 5], response3["seeders"])
        self.assertListEqual([2, 4, 6], response3["leechers"])
        self.assertIn(self.mid(0), self.crawler_overlay().crawl_history)
        self.assertEqual(1, self.crawler_overlay().crawl_history[self.mid(0)][0], "The known size should be 1")
        self.assertSetEqual(set(), self.crawler_overlay().crawl_history[self.mid(0)][1], "There should be no missing")

    async def test_crawl_query_v1(self) -> None:
        """
        Test if a single query can be crawled.
        """
        self.overlay(0).manager.add_query('{"query": "test query", "timestamp": 1234567890, "chosen_index": 2, "results": ['
                                          f'{{"infohash": "{"01" * 20}", "seeders": 1, "leechers": 2}}, '
                                          f'{{"infohash": "{"02" * 20}", "seeders": 3, "leechers": 4}}, '
                                          f'{{"infohash": "{"03" * 20}", "seeders": 5, "leechers": 6}}'
                                          ']}')

        with self.assertReceivedBy(1, [CrawlResponse, CrawlResponse, CrawlResponse]) as messages:
            self.crawler_overlay().crawl_next(self.peer(0))
            await self.deliver_messages()

        response1 = json.loads(messages[0].data)
        response2 = json.loads(messages[1].data)
        response3 = json.loads(messages[2].data)
        self.assertEqual("table_size", response1["type"])
        self.assertEqual("query_info", response2["type"])
        self.assertEqual(1, response2["query_id"])
        self.assertEqual("query_fragment", response3["type"])
        self.assertEqual(1, response3["query_id"])
        self.assertListEqual(["01" * 20, "02" * 20, "03" * 20], response3["infohashes"])
        self.assertListEqual([1, 3, 5], response3["seeders"])
        self.assertListEqual([2, 4, 6], response3["leechers"])
        self.assertIn(self.mid(0), self.crawler_overlay().crawl_history)
        self.assertEqual(1, self.crawler_overlay().crawl_history[self.mid(0)][0], "The known size should be 1")
        self.assertSetEqual(set(), self.crawler_overlay().crawl_history[self.mid(0)][1], "There should be no missing")

    async def test_crawl_query_done(self) -> None:
        """
        Test if a crawl after completion leads to no further requests for data.
        """
        self.overlay(0).manager.add_query("{}")
        self.crawler_overlay().crawl_history[self.mid(0)] = (1, set())

        with self.assertReceivedBy(1, [CrawlResponse]) as messages:
            self.crawler_overlay().crawl_next(self.peer(0))
            await self.deliver_messages()

        response = json.loads(messages[0].data)
        self.assertEqual("table_size", response["type"])
        self.assertEqual(1, response["total_queries"])

    async def test_crawl_query_fragmented(self) -> None:
        """
        Test if a fragmented crawl completes.
        """
        self.overlay(0).manager.add_query('{"query": "test query", "chosen_index": 2, "results": ['
                                          f'{{"infohash": "{"01" * 20}", "seeders": 1, "leechers": 2}}, '
                                          f'{{"infohash": "{"02" * 20}", "seeders": 3, "leechers": 4}}, '
                                          f'{{"infohash": "{"03" * 20}", "seeders": 5, "leechers": 6}}'
                                          ']}')

        with patch.object(RecommenderCommunity, "MAX_RESULTS_IN_PACKET", 1), \
                self.assertReceivedBy(1, [CrawlResponse] * 5) as messages:
            self.crawler_overlay().crawl_next(self.peer(0))
            await self.deliver_messages()

        frag1_response = json.loads(messages[2].data)
        frag2_response = json.loads(messages[3].data)
        frag3_response = json.loads(messages[4].data)
        self.assertEqual("table_size", json.loads(messages[0].data)["type"])
        self.assertEqual("query_info", json.loads(messages[1].data)["type"])
        self.assertEqual("query_fragment", frag1_response["type"])
        self.assertListEqual(["01" * 20], frag1_response["infohashes"])
        self.assertEqual("query_fragment", frag2_response["type"])
        self.assertListEqual(["02" * 20], frag2_response["infohashes"])
        self.assertEqual("query_fragment", frag3_response["type"])
        self.assertListEqual(["03" * 20], frag3_response["infohashes"])
