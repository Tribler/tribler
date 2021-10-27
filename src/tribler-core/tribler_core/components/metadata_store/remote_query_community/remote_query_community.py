import json
import struct
from asyncio import Future
from binascii import unhexlify

from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.requestcache import NumberCache, RandomNumberCache, RequestCache

from pony.orm.dbapiprovider import OperationalError

from tribler_core.components.ipv8.tribler_community import TriblerCommunity
from tribler_core.components.metadata_store.db.orm_bindings.channel_metadata import LZ4_EMPTY_ARCHIVE, entries_to_chunk
from tribler_core.components.metadata_store.db.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT
from tribler_core.components.metadata_store.db.store import MetadataStore
from tribler_core.components.metadata_store.remote_query_community.eva_protocol import EVAProtocolMixin
from tribler_core.components.metadata_store.remote_query_community.payload_checker import ObjState
from tribler_core.components.metadata_store.remote_query_community.settings import RemoteQueryCommunitySettings
from tribler_core.components.metadata_store.utils import RequestTimeoutException
from tribler_core.utilities.unicode import hexlify

BINARY_FIELDS = ("infohash", "channel_pk")


def sanitize_query(query_dict, cap=100):
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


class RemoteQueryCommunity(TriblerCommunity, EVAProtocolMixin):
    """
    Community for general purpose SELECT-like queries into remote Channels database
    """

    def __init__(self, my_peer, endpoint, network,
                 rqc_settings: RemoteQueryCommunitySettings = None,
                 metadata_store=None,
                 **kwargs):
        super().__init__(my_peer, endpoint, network=network, **kwargs)

        self.rqc_settings = rqc_settings
        self.mds: MetadataStore = metadata_store

        # This object stores requests for "select" queries that we sent to other hosts.
        # We keep track of peers we actually requested for data so people can't randomly push spam at us.
        # Also, this keeps track of hosts we responded to. There is a possibility that
        # those hosts will push back updates at us, so we need to allow it.
        self.request_cache = RequestCache()

        self.add_message_handler(RemoteSelectPayload, self.on_remote_select)
        self.add_message_handler(RemoteSelectPayloadEva, self.on_remote_select_eva)
        self.add_message_handler(SelectResponsePayload, self.on_remote_select_response)

        self.eva_init()
        self.eva_register_receive_callback(self.on_receive)
        self.eva_register_send_complete_callback(self.on_send_complete)
        self.eva_register_error_callback(self.on_error)

    def on_receive(self, peer, binary_info, binary_data, nonce):
        self.logger.debug(f"EVA data received: peer {hexlify(peer.mid)}, info {binary_info}")
        packet = (peer.address, binary_data)
        self.on_packet(packet)

    def on_send_complete(self, peer, binary_info, binary_data, nonce):
        self.logger.debug(f"EVA outgoing transfer complete: peer {hexlify(peer.mid)},  info {binary_info}")

    def on_error(self, peer, exception):
        self.logger.warning(f"EVA transfer error: peer {hexlify(peer.mid)}, exception: {exception}")

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

    async def process_rpc_query(self, json_bytes: bytes):
        """
        Retrieve the result of a database query from a third party, encoded as raw JSON bytes (through `dumps`).
        :raises TypeError: if the JSON contains invalid keys.
        :raises ValueError: if no JSON could be decoded.
        :raises pony.orm.dbapiprovider.OperationalError: if an illegal query was performed.
        """
        request_sanitized = sanitize_query(json.loads(json_bytes), self.rqc_settings.max_response_size)
        return await self.mds.get_entries_threaded(**request_sanitized)

    def send_db_results(self, peer, request_payload_id, db_results, force_eva_response=False):

        # Special case of empty results list - sending empty lz4 archive
        if len(db_results) == 0:
            self.ez_send(peer, SelectResponsePayload(request_payload_id, LZ4_EMPTY_ARCHIVE))
            return

        index = 0
        while index < len(db_results):
            transfer_size = (
                self.eva_protocol.binary_size_limit if force_eva_response else self.rqc_settings.maximum_payload_size
            )
            data, index = entries_to_chunk(db_results, transfer_size, start_index=index, include_health=True)
            payload = SelectResponsePayload(request_payload_id, data)
            if force_eva_response or (len(data) > self.rqc_settings.maximum_payload_size):
                self.eva_send_binary(
                    peer, struct.pack('>i', request_payload_id), self.ezr_pack(payload.msg_id, payload)
                )
            else:
                self.ez_send(peer, payload)

    @lazy_wrapper(RemoteSelectPayloadEva)
    async def on_remote_select_eva(self, peer, request_payload):
        await self._on_remote_select_basic(peer, request_payload, force_eva_response=True)

    @lazy_wrapper(RemoteSelectPayload)
    async def on_remote_select(self, peer, request_payload):
        await self._on_remote_select_basic(peer, request_payload)

    async def _on_remote_select_basic(self, peer, request_payload, force_eva_response=False):
        try:
            db_results = await self.process_rpc_query(request_payload.json)

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
        Match the the response that we received from the network to a query cache
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

        # If we know about updated versions of the received stuff, push the updates back
        if isinstance(request, SelectRequest) and self.rqc_settings.push_updates_back_enabled:
            newer_entities = [r.md_obj for r in processing_results if r.obj_state == ObjState.LOCAL_VERSION_NEWER]
            self.send_db_results(peer, response_payload.id, newer_entities)

        if self.rqc_settings.channel_query_back_enabled:
            for result in processing_results:
                # Query back the sender for preview contents for the new channels
                # The fact that the object is previously unknown is indicated by process_payload in the
                # .obj_state property of returned ProcessingResults objects.
                if result.obj_state == ObjState.NEW_OBJECT and result.md_obj.metadata_type in (
                        CHANNEL_TORRENT,
                        COLLECTION_NODE,
                ):
                    request_dict = {
                        "metadata_type": [COLLECTION_NODE, REGULAR_TORRENT],
                        "channel_pk": result.md_obj.public_key,
                        "origin_id": result.md_obj.id_,
                        "first": 0,
                        "last": self.rqc_settings.max_channel_query_back,
                    }
                    self.send_remote_select(peer=peer, **request_dict)

                # Query back for missing dependencies, e.g. thumbnail/description.
                # The fact that some dependency is missing is checked by the lower layer during
                # the query to process_payload and indicated through .missing_deps property of the
                # ProcessingResults objects returned by process_payload.
                for dep_query_dict in result.missing_deps:
                    self.send_remote_select(peer=peer, **dep_query_dict)

        if isinstance(request, SelectRequest) and request.processing_callback:
            request.processing_callback(request, processing_results)

        # Remember that at least a single packet was received was received from the queried peer.
        if isinstance(request, SelectRequest):
            request.peer_responded = True

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
        await self.request_cache.shutdown()
        await super().unload()
