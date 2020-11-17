import json
from binascii import unhexlify
from dataclasses import dataclass

from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.requestcache import RandomNumberCache, RequestCache

from pony.orm.dbapiprovider import OperationalError

from tribler_core.modules.metadata_store.orm_bindings.channel_metadata import entries_to_chunk
from tribler_core.modules.metadata_store.store import UNKNOWN_CHANNEL, UNKNOWN_COLLECTION
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


@vp_compile
class RemoteSelectPayload(VariablePayload):
    msg_id = 201
    format_list = ['I', 'varlenH']
    names = ['id', 'json']


@vp_compile
class SelectResponsePayload(VariablePayload):
    msg_id = 202
    format_list = ['I', 'raw']
    names = ['id', 'raw_blob']


class SelectRequest(RandomNumberCache):
    def __init__(self, request_cache, prefix, request_kwargs, processing_callback=None):
        super().__init__(request_cache, prefix)
        self.request_kwargs = request_kwargs
        # The callback to call on results of processing of the response payload
        self.processing_callback = processing_callback
        # The maximum number of packets to receive from any given peer from a single request.
        # This limit is imposed as a safety precaution to prevent spam/flooding
        self.packets_limit = 10

    def on_timeout(self):
        pass


@dataclass
class RemoteQueryCommunitySettings:
    minimal_blob_size: int = 200
    maximum_payload_size: int = 1300
    max_entries: int = maximum_payload_size // minimal_blob_size
    max_query_peers: int = 5
    max_response_size: int = 100  # Max number of entries returned by SQL query
    max_channel_query_back: int = 4  # Max number of entries to query back on receiving an unknown channel

    @property
    def channel_query_back_enabled(self):
        return self.max_channel_query_back > 0


class RemoteQueryCommunity(Community):
    """
    Community for general purpose SELECT-like queries into remote Channels database
    """

    def __init__(self, my_peer, endpoint, network, metadata_store, settings=None):
        super().__init__(my_peer, endpoint, network=network)

        self.settings = settings or RemoteQueryCommunitySettings()
        self.mds = metadata_store
        self.request_cache = RequestCache()

        self.add_message_handler(RemoteSelectPayload, self.on_remote_select)
        self.add_message_handler(SelectResponsePayload, self.on_remote_select_response)

    def send_remote_select(self, peer, processing_callback=None, **kwargs):

        request = SelectRequest(self.request_cache, hexlify(peer.mid), kwargs, processing_callback)
        self.request_cache.add(request)

        self.logger.info(f"Select to {hexlify(peer.mid)} with ({kwargs})")
        self.ez_send(peer, RemoteSelectPayload(request.number, json.dumps(kwargs).encode('utf8')))

    async def process_rpc_query(self, json_bytes: bytes):
        """
        Retrieve the result of a database query from a third party, encoded as raw JSON bytes (through `dumps`).
        :raises TypeError: if the JSON contains invalid keys.
        :raises ValueError: if no JSON could be decoded.
        :raises pony.orm.dbapiprovider.OperationalError: if an illegal query was performed.
        """
        request_sanitized = sanitize_query(json.loads(json_bytes), self.settings.max_response_size)
        return await self.mds.MetadataNode.get_entries_threaded(**request_sanitized)

    @lazy_wrapper(RemoteSelectPayload)
    async def on_remote_select(self, peer, request):
        try:
            db_results = await self.process_rpc_query(request.json)
            if not db_results:
                return

            index = 0
            while index < len(db_results):
                data, index = entries_to_chunk(db_results, self.settings.maximum_payload_size, start_index=index)
                self.ez_send(peer, SelectResponsePayload(request.id, data))
        except (OperationalError, TypeError, ValueError) as error:
            self.logger.error(f"Remote select. The error occurred: {error}")

    @lazy_wrapper(SelectResponsePayload)
    async def on_remote_select_response(self, peer, response):
        """
        Match the the response that we received from the network to a query cache
        and process it by adding the corresponding entries to the MetadataStore database
        """
        self.logger.info(f"Response from {hexlify(peer.mid)}")

        request = self.request_cache.get(hexlify(peer.mid), response.id)
        if request is None:
            return

        # Check for limit on the number of packets per request
        if request.packets_limit > 1:
            request.packets_limit -= 1
        else:
            self.request_cache.pop(hexlify(peer.mid), response.id)

        processing_results = await self.mds.process_compressed_mdblob_threaded(response.raw_blob)
        self.logger.info(f"Response result: {processing_results}")

        # Query back the sender for preview contents for the new channels
        # TODO: maybe transform this into a processing_callback?
        if self.settings.channel_query_back_enabled:
            new_channels = [md for md, result in processing_results if result in (UNKNOWN_CHANNEL, UNKNOWN_COLLECTION)]
            for channel in new_channels:
                request_dict = {
                    "channel_pk": hexlify(channel.public_key),
                    "origin_id": channel.id_,
                    "first": 0,
                    "last": self.settings.max_channel_query_back,
                }
                self.send_remote_select(peer=peer, **request_dict)

        if request.processing_callback:
            request.processing_callback(request, processing_results)

    async def unload(self):
        await self.request_cache.shutdown()
        await super().unload()
