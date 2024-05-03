from __future__ import annotations

from typing import TYPE_CHECKING

from ipv8.community import Community, CommunitySettings
from ipv8.lazy_community import lazy_wrapper

from tribler.core.user_activity.payload import InfohashPreferencePayload, PullPreferencePayload

if TYPE_CHECKING:
    from ipv8.types import Peer

    from tribler.core.user_activity.manager import UserActivityManager


class UserActivitySettings(CommunitySettings):
    """
    Settings for the UserActivityCommunity.
    """

    manager: UserActivityManager
    crawler_mid: bytes = b"Jy\xa9\x90G\x86\xec[\xde\xda\xf8(\xe6\x81l\xa2\xe0\xba\xaf\xac"


class UserActivityCommunity(Community):
    """
    A community that shares preferred infohashes.
    """

    community_id = b"UserActivityOverlay\x00"
    settings_class = UserActivitySettings

    def __init__(self, settings: UserActivitySettings) -> None:
        """
        Create a new user activity community.
        """
        super().__init__(settings)

        self.composition = settings

        self.add_message_handler(InfohashPreferencePayload, self.on_infohash_preference)
        self.add_message_handler(PullPreferencePayload, self.on_pull_preference)

        self.register_task("Gossip random preference", self.gossip, interval=5.0)

    def gossip(self, receivers: list[Peer] | None = None) -> None:
        """
        Select a random database entry and send it to a random peer.
        """
        neighbors = receivers if receivers is not None else self.get_peers()  # Explicit empty list leads to nothing.
        if not neighbors:
            return

        aggregate_for = 0 if receivers is not None else len(neighbors)
        aggregate = self.composition.manager.database_manager.get_random_query_aggregate(aggregate_for)

        if aggregate is not None:
            payload = InfohashPreferencePayload(*aggregate)
            for peer in neighbors:
                self.ez_send(peer, payload)

    @lazy_wrapper(InfohashPreferencePayload)
    def on_infohash_preference(self, peer: Peer, payload: InfohashPreferencePayload) -> None:
        """
        We received a preference message.
        """
        self.composition.manager.database_manager.store_external(payload.query, payload.infohashes, payload.weights,
                                                                 peer.public_key.key_to_bin())

        for infohash, _ in sorted(zip(payload.infohashes, payload.weights), key=lambda x: x[1], reverse=True):
            self.composition.manager.check(infohash)
            break

    @lazy_wrapper(PullPreferencePayload)
    def on_pull_preference(self, peer: Peer, payload: PullPreferencePayload) -> None:
        """
        We received a pull message. We only allow specific peers to do this!
        """
        peer_mid = peer.mid

        if peer_mid != self.composition.crawler_mid:
            self.logger.warning("Refusing to serve a pull from %s, not a crawler!", str(peer))
            return
        if payload.mid != self.my_peer.mid:
            self.logger.warning("Refusing to serve a pull from %s, replay attack?!", str(peer))
            return

        self.gossip([peer])
