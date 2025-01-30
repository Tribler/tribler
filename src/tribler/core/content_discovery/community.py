from __future__ import annotations

import json
import random
import sys
import time
import uuid
from binascii import hexlify, unhexlify
from importlib.metadata import PackageNotFoundError, version
from itertools import count
from typing import TYPE_CHECKING, Any, Callable

from ipv8.community import Community, CommunitySettings
from ipv8.lazy_community import lazy_wrapper
from ipv8.requestcache import RequestCache
from pony.orm import OperationalError, db_session

from tribler.core.content_discovery.cache import SelectRequest
from tribler.core.content_discovery.payload import (
    PopularTorrentsRequest,
    RemoteSelectPayload,
    SelectResponsePayload,
    TorrentsHealthPayload,
    VersionRequest,
    VersionResponse,
)
from tribler.core.database.orm_bindings.torrent_metadata import LZ4_EMPTY_ARCHIVE, entries_to_chunk
from tribler.core.database.store import MetadataStore, ObjState, ProcessingResult
from tribler.core.notifier import Notification, Notifier
from tribler.core.torrent_checker.dataclasses import HealthInfo

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ipv8.types import Peer

    from tribler.core.database.orm_bindings.torrent_metadata import TorrentMetadata
    from tribler.core.torrent_checker.torrent_checker import TorrentChecker


class ContentDiscoverySettings(CommunitySettings):
    """
    The settings for the content discovery community.
    """

    random_torrent_interval: float = 5  # seconds
    random_torrent_count: int = 10
    max_query_peers: int = 20
    maximum_payload_size: int = 1300
    max_response_size: int = 100  # Max number of entries returned by SQL query

    binary_fields: Sequence[str] = ("infohash", "channel_pk")
    deprecated_parameters: Sequence[str] = ("subscribed", "attribute_ranges", "complete_channel")

    metadata_store: MetadataStore
    torrent_checker: TorrentChecker
    notifier: Notifier | None = None


