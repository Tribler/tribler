import heapq
import random
from binascii import unhexlify

from ipv8.lazy_community import lazy_wrapper

from pony.orm import db_session

from tribler.core.components.metadata_store.remote_query_community.remote_query_community import RemoteQueryCommunity
from tribler.core.components.popularity.community.payload import TorrentsHealthPayload, PopularTorrentsRequest
from tribler.core.components.popularity.community.version_community_mixin import VersionCommunityMixin
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import get_normally_distributed_positive_integers


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

    def __init__(self, *args, torrent_checker=None, **kwargs):
        # Creating a separate instance of Network for this community to find more peers
        super().__init__(*args, **kwargs)
        self.torrent_checker = torrent_checker

        self.add_message_handler(TorrentsHealthPayload, self.on_torrents_health)
        self.add_message_handler(PopularTorrentsRequest, self.on_popular_torrents_request)

        self.logger.info('Popularity Community initialized (peer mid %s)', hexlify(self.my_peer.mid))
        self.register_task("gossip_random_torrents", self.gossip_random_torrents_health,
                           interval=PopularityCommunity.GOSSIP_INTERVAL_FOR_RANDOM_TORRENTS)

        # Init version community message handlers
        self.init_version_community()

    def introduction_request_callback(self, peer, _dist, _payload):
        # Send request to peer to send popular torrents
        self.ez_send(peer, PopularTorrentsRequest())

    def get_alive_checked_torrents(self):
        if not self.torrent_checker or not self.torrent_checker.torrents_checked:
            return []

        # Filter torrents that have seeders
        alive = {(_, seeders, *rest) for (_, seeders, *rest) in self.torrent_checker.torrents_checked if seeders > 0}
        return alive

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

        torrents = payload.random_torrents + payload.torrents_checked

        for infohash in await self.mds.run_threaded(self.process_torrents_health, torrents):
            # Get a single result per infohash to avoid duplicates
            self.send_remote_select(peer=peer, infohash=infohash, last=1)

    @db_session
    def process_torrents_health(self, torrent_healths):
        infohashes_to_resolve = set()
        for infohash, seeders, leechers, last_check in torrent_healths:
            added = self.mds.process_torrent_health(infohash, seeders, leechers, last_check)
            if added:
                infohashes_to_resolve.add(infohash)
        return infohashes_to_resolve

    @lazy_wrapper(PopularTorrentsRequest)
    async def on_popular_torrents_request(self, peer, payload):
        self.logger.debug("Received popular torrents health request")
        popular_torrents = self.get_likely_popular_torrents()
        self.ez_send(peer, TorrentsHealthPayload.create({}, popular_torrents))

    def get_likely_popular_torrents(self):
        checked_and_alive = self.get_alive_checked_torrents()
        if not checked_and_alive:
            return {}

        num_torrents = len(checked_and_alive)
        num_torrents_to_send = min(PopularityCommunity.GOSSIP_RANDOM_TORRENT_COUNT, num_torrents)
        likely_popular_indices = self._get_likely_popular_indices(num_torrents_to_send, num_torrents)

        sorted_torrents = sorted(list(checked_and_alive), key=lambda t: -t[1])
        likely_popular_torrents = {sorted_torrents[i] for i in likely_popular_indices}
        return likely_popular_torrents

    def _get_likely_popular_indices(self, size, limit):
        """
        Returns a list of indices favoring the lower value numbers.

        Assuming lower indices being more popular than higher value indices, the returned list
        favors the lower indexed popular values.
        @param size: Number of indices to return
        @param limit: Max number of indices that can be returned.
        @return: List of non-repeated positive indices.
        """
        return get_normally_distributed_positive_integers(size=size, limit=limit)

    def get_random_torrents(self):
        checked_and_alive = list(self.get_alive_checked_torrents())
        if not checked_and_alive:
            return {}

        num_torrents = len(checked_and_alive)
        num_torrents_to_send = min(PopularityCommunity.GOSSIP_RANDOM_TORRENT_COUNT, num_torrents)

        random_torrents = set(random.sample(checked_and_alive, num_torrents_to_send))
        return random_torrents
