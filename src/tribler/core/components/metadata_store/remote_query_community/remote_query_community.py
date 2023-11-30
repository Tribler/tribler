import json
import logging
import struct
import time
from asyncio import Future
from binascii import unhexlify
from itertools import count
from typing import Any, Dict, List, Optional, Set

from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.requestcache import NumberCache, RandomNumberCache, RequestCache
from pony.orm import db_session
from pony.orm.dbapiprovider import OperationalError

from tribler.core.components.database.db.layers.knowledge_data_access_layer import ResourceType
from tribler.core.components.ipv8.eva.protocol import EVAProtocol
from tribler.core.components.ipv8.eva.result import TransferResult
from tribler.core.components.ipv8.tribler_community import TriblerCommunity
from tribler.core.components.knowledge.community.knowledge_validator import is_valid_resource
from tribler.core.components.metadata_store.db.orm_bindings.torrent_metadata import LZ4_EMPTY_ARCHIVE, entries_to_chunk
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.metadata_store.remote_query_community.settings import RemoteQueryCommunitySettings
from tribler.core.components.metadata_store.utils import RequestTimeoutException
from tribler.core.utilities.pony_utils import run_threaded
from tribler.core.utilities.unicode import hexlify

BINARY_FIELDS = ("infohash", "channel_pk")
DEPRECATED_PARAMETERS = ['subscribed', 'attribute_ranges', 'complete_channel']


def sanitize_query(query_dict: Dict[str, Any], cap=100) -> Dict[str, Any]:
    sanitized_dict = dict(query_dict)

    # We impose a cap on max numbers of returned entries to prevent DDOS-like attacks
    first = sanitized_dict.get("first", None)
    last = sanitized_dict.get("last", None)
    first = first or 0
    last = last if (last is not None and last <= (first + cap)) else (first + cap)
    sanitized_dict.update({"first": first, "last": last})

    # convert hex fields to binary
    for field in BINARY_FIELDS:
        value = sanitized_dict.get(field)
        if value is not None:
            sanitized_dict[field] = unhexlify(value)

    return sanitized_dict


def convert_to_json(parameters):
    sanitized = dict(parameters)
    # Convert frozenset to string
    if "metadata_type" in sanitized:
        sanitized["metadata_type"] = [int(mt) for mt in sanitized["metadata_type"] if mt]

    for field in BINARY_FIELDS:
        value = parameters.get(field)
        if value is not None:
            sanitized[field] = hexlify(value)

    if "origin_id" in parameters:
        sanitized["origin_id"] = int(parameters["origin_id"])

    return json.dumps(sanitized)


@vp_compile
class RemoteSelectPayload(VariablePayload):
    msg_id = 201
    format_list = ['I', 'varlenH']
    names = ['id', 'json']


@vp_compile
class RemoteSelectPayloadEva(RemoteSelectPayload):
    msg_id = 209


@vp_compile
class SelectResponsePayload(VariablePayload):
    msg_id = 202
    format_list = ['I', 'raw']
    names = ['id', 'raw_blob']


class SelectRequest(RandomNumberCache):
    def __init__(self, request_cache, prefix, request_kwargs, peer, processing_callback=None, timeout_callback=None):
        super().__init__(request_cache, prefix)
        self.request_kwargs = request_kwargs
        # The callback to call on results of processing of the response payload
        self.processing_callback = processing_callback
        # The maximum number of packets to receive from any given peer from a single request.
        # This limit is imposed as a safety precaution to prevent spam/flooding
        self.packets_limit = 10

        self.peer = peer
        # Indicate if at least a single packet was returned by the queried peer.
        self.peer_responded = False

        self.timeout_callback = timeout_callback

    def on_timeout(self):
        if self.timeout_callback is not None:
            self.timeout_callback(self)


