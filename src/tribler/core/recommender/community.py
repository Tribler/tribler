from __future__ import annotations

import json
import os
from binascii import hexlify, unhexlify
from typing import TYPE_CHECKING, TypedDict, cast

from ipv8.community import Community, CommunitySettings
from ipv8.lazy_community import lazy_wrapper
from ipv8.requestcache import NumberCache, RequestCache

from tribler.core.recommender.payload import Crawl, CrawlInfo, CrawlResponse

if TYPE_CHECKING:
    from ipv8.types import Peer

    from tribler.core.recommender.manager import Manager


class ResultItem(TypedDict):
    """
    A displayed result.
    """

    infohash: str
    seeders: int
    leechers: int


def create_crawl_fragment(query_id: int, from_id: int, to_id: int = -1) -> dict:
    """
    A request to get results with id ``from_id`` to ``to_id`` for the query ``query_id``.
    """
    return {
        "version": 0,
        "type": "query_fragment",
        "query_id": query_id,
        "from_id": from_id,
        "to_id": to_id
    }


def create_crawl_fragment_response(query_id: int, from_id: int, to_id: int, infohashes: list[str], seeders: list[int],
                                   leechers: list[int]) -> dict:
    """
    A response to with results that have id ``from_id`` to ``to_id`` for the query ``query_id``.
    """
    return {
        "version": 0,
        "type": "query_fragment",
        "query_id": query_id,
        "from_id": from_id,
        "to_id": to_id,
        "infohashes": infohashes,
        "seeders": seeders,
        "leechers": leechers,
    }


def create_crawl_query_info(query_id: int) -> dict:
    """
    A request to get the number of available results for the query with the id ``query_id``.
    """
    return {
        "version": 0,
        "type": "query_info",
        "query_id": query_id
    }


def create_crawl_query_info_response(query_id: int, timestamp: int, results: int, chosen_index: int, query: str) -> dict:
    """
    A response with the number of available results for the query with the id ``query_id``.
    """
    return {
        "version": 1,
        "type": "query_info",
        "query_id": query_id,
        "results": results,
        "chosen_index": chosen_index,
        "timestamp": timestamp,
        "query": query
    }


def create_crawl_table_size_response(total_queries: int) -> dict:
    """
    A response with the number of performed queries.
    """
    return {
        "version": 0,
        "type": "table_size",
        "total_queries": total_queries
    }


class RecommenderSettings(CommunitySettings):
    """
    Settings for the RecommenderCommunity.
    """

    crawler_mid: bytes = b"Jy\xa9\x90G\x86\xec[\xde\xda\xf8(\xe6\x81l\xa2\xe0\xba\xaf\xac"
    manager: Manager
    crawl_directory: str = "crawl"


