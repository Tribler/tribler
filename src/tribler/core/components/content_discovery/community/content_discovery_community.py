from __future__ import annotations

import json
import random
import struct
import sys
import time
import uuid
from binascii import unhexlify
from itertools import count
from typing import Any, Dict, List, Optional, Set

from ipv8.types import Peer
from pony.orm import OperationalError, db_session

from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from ipv8.requestcache import RequestCache
from tribler.core import notifications
from tribler.core.components.content_discovery.community.cache import EvaSelectRequest, SelectRequest
from tribler.core.components.content_discovery.community.payload import (
    PopularTorrentsRequest,
    RemoteSelectPayload,
    RemoteSelectPayloadEva,
    SelectResponsePayload,
    TorrentsHealthPayload,
    VersionRequest,
    VersionResponse
)
from tribler.core.components.content_discovery.community.settings import ContentDiscoverySettings
from tribler.core.components.ipv8.eva.protocol import EVAProtocol
from tribler.core.components.ipv8.eva.result import TransferResult
from tribler.core.components.knowledge.community.knowledge_validator import is_valid_resource
from tribler.core.components.database.db.orm_bindings.torrent_metadata import LZ4_EMPTY_ARCHIVE, entries_to_chunk
from tribler.core.components.database.db.store import ObjState
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo
from tribler.core.upgrade.tags_to_knowledge.previous_dbs.knowledge_db import ResourceType
from tribler.core.utilities.pony_utils import run_threaded
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import get_normally_distributed_positive_integers
from tribler.core.version import version_id


