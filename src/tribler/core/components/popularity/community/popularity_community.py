from __future__ import annotations

import random
from binascii import unhexlify
from typing import List, TYPE_CHECKING

from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.interfaces.udp.endpoint import UDPv4Address, UDPv4LANAddress
from ipv8.messaging.serialization import PackError
from pony.orm import db_session

from tribler.core.components.metadata_store.remote_query_community.remote_query_community import RemoteQueryCommunity
from tribler.core.components.popularity.community.payload import PopularTorrentsRequest, TorrentsHealthPayload
from tribler.core.components.popularity.community.version_community_mixin import VersionCommunityMixin
from tribler.core.components.popularity.rendezvous.db.database import RendezvousDatabase
from tribler.core.components.popularity.rendezvous.rendezvous import RendezvousRequestPayload, \
    RendezvousResponsePayload, RawRendezvousResponsePayload, \
    RendezvousChallenge, RendezvousSignature
from tribler.core.components.popularity.rendezvous.rendezvous_cache import RendezvousCache, EMPTY_PEER_CHALLENGE
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo
from tribler.core.utilities.pony_utils import run_threaded
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import get_normally_distributed_positive_integers

if TYPE_CHECKING:
    from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker


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

    PING_INTERVAL_RENDEZVOUS = 60  # seconds
    DB_NAME = 'rendezvous.db'

    community_id = unhexlify('9aca62f878969c437da9844cba29a134917e1649')

    def __init__(self, *args, torrent_checker=None, rendezvous_db=None, **kwargs):
        # Creating a separate instance of Network for this community to find more peers
        super().__init__(*args, **kwargs)

        self.rdb: RendezvousDatabase = rendezvous_db
        self.torrent_checker: TorrentChecker = torrent_checker

        self.add_message_handler(TorrentsHealthPayload, self.on_torrents_health)
        self.add_message_handler(PopularTorrentsRequest, self.on_popular_torrents_request)

        self.add_message_handler(RendezvousRequestPayload, self.on_rendezvous_request)
        self.add_message_handler(RendezvousResponsePayload, self.on_rendezvous_response)

        self.logger.info('Popularity Community initialized (peer mid %s)', hexlify(self.my_peer.mid))
        self.register_task("gossip_random_torrents", self.gossip_random_torrents_health,
                           interval=PopularityCommunity.GOSSIP_INTERVAL_FOR_RANDOM_TORRENTS)
        self.register_task("ping_rendezvous", self.ping_rendezvous,
                           interval=PopularityCommunity.PING_INTERVAL_RENDEZVOUS)

        # Init version community message handlers
        self.init_version_community()
        self.rendezvous_cache = RendezvousCache()

    def send_introduction_request(self, peer):
        rendezvous_request = self._create_rendezvous_request()
        extra_payload = self.serializer.pack_serializable(rendezvous_request)
        self.logger.debug("Piggy-backing Rendezvous to %s:%d", peer.address[0], peer.address[1])
        packet = self.create_introduction_request(peer.address, extra_bytes=extra_payload,
                                                  new_style=peer.new_style_intro)
        self.endpoint.send(peer.address, packet)
        self.rendezvous_cache.add_peer(peer, rendezvous_request.challenge.nonce)

    # We override this method to add the rendezvous certificate to the introduction request
    def on_introduction_request(self, peer, dist, payload):
        if 0 <= self.max_peers < len(self.get_peers()):
            self.logger.debug("Dropping introduction request from (%s, %d): too many peers!",
                              peer.address[0], peer.address[1])
            return

        extra_payload = b''
        if payload.extra_bytes:
            self.logger.debug("Received introduction request with extra bytes")
            try:
                rendezvous_request, _ = self.serializer.unpack_serializable(RendezvousRequestPayload,
                                                                            payload.extra_bytes)
                rendezvous_response = self._create_rendezvous_response(rendezvous_request.challenge)
                # As we are sending the rendezvous response, we know this peer is interested in rendezvous.
                self.rendezvous_cache.add_peer(peer)
                extra_payload = self.serializer.pack_serializable(rendezvous_response)
            except PackError as e:
                self.logger.warning("Failed to unpack RendezvousRequestPayload: %s", e)

        if isinstance(payload.source_lan_address, UDPv4Address):
            peer.address = UDPv4LANAddress(*payload.source_lan_address)
        self.network.add_verified_peer(peer)
        self.network.discover_services(peer, [self.community_id, ])

        packet = self.create_introduction_response(payload.destination_address, peer.address, payload.identifier,
                                                   extra_bytes=extra_payload, new_style=peer.new_style_intro)

        self.endpoint.send(peer.address, packet)
        self.introduction_request_callback(peer, dist, payload)

    @lazy_wrapper(RendezvousRequestPayload)
    def on_rendezvous_request(self, peer, payload: RendezvousRequestPayload):
        self.logger.debug("Received rendezvous request from %s:%d", peer.address[0], peer.address[1])
        # As we are sending the rendezvous response, we know this peer is interested in rendezvous.
        self.rendezvous_cache.add_peer(peer)
        rendezvous_response = self._create_rendezvous_response(payload.challenge)
        self.ez_send(peer, rendezvous_response)

    @lazy_wrapper(RawRendezvousResponsePayload)
    def on_rendezvous_response(self, peer, payload: RawRendezvousResponsePayload):
        self.logger.debug("Received rendezvous response from %s:%d", peer.address[0], peer.address[1])
        self._handle_rendezvous_response(peer, payload)

    def introduction_response_callback(self, peer, dist, payload):
        super().introduction_response_callback(peer, dist, payload)
        if payload.extra_bytes:
            self.logger.debug("Received introduction response with extra bytes")
            try:
                raw_rendezvous_response, _ = self.serializer.unpack_serializable(RawRendezvousResponsePayload,
                                                                                 payload.extra_bytes)
                self._handle_rendezvous_response(peer, raw_rendezvous_response)

            except PackError as e:
                self.logger.warning("Failed to unpack RendezvousResponsePayload: %s", e)

    def introduction_request_callback(self, peer, dist, payload):
        super().introduction_request_callback(peer, dist, payload)
        # Send request to peer to send popular torrents
        self.ez_send(peer, PopularTorrentsRequest())

    def get_alive_checked_torrents(self) -> List[HealthInfo]:
        if not self.torrent_checker:
            return []

        # Filter torrents that have seeders
        return [health for health in self.torrent_checker.torrents_checked.values() if health.seeders > 0]

    def gossip_random_torrents_health(self):
        """
        Gossip random torrent health information to another peer.
        """
        if not self.get_peers() or not self.torrent_checker:
            return

        random_torrents = self.get_random_torrents()
        random_peer = random.choice(self.get_peers())

        self.ez_send(random_peer, TorrentsHealthPayload.create(random_torrents, {}))

    def ping_rendezvous(self):
        # Remove peers that haven't replied in a while.
        self.rendezvous_cache.clear_inactive_peers()

        for peer in self.rendezvous_cache.get_rendezvous_peers():
            payload = self._create_rendezvous_request()
            self.rendezvous_cache.set_rendezvous_challenge(peer, payload.challenge.nonce)
            self.ez_send(peer, payload)

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

    def _create_rendezvous_request(self) -> RendezvousRequestPayload:
        challenge = RendezvousChallenge.create()
        payload = RendezvousRequestPayload(challenge)
        return payload

    def _create_rendezvous_response(self, challenge: RendezvousChallenge) -> RendezvousResponsePayload:
        signature = challenge.sign(self.my_peer.key)
        payload = RendezvousResponsePayload(challenge, RendezvousSignature(signature))
        return payload

    def _handle_rendezvous_response(self, peer, raw_payload: RawRendezvousResponsePayload):
        signature, _ = self.serializer.unpack_serializable(RendezvousSignature, raw_payload.signature)
        challenge, _ = self.serializer.unpack_serializable(RendezvousChallenge, raw_payload.challenge)

        expected_nonce = self.rendezvous_cache.get_rendezvous_challenge(peer) or EMPTY_PEER_CHALLENGE
        if expected_nonce == EMPTY_PEER_CHALLENGE or expected_nonce != challenge.nonce:
            self.logger.warning(f"Received invalid rendezvous response from {peer.mid}")
            return

        if not self.crypto.is_valid_signature(peer.key, raw_payload.challenge, signature.signature):
            self.logger.warning(f"Received invalid signature from {peer.mid}")
            return
        else:
            # This nonce has been burned.
            self.rendezvous_cache.clear_peer_challenge(peer)

        self.logger.debug(f"Received valid rendezvous response from {peer.mid}")
        with db_session:
            certificate = self.rdb.Certificate.get(public_key=peer.mid)
            if not certificate:
                certificate = self.rdb.Certificate(public_key=peer.mid, counter=0)
            certificate.counter += 1
        return
