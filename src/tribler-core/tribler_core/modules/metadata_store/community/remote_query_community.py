import json
from binascii import unhexlify
from random import sample

from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.peerdiscovery.network import Network
from ipv8.requestcache import RandomNumberCache, RequestCache

from pony.orm.dbapiprovider import OperationalError

from tribler_common.simpledefs import CHANNELS_VIEW_UUID, NTFY

from tribler_core.modules.metadata_store.orm_bindings.channel_metadata import entries_to_chunk
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT
from tribler_core.modules.metadata_store.store import UNKNOWN_CHANNEL
from tribler_core.utilities.unicode import hexlify


def sanitize_query(query_dict, cap=100):
    # We impose a cap on max numbers of returned entries to prevent DDOS-like attacks
    first, last = query_dict.get("first", None), query_dict.get("last", None)
    first = first or 0
    last = last if (last is not None and last <= (first + cap)) else (first + cap)
    query_dict.update({"first": first, "last": last})

    # convert hex infohash to binary
    infohash = query_dict.get('infohash', None)
    if infohash:
        query_dict['infohash'] = unhexlify(infohash)

    return query_dict


@vp_compile
class RemoteSelectPayload(VariablePayload):
    msg_id = 1
    format_list = ['I', 'varlenH']
    names = ['id', 'json']


@vp_compile
class SelectResponsePayload(VariablePayload):
    msg_id = 2
    format_list = ['I', 'raw']
    names = ['id', 'raw_blob']


class SelectRequest(RandomNumberCache):
    def __init__(self, request_cache, prefix, request_kwargs):
        super(SelectRequest, self).__init__(request_cache, prefix)
        self.request_kwargs = request_kwargs
        # The maximum number of packets to receive from any given peer from a single request.
        # This limit is imposed as a safety precaution to prevent spam/flooding
        self.packets_limit = 10

    def on_timeout(self):
        pass


class RemoteQueryCommunitySettings:
    def __init__(self):
        self.minimal_blob_size = 200
        self.maximum_payload_size = 1300
        self.max_entries = self.maximum_payload_size // self.minimal_blob_size
        self.max_query_peers = 5
        self.max_response_size = 100  # Max number of entries returned by SQL query


class RemoteQueryCommunity(Community):
    """
    Community for general purpose SELECT-like queries into remote Channels database
    """

    community_id = unhexlify('dc43e3465cbd83948f30d3d3e8336d71cce33aa7')

    def __init__(self, my_peer, endpoint, network, metadata_store, settings=None, notifier=None):
        super().__init__(my_peer, endpoint, Network())

        self.notifier = notifier

        self.settings = settings or RemoteQueryCommunitySettings()

        self.mds = metadata_store

        # This set contains all the peers that we queried for subscribed channels over time.
        # It is emptied regularly. The purpose of this set is to work as a filter so we never query the same
        # peer twice. If we do, this should happen realy rarely
        # TODO: use Bloom filter here instead. We actually *want* it to be all-false-positives eventually.
        self.queried_subscribed_channels_peers = set()
        self.queried_peers_limit = 1000

        if self.notifier:
            self.notifier.add_observer(NTFY.POPULARITY_COMMUNITY_ADD_UNKNOWN_TORRENT, self.on_pc_add_unknown_torrent)

        # this flag enable or disable https://github.com/Tribler/tribler/pull/5657
        # it can be changed in runtime
        self.enable_resolve_unknown_torrents_feature = False
        self.add_message_handler(RemoteSelectPayload, self.on_remote_select)
        self.add_message_handler(SelectResponsePayload, self.on_remote_select_response)

        self.request_cache = RequestCache()

    def on_pc_add_unknown_torrent(self, peer, infohash):
        if not self.enable_resolve_unknown_torrents_feature:
            return
        query = {'infohash': hexlify(infohash)}
        self.send_remote_select(peer, **query)

    def get_random_peers(self, sample_size=None):
        # Randomly sample sample_size peers from the complete list of our peers
        all_peers = self.get_peers()
        if sample_size is not None and sample_size < len(all_peers):
            return sample(all_peers, sample_size)
        return all_peers

    def send_remote_select(self, peer, **kwargs):
        request = SelectRequest(self.request_cache, hexlify(peer.mid), kwargs)
        self.request_cache.add(request)

        self.logger.info(f"Select to {hexlify(peer.mid)} with ({kwargs})")
        self.ez_send(peer, RemoteSelectPayload(request.number, json.dumps(kwargs).encode('utf8')))

    def send_remote_select_to_many(self, **kwargs):
        for p in self.get_random_peers(self.settings.max_query_peers):
            self.send_remote_select(p, **kwargs)

    def send_remote_select_subscribed_channels(self, peer):
        request_dict = {
            "metadata_type": [CHANNEL_TORRENT],
            "subscribed": True,
            "attribute_ranges": (("num_entries", 1, None),),
        }
        self.send_remote_select(peer, **request_dict)

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
        self.logger.info(f"Response from {hexlify(peer.mid)}")

        request = self.request_cache.get(hexlify(peer.mid), response.id)
        if request is None:
            return

        # Check for limit on the number of packets per request
        if request.packets_limit > 1:
            request.packets_limit -= 1
        else:
            self.request_cache.pop(hexlify(peer.mid), response.id)

        # We use responses for requests about subscribed channels to bump our local channels ratings
        peer_vote = peer if request.request_kwargs.get("subscribed", None) is True else None

        result = await self.mds.process_compressed_mdblob_threaded(response.raw_blob, peer_vote_for_channels=peer_vote)

        self.logger.info(f"Response result: {result}")
        # Maybe move this callback to MetadataStore side?
        if self.notifier:
            new_channels = [
                md.to_simple_dict()
                for md, result in result
                if md and md.metadata_type == CHANNEL_TORRENT and result == UNKNOWN_CHANNEL and md.origin_id == 0
            ]
            if new_channels:
                self.notifier.notify(
                    NTFY.CHANNEL_DISCOVERED, {"results": new_channels, "uuid": str(CHANNELS_VIEW_UUID)}
                )

    def introduction_response_callback(self, peer, dist, payload):
        if peer.address in self.network.blacklist or peer.mid in self.queried_subscribed_channels_peers:
            return
        if len(self.queried_subscribed_channels_peers) >= self.queried_peers_limit:
            self.queried_subscribed_channels_peers.clear()
        self.queried_subscribed_channels_peers.add(peer.mid)
        self.send_remote_select_subscribed_channels(peer)

    async def unload(self):
        await self.request_cache.shutdown()
        await super(RemoteQueryCommunity, self).unload()

        if self.notifier:
            self.notifier.remove_observer(NTFY.POPULARITY_COMMUNITY_ADD_UNKNOWN_TORRENT, self.on_pc_add_unknown_torrent)


class RemoteQueryTestnetCommunity(RemoteQueryCommunity):
    community_id = unhexlify('ad8cece0dfdb0e03344b59a4d31a38fe9812da9d')