class RecommenderCommunity(Community):
    """
    A community that allows peer-to-peer learning to rank.
    """

    community_id = b"RecommenderOverlay\x00\x00"
    settings_class = RecommenderSettings

    MAX_RESULTS_IN_PACKET = 14

    def __init__(self, settings: RecommenderSettings) -> None:
        """
        Create a new recommender community.
        """
        super().__init__(settings)

        self.manager = settings.manager
        self.crawler_mid = settings.crawler_mid

        self.add_message_handler(CrawlInfo, self.on_crawl_info)
        self.add_message_handler(Crawl, self.on_crawl)
        self.add_message_handler(CrawlResponse, self.on_crawl_response)

    def json_pack(self, info: dict) -> bytes:
        """
        Convert crawl request/response dictionary to a bytes string.
        """
        return json.dumps(info, separators=(',', ':')).encode()

    def valid_crawler(self, peer: Peer, mid: bytes) -> bool:
        """
        Check if the given peer is allowed to crawl.
        """
        return peer.mid == self.crawler_mid and mid == self.my_peer.mid

    @lazy_wrapper(CrawlInfo)
    def on_crawl_info(self, peer: Peer, payload: CrawlInfo) -> None:
        """
        Process a crawl info message.
        """
        if not self.valid_crawler(peer, payload.mid):
            self.logger.warning("Unknown peer attempting to crawl us!")
            return
        self.ez_send(peer, CrawlResponse(peer.mid, self.json_pack(create_crawl_table_size_response(
            total_queries=self.manager.get_total_queries()
        )), b""))

    def process_query_fragment(self, peer: Peer, request: dict) -> None:
        """
        We received a query fragment.
        """
        query = self.manager.get_query(request["query_id"])
        unpacked = json.loads(query.json)
        results = unpacked["results"][request["from_id"]: request["to_id"]][:self.MAX_RESULTS_IN_PACKET]
        self.ez_send(peer, CrawlResponse(peer.mid, self.json_pack(create_crawl_fragment_response(
            query_id=query.rowid,
            from_id=request["from_id"],
            to_id=request["from_id"] + len(results),
            infohashes=[r["infohash"] for r in results],
            seeders=[r["seeders"] for r in results],
            leechers=[r["leechers"] for r in results]
        )), b""))

    def process_query_info(self, peer: Peer, request: dict) -> None:
        """
        We received a query info request.
        """
        query = self.manager.get_query(request["query_id"])
        unpacked = json.loads(query.json)
        self.ez_send(peer, CrawlResponse(peer.mid, self.json_pack(create_crawl_query_info_response(
            query_id=query.rowid,
            results=len(unpacked["results"]),
            chosen_index=unpacked["chosen_index"],
            timestamp=unpacked.get("timestamp", 0),
            query=unpacked["query"],
        )), b""))

    @lazy_wrapper(Crawl)
    def on_crawl(self, peer: Peer, payload: Crawl) -> None:
        """
        Process a crawl message.
        """
        if not self.valid_crawler(peer, payload.mid):
            self.logger.warning("Unknown peer attempting to crawl us!")
            return
        request = payload.json()
        request_type = request.get("type")
        if request_type == "query_fragment":
            self.process_query_fragment(peer, request)
        elif request_type == "query_info":
            self.process_query_info(peer, request)
        else:
            self.logger.warning("Crawler sent unknown request type!")

    @lazy_wrapper(CrawlResponse)
    def on_crawl_response(self, peer: Peer, payload: CrawlResponse) -> None:
        """
        Process a crawl response message.
        """
        self.logger.warning("Received a crawl response from %s, even though we are not a crawler!", str(peer))


class PartialQueryCache(NumberCache):
    """
    Cache a partially fetched query response.
    """

    def __init__(self, request_cache: RequestCache, peer: Peer, response: dict) -> None:
        """
        A cache for a query that is being retrieved.
        """
        super().__init__(request_cache, hexlify(peer.mid).decode(), response["query_id"])

        self.peer = peer
        self.query_id = response["query_id"]
        self.total_results = response["results"]
        self.results: list[ResultItem | None] = [None] * self.total_results
        self.chosen_index = response["chosen_index"]
        self.timestamp = response.get("timestamp", 0)
        self.query = response["query"]

    def get_next_range(self) -> tuple[int, int] | None:
        """
        Get the next range of value to request.
        """
        try:
            start_index = self.results.index(None)
        except ValueError:
            return None
        end_index = min(start_index + RecommenderCommunity.MAX_RESULTS_IN_PACKET, len(self.results))
        for i in range(start_index, end_index):
            if self.results[i] is not None:
                end_index = i
        return start_index, end_index

    def process_fragment(self, response: dict) -> None:
        """
        Merge a fragment into our pending results.
        """
        for i in range(len(response["infohashes"])):
            self.results[response["from_id"] + i] = ResultItem(
                infohash=response["infohashes"][i],
                seeders=response["seeders"][i],
                leechers=response["leechers"][i]
            )

    @property
    def timeout_delay(self) -> float:
        """
        Consider this peer as dropped after 2 minutes.
        """
        return 120.0