class ContentDiscoveryCommunity(Community):
    """
    Community for disseminating the content across the network.

    Push:
        - Every 5 seconds it gossips 10 random torrents to a random peer.
    Pull:
        - Every time it receives an introduction request, it sends a request
        to return their popular torrents.

    Gossiping is for checked torrents only.
    """
    community_id = unhexlify('9aca62f878969c437da9844cba29a134917e1648')
    settings_class = ContentDiscoverySettings

    def __init__(self, settings: ContentDiscoverySettings):
        super().__init__(settings)
        self.composition = settings

        self.add_message_handler(TorrentsHealthPayload, self.on_torrents_health)
        self.add_message_handler(PopularTorrentsRequest, self.on_popular_torrents_request)
        self.add_message_handler(VersionRequest, self.on_version_request)
        self.add_message_handler(VersionResponse, self.on_version_response)
        self.add_message_handler(RemoteSelectPayload, self.on_remote_select)
        self.add_message_handler(RemoteSelectPayloadEva, self.on_remote_select_eva)
        self.add_message_handler(SelectResponsePayload, self.on_remote_select_response)

        self.request_cache = RequestCache()

        self.eva = EVAProtocol(self, self.on_receive, self.on_send_complete, self.on_error)
        self.remote_queries_in_progress = 0
        self.next_remote_query_num = count().__next__  # generator of sequential numbers, for logging & debug purposes

        self.logger.info('Content Discovery Community initialized (peer mid %s)', hexlify(self.my_peer.mid))
        self.register_task("gossip_random_torrents", self.gossip_random_torrents_health,
                           interval=self.composition.random_torrent_interval)

    async def unload(self):
        await self.eva.shutdown()
        await self.request_cache.shutdown()
        await super().unload()

    def sanitize_dict(self, parameters: dict[str, Any], decode=True) -> None:
        for field in self.composition.binary_fields:
            value = parameters.get(field)
            if value is not None:
                parameters[field] = unhexlify(value) if decode else hexlify(value)

    def sanitize_query(self, query_dict: Dict[str, Any], cap=100) -> Dict[str, Any]:
        sanitized_dict = dict(query_dict)

        # We impose a cap on max numbers of returned entries to prevent DDOS-like attacks
        first = sanitized_dict.get("first", None) or 0
        last = sanitized_dict.get("last", None)
        last = last if (last is not None and last <= (first + cap)) else (first + cap)
        sanitized_dict.update({"first": first, "last": last})

        # convert hex fields to binary
        self.sanitize_dict(sanitized_dict, decode=True)

        return sanitized_dict

    def convert_to_json(self, parameters):
        sanitized = dict(parameters)
        # Convert metadata_type to an int list if it is a string
        if "metadata_type" in sanitized and isinstance(sanitized["metadata_type"], str):
            sanitized["metadata_type"] = [int(sanitized["metadata_type"])]

        self.sanitize_dict(sanitized, decode=False)

        if "origin_id" in parameters:
            sanitized["origin_id"] = int(parameters["origin_id"])

        return json.dumps(sanitized)

    def get_alive_checked_torrents(self) -> List[HealthInfo]:
        if not self.composition.torrent_checker:
            return []

        # Filter torrents that have seeders
        return [health for health in self.composition.torrent_checker.torrents_checked.values() if
                health.seeders > 0 and health.leechers >= 0]

    def gossip_random_torrents_health(self):
        """
        Gossip random torrent health information to another peer.
        """
        if not self.get_peers() or not self.composition.torrent_checker:
            return

        self.ez_send(random.choice(self.get_peers()), TorrentsHealthPayload.create(self.get_random_torrents(), {}))

    @lazy_wrapper(TorrentsHealthPayload)
    async def on_torrents_health(self, peer, payload):
        self.logger.debug(f"Received torrent health information for "
                          f"{len(payload.torrents_checked)} popular torrents and"
                          f" {len(payload.random_torrents)} random torrents")

        health_tuples = payload.random_torrents + payload.torrents_checked
        health_list = [HealthInfo(infohash, last_check=last_check, seeders=seeders, leechers=leechers)
                       for infohash, seeders, leechers, last_check in health_tuples]

        for infohash in await run_threaded(self.composition.metadata_store.db, self.process_torrents_health,
                                           health_list):
            # Get a single result per infohash to avoid duplicates
            self.send_remote_select(peer=peer, infohash=infohash, last=1)

    @db_session
    def process_torrents_health(self, health_list: List[HealthInfo]):
        infohashes_to_resolve = set()
        for health in health_list:
            added = self.composition.metadata_store.process_torrent_health(health)
            if added:
                infohashes_to_resolve.add(health.infohash)
        return infohashes_to_resolve

    @lazy_wrapper(PopularTorrentsRequest)
    async def on_popular_torrents_request(self, peer, payload):
        self.logger.debug("Received popular torrents health request")
        popular_torrents = self.get_likely_popular_torrents()
        self.ez_send(peer, TorrentsHealthPayload.create({}, popular_torrents))

    def get_likely_popular_torrents(self) -> List[HealthInfo]:
        checked_and_alive = self.get_alive_checked_torrents()
        if not checked_and_alive:
            return []

        num_torrents = len(checked_and_alive)
        num_torrents_to_send = min(self.composition.random_torrent_count, num_torrents)
        likely_popular_indices = self._get_likely_popular_indices(num_torrents_to_send, num_torrents)

        sorted_torrents = sorted(list(checked_and_alive), key=lambda health: -health.seeders)
        likely_popular_torrents = [sorted_torrents[i] for i in likely_popular_indices]
        return likely_popular_torrents

    def _get_likely_popular_indices(self, size, limit) -> List[int]:
        """
        Returns a list of indices favoring the lower value numbers.

        Assuming lower indices being more popular than higher value indices, the returned list
        favors the lower indexed popular values.
        @param size: Number of indices to return
        @param limit: Max number of indices that can be returned.
        @return: List of non-repeated positive indices.
        """
        return get_normally_distributed_positive_integers(size=size, upper_limit=limit)

    def get_random_torrents(self) -> List[HealthInfo]:
        checked_and_alive = list(self.get_alive_checked_torrents())
        if not checked_and_alive:
            return []

        num_torrents = len(checked_and_alive)
        num_torrents_to_send = min(self.composition.random_torrent_count, num_torrents)

        random_torrents = random.sample(checked_and_alive, num_torrents_to_send)
        return random_torrents

    def get_random_peers(self, sample_size=None):
        # Randomly sample sample_size peers from the complete list of our peers
        all_peers = self.get_peers()
        return random.sample(all_peers, min(sample_size or len(all_peers), len(all_peers)))

    def send_search_request(self, **kwargs):
        # Send a remote query request to multiple random peers to search for some terms
        request_uuid = uuid.uuid4()

        def notify_gui(request, processing_results):
            results = [
                r.md_obj.to_simple_dict()
                for r in processing_results
                if r.obj_state == ObjState.NEW_OBJECT
            ]
            if self.composition.notifier:
                self.composition.notifier[notifications.remote_query_results](
                    {"results": results, "uuid": str(request_uuid), "peer": hexlify(request.peer.mid)})

        peers_to_query = self.get_random_peers(self.composition.max_query_peers)

        for p in peers_to_query:
            self.send_remote_select(p, **kwargs, processing_callback=notify_gui)

        return request_uuid, peers_to_query

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

    async def on_receive(self, result: TransferResult):
        self.logger.debug(f"EVA data received: peer {hexlify(result.peer.mid)}, info {result.info}")
        packet = (result.peer.address, result.data)
        self.on_packet(packet)

    async def on_send_complete(self, result: TransferResult):
        self.logger.debug(f"EVA outgoing transfer complete: peer {hexlify(result.peer.mid)},  info {result.info}")

    async def on_error(self, peer, exception):
        self.logger.warning(f"EVA transfer error:{exception.__class__.__name__}:{exception}, Peer: {hexlify(peer.mid)}")

    def send_remote_select(self, peer, processing_callback=None, force_eva_response=False, **kwargs):
        request_class = EvaSelectRequest if force_eva_response else SelectRequest
        request = request_class(
            self.request_cache,
            hexlify(peer.mid),
            kwargs,
            peer,
            processing_callback=processing_callback,
            timeout_callback=self._on_query_timeout,
        )
        self.request_cache.add(request)

        self.logger.debug(f"Select to {hexlify(peer.mid)} with ({kwargs})")
        args = (request.number, self.convert_to_json(kwargs).encode('utf8'))
        if force_eva_response:
            self.ez_send(peer, RemoteSelectPayloadEva(*args))
        else:
            self.ez_send(peer, RemoteSelectPayload(*args))
        return request

    def should_limit_rate_for_query(self, sanitized_parameters: Dict[str, Any]) -> bool:
        return 'txt_filter' in sanitized_parameters

    async def process_rpc_query_rate_limited(self, sanitized_parameters: Dict[str, Any]) -> List:
        query_num = self.next_remote_query_num()
        if self.remote_queries_in_progress and self.should_limit_rate_for_query(sanitized_parameters):
            self.logger.warning(f'Ignore remote query {query_num} as another one is already processing. '
                                f'The ignored query: {sanitized_parameters}')
            return []

        self.logger.info(f'Process remote query {query_num}: {sanitized_parameters}')
        self.remote_queries_in_progress += 1
        t = time.time()
        try:
            return await self.process_rpc_query(sanitized_parameters)
        finally:
            self.remote_queries_in_progress -= 1
            self.logger.info(f'Remote query {query_num} processed in {time.time() - t} seconds: {sanitized_parameters}')

    async def process_rpc_query(self, sanitized_parameters: Dict[str, Any]) -> List:
        """
        Retrieve the result of a database query from a third party, encoded as raw JSON bytes (through `dumps`).
        :raises TypeError: if the JSON contains invalid keys.
        :raises ValueError: if no JSON could be decoded.
        :raises pony.orm.dbapiprovider.OperationalError: if an illegal query was performed.
        """
        if self.composition.tribler_db:
            # tags should be extracted because `get_entries_threaded` doesn't expect them as a parameter
            tags = sanitized_parameters.pop('tags', None)

            infohash_set = await run_threaded(self.composition.tribler_db.instance, self.search_for_tags, tags)
            if infohash_set:
                sanitized_parameters['infohash_set'] = {bytes.fromhex(s) for s in infohash_set}

            # exclude_deleted should be extracted because `get_entries_threaded` doesn't expect it as a parameter
            sanitized_parameters.pop('exclude_deleted', None)

        return await self.composition.metadata_store.get_entries_threaded(**sanitized_parameters)

    @db_session
    def search_for_tags(self, tags: Optional[List[str]]) -> Optional[Set[str]]:
        if not tags or not self.composition.tribler_db:
            return None
        valid_tags = {tag for tag in tags if is_valid_resource(tag)}
        result = self.composition.tribler_db.knowledge.get_subjects_intersection(
            subjects_type=ResourceType.TORRENT,
            objects=valid_tags,
            predicate=ResourceType.TAG,
            case_sensitive=False
        )
        return result

    def send_db_results(self, peer, request_payload_id, db_results, force_eva_response=False):

        # Special case of empty results list - sending empty lz4 archive
        if len(db_results) == 0:
            self.ez_send(peer, SelectResponsePayload(request_payload_id, LZ4_EMPTY_ARCHIVE))
            return

        index = 0
        while index < len(db_results):
            transfer_size = (
                self.eva.settings.binary_size_limit if force_eva_response else self.composition.maximum_payload_size
            )
            data, index = entries_to_chunk(db_results, transfer_size, start_index=index, include_health=True)
            payload = SelectResponsePayload(request_payload_id, data)
            if force_eva_response or (len(data) > self.composition.maximum_payload_size):
                self.eva.send_binary(peer, struct.pack('>i', request_payload_id),
                                     self.ezr_pack(payload.msg_id, payload))
            else:
                self.ez_send(peer, payload)

    @lazy_wrapper(RemoteSelectPayloadEva)
    async def on_remote_select_eva(self, peer, request_payload):
        await self._on_remote_select_basic(peer, request_payload, force_eva_response=True)

    @lazy_wrapper(RemoteSelectPayload)
    async def on_remote_select(self, peer, request_payload):
        await self._on_remote_select_basic(peer, request_payload)

    def parse_parameters(self, json_bytes: bytes) -> Dict[str, Any]:
        return self.sanitize_query(json.loads(json_bytes), self.composition.max_response_size)

    async def _on_remote_select_basic(self, peer, request_payload, force_eva_response=False):
        try:
            sanitized_parameters = self.parse_parameters(request_payload.json)
            # Drop selects with deprecated queries
            if any(param in sanitized_parameters for param in self.composition.deprecated_parameters):
                self.logger.warning(f"Remote select with deprecated parameters: {sanitized_parameters}")
                self.ez_send(peer, SelectResponsePayload(request_payload.id, LZ4_EMPTY_ARCHIVE))
                return
            db_results = await self.process_rpc_query_rate_limited(sanitized_parameters)

            self.send_db_results(peer, request_payload.id, db_results, force_eva_response)
        except (OperationalError, TypeError, ValueError) as error:
            self.logger.error(f"Remote select. The error occurred: {error}")

    @lazy_wrapper(SelectResponsePayload)
    async def on_remote_select_response(self, peer, response_payload):
        """
        Match the response that we received from the network to a query cache
        and process it by adding the corresponding entries to the MetadataStore database.
        This processes both direct responses and pushback (updates) responses
        """
        self.logger.debug(f"Response from {hexlify(peer.mid)}")

        request: SelectRequest | None = self.request_cache.get(hexlify(peer.mid), response_payload.id)
        if request is None:
            return

        # Check for limit on the number of packets per request
        if request.packets_limit > 1:
            request.packets_limit -= 1
        else:
            self.request_cache.pop(hexlify(peer.mid), response_payload.id)

        processing_results = await self.composition.metadata_store.process_compressed_mdblob_threaded(
            response_payload.raw_blob
        )
        self.logger.debug(f"Response result: {processing_results}")

        if isinstance(request, EvaSelectRequest) and not request.processing_results.done():
            request.processing_results.set_result(processing_results)

        if isinstance(request, SelectRequest) and request.processing_callback:
            request.processing_callback(request, processing_results)

        # Remember that at least a single packet was received from the queried peer.
        if isinstance(request, SelectRequest):
            request.peer_responded = True

        return processing_results

    def _on_query_timeout(self, request_cache):
        if not request_cache.peer_responded:
            self.logger.debug(
                "Remote query timeout, deleting peer: %s %s %s",
                str(request_cache.peer.address),
                hexlify(request_cache.peer.mid),
                str(request_cache.request_kwargs),
            )
            self.network.remove_peer(request_cache.peer)

    def send_ping(self, peer: Peer) -> None:
        self.send_introduction_request(peer)
