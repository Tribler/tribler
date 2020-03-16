import json
from binascii import unhexlify
from random import sample

from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.peer import Peer
from ipv8.requestcache import RandomNumberCache, RequestCache

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

    master_peer = Peer(
        unhexlify(
            "4c69624e61434c504b3a667b8dee4645475512c0780990cfaca234ad19c5dabcb065751776"
            "b75a4b4210c06e2eb4d8bbf4a775ed735eb16bbc3e44193479ad7426d7cd1067807f95b696"
        )
    )

    def __init__(self, my_peer, endpoint, network, metadata_store, settings=None, notifier=None):
        super(RemoteQueryCommunity, self).__init__(my_peer, endpoint, network)

        self.notifier = notifier
        self.max_peers = 60

        self.settings = settings or RemoteQueryCommunitySettings()

        self.mds = metadata_store

        # This set contains all the peers that we queried for subscribed channels over time.
        # It is emptied regularly. The purpose of this set is to work as a filter so we never query the same
        # peer twice. If we do, this should happen realy rarely
        # TODO: use Bloom filter here instead. We actually *want* it to be all-false-positives eventually.
        self.queried_subscribed_channels_peers = set()
        self.queried_peers_limit = 1000

        self.add_message_handler(RemoteSelectPayload, self.on_remote_select)
        self.add_message_handler(SelectResponsePayload, self.on_remote_select_response)

        self.request_cache = RequestCache()

    def get_random_peers(self, sample_size=None):
        # Randomly sample sample_size peers from the complete list of our peers
        all_peers = self.get_peers()
        if sample_size is not None and sample_size < len(all_peers):
            return sample(all_peers, sample_size)
        return all_peers

    def send_remote_select(self, peer, **kwargs):
        request = SelectRequest(self.request_cache, hexlify(peer.mid), kwargs)
        self.request_cache.add(request)
        self.ez_send(peer, RemoteSelectPayload(request.number, json.dumps(kwargs).encode('utf8')))

    def send_remote_select_to_many(self, **kwargs):
        for p in self.get_random_peers(self.settings.max_query_peers):
            self.send_remote_select(p, **kwargs)

    def send_remote_select_subscribed_channels(self, peer):
        request_dict = {"metadata_type": [CHANNEL_TORRENT], "subscribed": True}
        self.send_remote_select(peer, **request_dict)

    @lazy_wrapper(RemoteSelectPayload)
    async def on_remote_select(self, peer, request):
        request_sanitized = sanitize_query(json.loads(request.json), self.settings.max_response_size)
        db_results = await self.mds.MetadataNode.get_entries_threaded(**request_sanitized)
        if not db_results:
            return

        index = 0
        while index < len(db_results):
            data, index = entries_to_chunk(db_results, self.settings.maximum_payload_size, start_index=index)
            self.ez_send(peer, SelectResponsePayload(request.id, data))

    @lazy_wrapper(SelectResponsePayload)
    async def on_remote_select_response(self, peer, response):

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


class RemoteQueryTestnetCommunity(RemoteQueryCommunity):
    master_peer = Peer(
        unhexlify(
            "4c69624e61434c504b3a7fcf64783215dba08c1623fb14c3c86127b8591f858c56763e2281"
            "a8e121ef08caae395b2597879f7f4658b608f22df280073661f85174fd7c565cbee3e4328f"
        )
    )