class RecommenderCommunityCrawler(RecommenderCommunity):
    """
    The crawler of the recommender community.
    """

    def __init__(self, settings: RecommenderSettings) -> None:
        """
        Create a new recommender community.
        """
        super().__init__(settings)

        assert self.my_peer.mid == settings.crawler_mid, "You are not the crawler, begone!"

        self.request_cache = RequestCache()
        self.crawl_history: dict[bytes, tuple[int, set[int]]] = {}
        self.crawl_directory = settings.crawl_directory
        """
        Peer -> (table_size, missing_queries)
        """
        self.init_crawl_history()

        self.decode_map[CrawlResponse.msg_id] = self.on_crawl_response

    def init_crawl_history(self) -> None:
        """
        Initialize the crawl history from local files.
        """
        os.makedirs(self.crawl_directory, exist_ok=True)
        crawl_dirs = os.listdir(self.crawl_directory)
        for crawl_dir in crawl_dirs:
            peer_mid = unhexlify(crawl_dir)
            peer_dir = os.path.join(self.crawl_directory, crawl_dir)
            max_id = 0
            found = set()
            for query_file in os.listdir(peer_dir):
                query_id = int(query_file.split(".")[0])
                found.add(query_id)
                max_id = max(max_id, query_id)
            if max_id == 0:  # No files
                self.crawl_history[peer_mid] = (0, set())  # Size 0, no missing ids
            else:
                missing = set(range(1, max_id + 1)) - found  # Row ids are base 1, not base 0!
                self.crawl_history[peer_mid] = (max_id, missing)

    def finalize_query(self, peer: Peer, query_id: int, query: str, chosen_index: int,
                       timestamp: int, results: list[ResultItem]) -> None:
        """
        Update self.crawl_history and write the results to a file.
        """
        query_dir = os.path.join(self.crawl_directory, hexlify(peer.mid).decode())
        os.makedirs(query_dir, exist_ok=True)
        json_dict = {
            "query": query,
            "timestamp": timestamp,
            "chosen_index": chosen_index,
            "results": results
        }
        with open(f"{query_id}.json", "w") as handle:
            json.dump(json_dict, handle)
        size, missing = self.crawl_history.get(peer.mid, (0, set()))
        missing.remove(query_id)
        self.crawl_history[peer.mid] = (size, missing)

    async def unload(self) -> None:
        """
        Destroy this overlay.
        """
        await self.request_cache.shutdown()
        await super().unload()

    def crawl_next(self, peer: Peer) -> None:
        """
        Every exchange starts with a request for crawl info (this can update over time).
        """
        self.ez_send(peer, CrawlInfo(peer.mid, b""))

    def process_table_size_response(self, peer: Peer, response: dict) -> None:
        """
        We got the table size info from a peer.
        """
        previous_size, missing = self.crawl_history.get(peer.mid, (0, set()))
        current_size = response["total_queries"]
        if current_size > previous_size:
            missing |= {i + 1 for i in range(previous_size, current_size)}  # Row ids are base 1, not base 0!
        self.crawl_history[peer.mid] = (current_size, missing)

        if missing:
            self.ez_send(peer, Crawl(peer.mid, self.json_pack(create_crawl_query_info(
                query_id=min(missing)
            )), b""))
        else:
            self.logger.info("Nothing left to crawl for %s.", str(peer))

    def process_query_info_response(self, peer: Peer, response: dict) -> None:
        """
        We got the query info from a peer.
        """
        cache = PartialQueryCache(self.request_cache, peer, response)
        next_range = cache.get_next_range()

        if next_range is None:
            self.logger.info("Query %d is empty for %s.", response["query_id"], str(peer))
            self.finalize_query(peer, cache.query_id, cache.query, cache.chosen_index, cache.timestamp, [])
        else:
            self.request_cache.add(cache)
            self.ez_send(peer, Crawl(peer.mid, self.json_pack(create_crawl_fragment(
                query_id=response["query_id"],
                from_id=next_range[0],
                to_id=next_range[1]
            )), b""))

    def process_query_fragment_response(self, peer: Peer, response: dict) -> None:
        """
        We got a query fragment from a peer.
        """
        cache = cast(PartialQueryCache, self.request_cache.pop(hexlify(peer.mid).decode(), response["query_id"]))
        cache.process_fragment(response)
        next_range = cache.get_next_range()

        if next_range is None:
            self.logger.info("Query %d has completed for %s.", response["query_id"], str(peer))
            self.finalize_query(peer, cache.query_id, cache.query, cache.chosen_index, cache.timestamp,
                                cast(list[ResultItem] , cache.results))
        else:
            self.request_cache.add(cache)  # Reset the two-minute timer
            self.ez_send(peer, Crawl(peer.mid, self.json_pack(create_crawl_fragment(
                query_id=response["query_id"],
                from_id=next_range[0],
                to_id=next_range[1]
            )), b""))

    @lazy_wrapper(CrawlResponse)
    def on_crawl_response(self, peer: Peer, payload: CrawlResponse) -> None:
        """
        Process a crawl response message.
        """
        response = payload.json()
        request_type = response.get("type")
        if request_type == "query_fragment":
            self.process_query_fragment_response(peer, response)
        elif request_type == "query_info":
            self.process_query_info_response(peer, response)
        elif request_type == "table_size":
            self.process_table_size_response(peer, response)
        else:
            self.logger.warning("Crawlee sent unknown response type!")