class EvaSelectRequest(SelectRequest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # For EVA transfer it is meaningless to send more than one message
        self.packets_limit = 1

        self.processing_results = Future()
        self.register_future(self.processing_results, on_timeout=RequestTimeoutException())


class PushbackWindow(NumberCache):
    def __init__(self, request_cache, prefix, original_request_id):
        super().__init__(request_cache, prefix, original_request_id)

        # The maximum number of packets to receive from any given peer from a single request.
        # This limit is imposed as a safety precaution to prevent spam/flooding
        self.packets_limit = 10

    def on_timeout(self):
        pass


class RemoteQueryCommunity(TriblerCommunity):
    """
    Community for general purpose SELECT-like queries into remote Channels database
    """

    def __init__(self, my_peer, endpoint, network,
                 rqc_settings: RemoteQueryCommunitySettings = None,
                 metadata_store=None,
                 tribler_db=None,
                 **kwargs):
        super().__init__(my_peer, endpoint, network=network, **kwargs)

        self.rqc_settings = rqc_settings
        self.mds: MetadataStore = metadata_store
        self.tribler_db = tribler_db
        # This object stores requests for "select" queries that we sent to other hosts.
        # We keep track of peers we actually requested for data so people can't randomly push spam at us.
        # Also, this keeps track of hosts we responded to. There is a possibility that
        # those hosts will push back updates at us, so we need to allow it.
        self.request_cache = RequestCache()

        self.add_message_handler(RemoteSelectPayload, self.on_remote_select)
        self.add_message_handler(RemoteSelectPayloadEva, self.on_remote_select_eva)
        self.add_message_handler(SelectResponsePayload, self.on_remote_select_response)

        self.eva = EVAProtocol(self, self.on_receive, self.on_send_complete, self.on_error)
        self.remote_queries_in_progress = 0
        self.next_remote_query_num = count().__next__  # generator of sequential numbers, for logging & debug purposes

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
        args = (request.number, convert_to_json(kwargs).encode('utf8'))
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
        if self.tribler_db:
            # tags should be extracted because `get_entries_threaded` doesn't expect them as a parameter
            tags = sanitized_parameters.pop('tags', None)

            infohash_set = await run_threaded(self.tribler_db.instance, self.search_for_tags, tags)
            if infohash_set:
                sanitized_parameters['infohash_set'] = {bytes.fromhex(s) for s in infohash_set}

        return await self.mds.get_entries_threaded(**sanitized_parameters)

    @db_session
    def search_for_tags(self, tags: Optional[List[str]]) -> Optional[Set[str]]:
        if not tags or not self.tribler_db:
            return None
        valid_tags = {tag for tag in tags if is_valid_resource(tag)}
        result = self.tribler_db.knowledge.get_subjects_intersection(
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
                self.eva.settings.binary_size_limit if force_eva_response else self.rqc_settings.maximum_payload_size
            )
            data, index = entries_to_chunk(db_results, transfer_size, start_index=index, include_health=True)
            payload = SelectResponsePayload(request_payload_id, data)
            if force_eva_response or (len(data) > self.rqc_settings.maximum_payload_size):
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
        parameters = json.loads(json_bytes)
        return sanitize_query(parameters, self.rqc_settings.max_response_size)

    async def _on_remote_select_basic(self, peer, request_payload, force_eva_response=False):
        try:
            sanitized_parameters = self.parse_parameters(request_payload.json)
            # Drop selects with deprecated queries
            if any(param in sanitized_parameters for param in DEPRECATED_PARAMETERS):
                self.logger.warning(f"Remote select with deprecated parameters: {sanitized_parameters}")
                self.ez_send(peer, SelectResponsePayload(request_payload.id, LZ4_EMPTY_ARCHIVE))
                return
            db_results = await self.process_rpc_query_rate_limited(sanitized_parameters)

            # When we send our response to a host, we open a window of opportunity
            # for it to push back updates
            if db_results and not self.request_cache.has(hexlify(peer.mid), request_payload.id):
                self.request_cache.add(PushbackWindow(self.request_cache, hexlify(peer.mid), request_payload.id))

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

        # ACHTUNG! the returned request cache can be any one of SelectRequest, PushbackWindow
        request = self.request_cache.get(hexlify(peer.mid), response_payload.id)
        if request is None:
            return

        # Check for limit on the number of packets per request
        if request.packets_limit > 1:
            request.packets_limit -= 1
        else:
            self.request_cache.pop(hexlify(peer.mid), response_payload.id)

        processing_results = await self.mds.process_compressed_mdblob_threaded(response_payload.raw_blob)
        self.logger.debug(f"Response result: {processing_results}")

        if isinstance(request, EvaSelectRequest) and not request.processing_results.done():
            request.processing_results.set_result(processing_results)

        if isinstance(request, SelectRequest) and request.processing_callback:
            request.processing_callback(request, processing_results)

        # Remember that at least a single packet was received was received from the queried peer.
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

    async def unload(self):
        await self.eva.shutdown()
        await self.request_cache.shutdown()
        await super().unload()
