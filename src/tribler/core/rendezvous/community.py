from __future__ import annotations

from typing import TYPE_CHECKING

from ipv8.community import Community, CommunitySettings
from ipv8.lazy_community import lazy_wrapper

from tribler.core.rendezvous.payload import PullRecordPayload, RecordPayload

if TYPE_CHECKING:
    from ipv8.types import Peer

    from tribler.core.rendezvous.database import RendezvousDatabase


class RendezvousSettings(CommunitySettings):
    """
    Settings for the RendezvousCommunity.
    """

    database: RendezvousDatabase
    crawler_mid: bytes = b"Jy\xa9\x90G\x86\xec[\xde\xda\xf8(\xe6\x81l\xa2\xe0\xba\xaf\xac"


class RendezvousCommunity(Community):
    """
    A community that shares preferred infohashes.
    """

    community_id = b"RendezvousCommunity\x00"
    settings_class = RendezvousSettings

    def __init__(self, settings: RendezvousSettings) -> None:
        """
        Create a new user activity community.
        """
        super().__init__(settings)

        self.composition = settings

        self.add_message_handler(PullRecordPayload, self.on_pull_record)
        self.add_message_handler(RecordPayload, self.on_record)

    @lazy_wrapper(RecordPayload)
    def on_record(self, peer: Peer, payload: RecordPayload) -> None:
        """
        We are not a crawler. Do nothing.
        """

    @lazy_wrapper(PullRecordPayload)
    def on_pull_record(self, peer: Peer, payload: PullRecordPayload) -> None:
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

        entry = self.composition.database.random()
        if entry is None:
            return
        self.ez_send(peer, RecordPayload(entry.public_key, entry.ip, entry.port, entry.ping, entry.start, entry.stop))
