from __future__ import annotations

import random
import time
import uuid
from binascii import unhexlify
from typing import List, TYPE_CHECKING

from ipv8.lazy_community import lazy_wrapper
from pony.orm import db_session

from tribler.core import notifications
from tribler.core.components.ipv8.discovery_booster import DiscoveryBooster
from tribler.core.components.metadata_store.db.store import ObjState
from tribler.core.components.metadata_store.remote_query_community.remote_query_community import RemoteQueryCommunity
from tribler.core.components.popularity.community.payload import PopularTorrentsRequest, TorrentsHealthPayload
from tribler.core.components.popularity.community.version_community_mixin import VersionCommunityMixin
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo
from tribler.core.utilities.notifier import Notifier
from tribler.core.utilities.pony_utils import run_threaded
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import get_normally_distributed_positive_integers

if TYPE_CHECKING:
    from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker

max_address_cache_lifetime = 5.0  # seconds


class PopularityCommunity(RemoteQueryCommunity, VersionCommunityMixin):
    """
    Community for disseminating the content across the network.

    Push:
        - Every 5 seconds it gossips 10 random torrents to a random peer.
    Pull:
        - Every time it receives an introduction request, it sends a request
        to return their popular torrents.

    Gossiping is for checked torrents only.
    """
    GOSSIP_INTERVAL_FOR_RANDOM_TORRENTS = 5  # seconds
    GOSSIP_POPULAR_TORRENT_COUNT = 10
    GOSSIP_RANDOM_TORRENT_COUNT = 10

    community_id = unhexlify('9aca62f878969c437da9844cba29a134917e1648')

    def __init__(self, *args, torrent_checker=None, notifier=None, **kwargs):
        # Creating a separate instance of Network for this community to find more peers
        super().__init__(*args, **kwargs)
        self.torrent_checker: TorrentChecker = torrent_checker
        self.notifier: Notifier = notifier

        self.add_message_handler(TorrentsHealthPayload, self.on_torrents_health)
        self.add_message_handler(PopularTorrentsRequest, self.on_popular_torrents_request)

        self.logger.info('Popularity Community initialized (peer mid %s)', hexlify(self.my_peer.mid))
        self.register_task("gossip_random_torrents", self.gossip_random_torrents_health,
                           interval=PopularityCommunity.GOSSIP_INTERVAL_FOR_RANDOM_TORRENTS)

        # Init version community message handlers
        self.init_version_community()

        self.address_cache = {}
        self.address_cache_created_at = time.time()

        self.discovery_booster = DiscoveryBooster()
        self.discovery_booster.apply(self)

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

    def introduction_request_callback(self, peer, dist, payload):
        super().introduction_request_callback(peer, dist, payload)
        # Send request to peer to send popular torrents
        self.ez_send(peer, PopularTorrentsRequest())

    def get_alive_checked_torrents(self) -> List[HealthInfo]:
        if not self.torrent_checker:
            return []

        # Filter torrents that have seeders
        return [health for health in self.torrent_checker.torrents_checked.values() if
                health.seeders > 0 and health.leechers >= 0]

    def gossip_random_torrents_health(self):
        """
        Gossip random torrent health information to another peer.
        """
        if not self.get_peers() or not self.torrent_checker:
            return

        random_torrents = self.get_random_torrents()
        random_peer = random.choice(self.get_peers())

        self.ez_send(random_peer, TorrentsHealthPayload.create(random_torrents, {}))

    @lazy_wrapper(TorrentsHealthPayload)
    async def on_torrents_health(self, peer, payload):
        self.logger.debug(f"Received torrent health information for "
                          f"{len(payload.torrents_checked)} popular torrents and"
                          f" {len(payload.random_torrents)} random torrents")

        health_tuples = payload.random_torrents + payload.torrents_checked
        health_list = [HealthInfo(infohash, last_check=last_check, seeders=seeders, leechers=leechers)
                       for infohash, seeders, leechers, last_check in health_tuples]

        for infohash in await run_threaded(self.mds.db, self.process_torrents_health, health_list):
            # Get a single result per infohash to avoid duplicates
            self.send_remote_select(peer=peer, infohash=infohash, last=1)

    @db_session
    def process_torrents_health(self, health_list: List[HealthInfo]):
        infohashes_to_resolve = set()
        for health in health_list:
            added = self.mds.process_torrent_health(health)
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
        num_torrents_to_send = min(PopularityCommunity.GOSSIP_RANDOM_TORRENT_COUNT, num_torrents)
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
        num_torrents_to_send = min(PopularityCommunity.GOSSIP_RANDOM_TORRENT_COUNT, num_torrents)

        random_torrents = random.sample(checked_and_alive, num_torrents_to_send)
        return random_torrents

    def get_random_peers(self, sample_size=None):
        # Randomly sample sample_size peers from the complete list of our peers
        all_peers = self.get_peers()
        if sample_size is not None and sample_size < len(all_peers):
            return random.sample(all_peers, sample_size)
        return all_peers

    def send_search_request(self, **kwargs):
        # Send a remote query request to multiple random peers to search for some terms
        request_uuid = uuid.uuid4()

        def notify_gui(request, processing_results):
            results = [
                r.md_obj.to_simple_dict()
                for r in processing_results
                if r.obj_state == ObjState.NEW_OBJECT
            ]
            if self.notifier:
                self.notifier[notifications.remote_query_results](
                    {"results": results, "uuid": str(request_uuid), "peer": hexlify(request.peer.mid)})

        peers_to_query = self.get_random_peers(self.rqc_settings.max_query_peers)

        for p in peers_to_query:
            self.send_remote_select(p, **kwargs, processing_callback=notify_gui)

        return request_uuid, peers_to_query
