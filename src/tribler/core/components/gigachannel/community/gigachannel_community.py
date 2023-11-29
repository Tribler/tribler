import time
import uuid
from binascii import unhexlify
from collections import defaultdict
from dataclasses import dataclass
from random import sample

from anyio import Event, create_task_group, move_on_after
from ipv8.types import Peer
from pony.orm import db_session

from tribler.core import notifications
from tribler.core.components.ipv8.discovery_booster import DiscoveryBooster
from tribler.core.components.metadata_store.db.serialization import CHANNEL_TORRENT
from tribler.core.components.metadata_store.db.store import ObjState
from tribler.core.components.metadata_store.remote_query_community.remote_query_community import RemoteQueryCommunity
from tribler.core.components.metadata_store.utils import NoChannelSourcesException
from tribler.core.utilities.notifier import Notifier
from tribler.core.utilities.simpledefs import CHANNELS_VIEW_UUID
from tribler.core.utilities.unicode import hexlify

minimal_blob_size = 200
maximum_payload_size = 1024
max_entries = maximum_payload_size // minimal_blob_size
max_search_peers = 5

happy_eyeballs_delay = 0.3  # Send request to another peer if the answer did not arrive in 0.3s

max_address_cache_lifetime = 5.0  # seconds


@dataclass
class ChannelEntry:
    timestamp: float
    channel_version: int


class ChannelsPeersMapping:
    def __init__(self, max_peers_per_channel=10):
        self.max_peers_per_channel = max_peers_per_channel
        self._channels_dict = defaultdict(set)
        # Reverse mapping from peers to channels
        self._peers_channels = defaultdict(set)

    def add(self, peer: Peer, channel_pk: bytes, channel_id: int):
        id_tuple = (channel_pk, channel_id)
        channel_peers = self._channels_dict[id_tuple]

        channel_peers.add(peer)
        self._peers_channels[peer].add(id_tuple)

        if len(channel_peers) > self.max_peers_per_channel:
            removed_peer = min(channel_peers, key=lambda x: x.last_response)
            channel_peers.remove(removed_peer)
            # Maintain the reverse mapping
            self._peers_channels[removed_peer].remove(id_tuple)
            if not self._peers_channels[removed_peer]:
                self._peers_channels.pop(removed_peer)

    def remove_peer(self, peer):
        for id_tuple in self._peers_channels[peer]:
            self._channels_dict[id_tuple].discard(peer)
            if not self._channels_dict[id_tuple]:
                self._channels_dict.pop(id_tuple)
        self._peers_channels.pop(peer)

    def get_last_seen_peers_for_channel(self, channel_pk: bytes, channel_id: int, limit=None):
        id_tuple = (channel_pk, channel_id)
        channel_peers = self._channels_dict.get(id_tuple, [])
        return sorted(channel_peers, key=lambda x: x.last_response, reverse=True)[0:limit]