class ContentDiscoveryCommunity(Community):
    """
    Community for disseminating the content across the network.
    """

    community_id = unhexlify("9aca62f878969c437da9844cba29a134917e1648")
    settings_class = ContentDiscoverySettings

    def __init__(self, settings: ContentDiscoverySettings) -> None:
        """
        Create a new overlay for content discovery.
        """
        super().__init__(settings)
        self.composition = settings

        self.add_message_handler(TorrentsHealthPayload, self.on_torrents_health)
        self.add_message_handler(PopularTorrentsRequest, self.on_popular_torrents_request)
        self.add_message_handler(VersionRequest, self.on_version_request)
        self.add_message_handler(VersionResponse, self.on_version_response)
        self.add_message_handler(RemoteSelectPayload, self.on_remote_select)
        self.add_message_handler(SelectResponsePayload, self.on_remote_select_response)

        self.add_message_handler(209, self.on_deprecated_message)
        self.deprecated_message_names[209] = "RemoteSelectPayloadEva"

        self.request_cache = RequestCache()

        self.remote_queries_in_progress = 0
        self.next_remote_query_num = count().__next__  # generator of sequential numbers, for logging & debug purposes

        self.logger.info("Content Discovery Community initialized (peer mid %s)", hexlify(self.my_peer.mid))
        self.register_task("gossip_random_torrents", self.gossip_random_torrents_health,
                           interval=self.composition.random_torrent_interval)

    async def unload(self) -> None:
        """
        Shut down the request cache.
        """
        await self.request_cache.shutdown()
        await super().unload()

    def sanitize_dict(self, parameters: dict[str, Any], decode: bool = True) -> None:
        """
        Convert the binary values in the given dictionary to (decode=True) and from (decode=False) hex format.
        """
        for field in self.composition.binary_fields:
            value = parameters.get(field)
            if value is not None:
                parameters[field] = unhexlify(value.encode()) if decode else hexlify(value.encode()).decode()

    def sanitize_query(self, query_dict: dict[str, Any], cap: int = 100) -> dict[str, Any]:
        """
        Convert the values in a query to the appropriate format and supply missing values.
        """
        sanitized_dict = dict(query_dict)

        # We impose a cap on max numbers of returned entries to prevent DDOS-like attacks
        first = sanitized_dict.get("first") or 0
        last = sanitized_dict.get("last")
        last = last if (last is not None and last <= (first + cap)) else (first + cap)
        sanitized_dict.update({"first": first, "last": last})

        # convert hex fields to binary
        self.sanitize_dict(sanitized_dict, decode=True)

        return sanitized_dict

    def convert_to_json(self, parameters: dict[str, Any]) -> str:
        """
        Sanitize and dump the given dictionary to a string using JSON.
        """
        sanitized = dict(parameters)
        # Convert metadata_type to an int list if it is a string
        if "metadata_type" in sanitized and isinstance(sanitized["metadata_type"], str):
            sanitized["metadata_type"] = [int(sanitized["metadata_type"])]

        self.sanitize_dict(sanitized, decode=False)

        if "origin_id" in parameters:
            sanitized["origin_id"] = int(parameters["origin_id"])

        return json.dumps(sanitized)

    def get_alive_checked_torrents(self) -> list[HealthInfo]:
        """
        Get torrents that we know have seeders AND leechers.
        """
        if not self.composition.torrent_checker:
            return []

        # Filter torrents that have seeders
        return [health for health in self.composition.torrent_checker.torrents_checked.values() if
                health.seeders > 0 and health.leechers >= 0]

    def gossip_random_torrents_health(self) -> None:
        """
        Gossip random torrent health information to another peer.
        """
        peers = self.get_peers()
        if not peers or not self.composition.torrent_checker:
            return

        self.ez_send(random.choice(peers), TorrentsHealthPayload.create(self.get_random_torrents(), {}))

        for p in random.sample(peers, min(len(peers), 5)):
            self.ez_send(p, PopularTorrentsRequest())

    @lazy_wrapper(TorrentsHealthPayload)
    async def on_torrents_health(self, peer: Peer, payload: TorrentsHealthPayload) -> None:
        """
        Callback for when we receive torrent health.
        """
        self.logger.debug("Received torrent health information for %d popular torrents"
                          " and %d random torrents", len(payload.torrents_checked), len(payload.random_torrents))

        health_tuples = payload.random_torrents + payload.torrents_checked
        health_list = [HealthInfo(infohash, last_check=last_check, seeders=seeders, leechers=leechers)
                       for infohash, seeders, leechers, last_check in health_tuples]

        to_resolve = self.process_torrents_health(health_list)

        for health_info in health_list:
            # Get a single result per infohash to avoid duplicates
            if health_info.infohash in to_resolve:
                infohash = hexlify(health_info.infohash).decode()
                self.send_remote_select(peer=peer, infohash=infohash, last=1)

    @db_session
    def process_torrents_health(self, health_list: list[HealthInfo]) -> set[bytes]:
        """
        Get the infohashes that we did not know about before from the given health list.
        """
        infohashes_to_resolve = set()
        for health in health_list:
            added = self.composition.metadata_store.process_torrent_health(health)
            if added:
                infohashes_to_resolve.add(health.infohash)
        return infohashes_to_resolve

    @lazy_wrapper(PopularTorrentsRequest)
    async def on_popular_torrents_request(self, peer: Peer, payload: PopularTorrentsRequest) -> None:
        """
        Callback for when we receive a request for popular torrents.
        """
        self.logger.debug("Received popular torrents health request")
        popular_torrents = self.get_random_torrents()
        self.ez_send(peer, TorrentsHealthPayload.create({}, popular_torrents))

    def get_random_torrents(self) -> list[HealthInfo]:
        """
        Get torrent health info for torrents that were alive, last we know of.
        """
        checked_and_alive = self.get_alive_checked_torrents()
        if not checked_and_alive:
            return []

        num_torrents_to_send = min(self.composition.random_torrent_count, len(checked_and_alive))
        return random.sample(checked_and_alive, num_torrents_to_send)

    def get_random_peers(self, sample_size: int | None = None) -> list[Peer]:
        """
        Randomly sample sample_size peers from the complete list of our peers.
        """
        all_peers = self.get_peers()
        return random.sample(all_peers, min(sample_size or len(all_peers), len(all_peers)))

    def send_search_request(self, **kwargs) -> tuple[uuid.UUID, list[Peer]]:
        """
        Send a remote query request to multiple random peers to search for some terms.
        """
        request_uuid = uuid.uuid4()

        def notify_gui(request: SelectRequest, processing_results: list[ProcessingResult]) -> None:
            results = [
                r.md_obj.to_simple_dict()
                for r in processing_results
                if r.obj_state == ObjState.NEW_OBJECT
            ]
            if self.composition.notifier:
                self.composition.notifier.notify(Notification.remote_query_results,
                                                 query=kwargs.get("txt_filter"),
                                                 results=results,
                                                 uuid=str(request_uuid),
                                                 peer=hexlify(request.peer.mid).decode())

        peers_to_query = self.get_random_peers(self.composition.max_query_peers)

        for p in peers_to_query:
            self.send_remote_select(p, **kwargs, processing_callback=notify_gui)

        return request_uuid, peers_to_query

    @lazy_wrapper(VersionRequest)
    async def on_version_request(self, peer: Peer, _: VersionRequest) -> None:
        """
        Callback for when our Tribler version and Operating System is requested.
        """
        try:
            v = version("tribler")
        except PackageNotFoundError:
            v = "git"
        version_response = VersionResponse(f"Tribler {v}", sys.platform)
        self.ez_send(peer, version_response)

    @lazy_wrapper(VersionResponse)
    async def on_version_response(self, peer: Peer, payload: VersionResponse) -> None:
        """
        Callback for when we receive a Tribler version and Operating System of a peer.
        """

    def send_remote_select(self, peer: Peer,
                           processing_callback: Callable[[SelectRequest, list[ProcessingResult]], None] | None = None,
                           **kwargs) -> SelectRequest:
        """
        Query a peer using an SQL statement descriptions (kwargs).
        """
        request = SelectRequest(self.request_cache, kwargs, peer, processing_callback, self._on_query_timeout)
        self.request_cache.add(request)

        self.logger.debug("Select to %s with (%s)", hexlify(peer.mid).decode(), str(kwargs))
        self.ez_send(peer, RemoteSelectPayload(request.number, self.convert_to_json(kwargs).encode()))
        return request

    def should_limit_rate_for_query(self, sanitized_parameters: dict[str, Any]) -> bool:
        """
        Don't allow too many queries with potentially heavy database load.
        """
        return "txt_filter" in sanitized_parameters

    async def process_rpc_query_rate_limited(self, sanitized_parameters: dict[str, Any]) -> list:
        """
        Process the given query and return results.
        """
        query_num = self.next_remote_query_num()
        if self.remote_queries_in_progress and self.should_limit_rate_for_query(sanitized_parameters):
            self.logger.warning("Ignore remote query %d as another one is already processing. The ignored query: %s",
                                query_num, sanitized_parameters)
            return []

        self.logger.info("Process remote query %d: %s", query_num, sanitized_parameters)
        self.remote_queries_in_progress += 1
        t = time.time()
        try:
            return await self.process_rpc_query(sanitized_parameters)
        finally:
            self.remote_queries_in_progress -= 1
            self.logger.info("Remote query %d processed in %f seconds: %s",
                             query_num, time.time() - t, sanitized_parameters)

    async def process_rpc_query(self, sanitized_parameters: dict[str, Any]) -> list:
        """
        Retrieve the result of a database query from a third party, encoded as raw JSON bytes (through `dumps`).

        :raises TypeError: if the JSON contains invalid keys.
        :raises ValueError: if no JSON could be decoded.
        :raises pony.orm.dbapiprovider.OperationalError: if an illegal query was performed.
        """
        return await self.composition.metadata_store.get_entries_threaded(**sanitized_parameters)


    def send_db_results(self, peer: Peer, request_payload_id: int, db_results: list[TorrentMetadata]) -> None:
        """
        Send the given results to the given peer.
        """
        # Special case of empty results list - sending empty lz4 archive
        if len(db_results) == 0:
            self.ez_send(peer, SelectResponsePayload(request_payload_id, LZ4_EMPTY_ARCHIVE))
            return

        index = 0
        while index < len(db_results):
            transfer_size = self.composition.maximum_payload_size
            data, index = entries_to_chunk(db_results, transfer_size, start_index=index, include_health=True)
            payload = SelectResponsePayload(request_payload_id, data)
            self.ez_send(peer, payload)

    @lazy_wrapper(RemoteSelectPayload)
    async def on_remote_select(self, peer: Peer, request_payload: RemoteSelectPayload) -> None:
        """
        Callback for when another peer queries us.
        """
        try:
            sanitized_parameters = self.parse_parameters(request_payload.json)
            # Drop selects with deprecated queries
            if any(param in sanitized_parameters for param in self.composition.deprecated_parameters):
                self.logger.warning("Remote select with deprecated parameters: %s", str(sanitized_parameters))
                self.ez_send(peer, SelectResponsePayload(request_payload.id, LZ4_EMPTY_ARCHIVE))
                return
            db_results = await self.process_rpc_query_rate_limited(sanitized_parameters)

            self.send_db_results(peer, request_payload.id, db_results)
        except (OperationalError, TypeError, ValueError) as error:
            self.logger.exception("Remote select error: %s. Request content: %s",
                                  str(error), repr(request_payload.json))

    def parse_parameters(self, json_bytes: bytes) -> dict[str, Any]:
        """
        Load a (JSON) dict from the given bytes and sanitize it to use as a database query.
        """
        return self.sanitize_query(json.loads(json_bytes), self.composition.max_response_size)

    @lazy_wrapper(SelectResponsePayload)
    async def on_remote_select_response(self, peer: Peer,
                                        response_payload: SelectResponsePayload) -> list[ProcessingResult] | None:
        """
        Match the response that we received from the network to a query cache
        and process it by adding the corresponding entries to the MetadataStore database.
        This processes both direct responses and pushback (updates) responses.
        """
        self.logger.debug("Response from %s", hexlify(peer.mid).decode())

        request: SelectRequest | None = self.request_cache.get(hexlify(peer.mid).decode(), response_payload.id)
        if request is None:
            return None

        # Check for limit on the number of packets per request
        if request.packets_limit > 1:
            request.packets_limit -= 1
        else:
            self.request_cache.pop(hexlify(peer.mid).decode(), response_payload.id)

        processing_results = await self.composition.metadata_store.process_compressed_mdblob_threaded(
            response_payload.raw_blob
        )
        self.logger.debug("Response result: %s", str(processing_results))

        if isinstance(request, SelectRequest) and request.processing_callback:
            request.processing_callback(request, processing_results)

        # Remember that at least a single packet was received from the queried peer.
        if isinstance(request, SelectRequest):
            request.peer_responded = True

        return processing_results

    def _on_query_timeout(self, request_cache: SelectRequest) -> None:
        """
        Remove a peer if it failed to respond to our select request.
        """
        if not request_cache.peer_responded:
            self.logger.debug(
                "Remote query timeout, deleting peer: %s %s %s",
                str(request_cache.peer.address),
                hexlify(request_cache.peer.mid).decode(),
                str(request_cache.request_kwargs),
            )
            self.network.remove_peer(request_cache.peer)

    def send_ping(self, peer: Peer) -> None:
        """
        Send a ping to a peer to keep it alive.
        """
        self.send_introduction_request(peer)