class GigaChannelCommunity(RemoteQueryCommunity):
    community_id = unhexlify('d3512d0ff816d8ac672eab29a9c1a3a32e17cb13')

    def create_introduction_response(
            self,
            lan_socket_address,
            socket_address,
            identifier,
            introduction=None,
            extra_bytes=b'',
            prefix=None,
            new_style=False,
    ):
        # ACHTUNG! We add extra_bytes here to identify the newer, 7.6+ version RemoteQuery/GigaChannel community
        # dialect, so that other 7.6+ are able to distinguish between the older and newer versions.
        return super().create_introduction_response(
            lan_socket_address,
            socket_address,
            identifier,
            introduction=introduction,
            prefix=prefix,
            new_style=new_style,
        )

    def __init__(
            self, *args, notifier: Notifier = None, **kwargs
    ):  # pylint: disable=unused-argument
        # ACHTUNG! We create a separate instance of Network for this community because it
        # walks aggressively and wants lots of peers, which can interfere with other communities
        super().__init__(*args, **kwargs)

        self.notifier = notifier

        # This set contains all the peers that we queried for subscribed channels over time.
        # It is emptied regularly. The purpose of this set is to work as a filter so we never query the same
        # peer twice. If we do, this should happen really rarely
        self.queried_peers = set()

        self.address_cache = {}
        self.address_cache_created_at = time.time()

        self.discovery_booster = DiscoveryBooster()
        self.discovery_booster.apply(self)

        self.channels_peers = ChannelsPeersMapping()

    def guess_address(self, interface):
        # Address caching allows 100x speedup of EdgeWalk.take_step() in DiscoveryBooster, from 3.0 to 0.03 seconds.
        # The overridden method can be removed after IPv8 adds internal caching of addresses.
        now = time.time()
        cache_lifetime = now - self.address_cache_created_at
        if cache_lifetime > max_address_cache_lifetime:
            self.address_cache.clear()
            self.address_cache_created_at = now

        result = self.address_cache.get(interface)
        if result is not None:
            return result

        result = super().guess_address(interface)
        self.address_cache[interface] = result
        return result

    def get_random_peers(self, sample_size=None):
        # Randomly sample sample_size peers from the complete list of our peers
        all_peers = self.get_peers()
        if sample_size is not None and sample_size < len(all_peers):
            return sample(all_peers, sample_size)
        return all_peers

    def introduction_response_callback(self, peer, dist, payload):
        # ACHTUNG! Due to Dispersy legacy, it is possible for other peer to send us an introduction
        # to ourselves (peer's public_key is not sent along with the introduction). To prevent querying
        # ourselves, we add the check for blacklist_mids here, which by default contains our own peer.
        if (
                peer.address in self.network.blacklist
                or peer.mid in self.queried_peers
                or peer.mid in self.network.blacklist_mids
        ):
            return
        if len(self.queried_peers) >= self.settings.queried_peers_limit:
            self.queried_peers.clear()
        self.queried_peers.add(peer.mid)

    async def remote_select_channel_contents(self, **kwargs):
        peers_to_query = self.get_known_subscribed_peers_for_node(kwargs["channel_pk"], kwargs["origin_id"])
        if not peers_to_query:
            raise NoChannelSourcesException()

        result = []
        async with create_task_group() as tg:
            got_at_least_one_response = Event()

            async def _send_remote_select(peer):
                request = self.send_remote_select(peer, force_eva_response=True, **kwargs)
                await request.processing_results

                # Stop execution if we already received the results from another coroutine
                if result or got_at_least_one_response.is_set():
                    return

                result.extend(request.processing_results.result())
                got_at_least_one_response.set()

            for peer in peers_to_query:
                # Before issuing another request, check if we possibly already received a response
                if got_at_least_one_response.is_set():
                    break

                # Issue a request to another peer
                tg.start_soon(_send_remote_select, peer)
                with move_on_after(happy_eyeballs_delay):
                    await got_at_least_one_response.wait()
            await got_at_least_one_response.wait()

            # Cancel the remaining requests so we don't have to wait for them to finish
            tg.cancel_scope.cancel()

        request_results = [r.md_obj.to_simple_dict() for r in result]
        return request_results

    def send_search_request(self, **kwargs):
        # Send a remote query request to multiple random peers to search for some terms
        request_uuid = uuid.uuid4()

        def notify_gui(request, processing_results):
            results = [
                r.md_obj.to_simple_dict()
                for r in processing_results
                if r.obj_state in (ObjState.NEW_OBJECT, ObjState.UPDATED_LOCAL_VERSION)
            ]
            if self.notifier:
                self.notifier[notifications.remote_query_results](
                    {"results": results, "uuid": str(request_uuid), "peer": hexlify(request.peer.mid)})

        # Try sending the request to at least some peers that we know have it
        if "channel_pk" in kwargs and "origin_id" in kwargs:
            peers_to_query = self.get_known_subscribed_peers_for_node(
                kwargs["channel_pk"], kwargs["origin_id"], self.settings.max_mapped_query_peers
            )
        else:
            peers_to_query = self.get_random_peers(self.rqc_settings.max_query_peers)

        for p in peers_to_query:
            self.send_remote_select(p, **kwargs, processing_callback=notify_gui)

        return request_uuid, peers_to_query

    def get_known_subscribed_peers_for_node(self, node_pk, node_id, limit=None):
        # Determine the toplevel parent channel
        root_id = node_id
        with db_session:
            node = self.mds.ChannelNode.get(public_key=node_pk, id_=node_id)
            if node:
                root_id = next((node.id_ for node in node.get_parent_nodes() if node.origin_id == 0), node.origin_id)

        return self.channels_peers.get_last_seen_peers_for_channel(node_pk, root_id, limit)

    def _on_query_timeout(self, request_cache):
        if not request_cache.peer_responded:
            self.channels_peers.remove_peer(request_cache.peer)
        super()._on_query_timeout(request_cache)


class GigaChannelTestnetCommunity(GigaChannelCommunity):
    """
    This community defines a testnet for the giga channels, used for testing purposes.
    """

    community_id = unhexlify('ad8cece0dfdb0e03344b59a4d31a38fe9812da9d')
