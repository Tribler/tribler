from __future__ import annotations

from typing import Sequence

from ipv8.community import CommunitySettings
from tribler.core.components.database.db.tribler_database import TriblerDatabase
from tribler.core.components.database.db.store import MetadataStore
from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.utilities.notifier import Notifier


class ContentDiscoverySettings(CommunitySettings):
    random_torrent_interval: float = 5  # seconds
    random_torrent_count: int = 10
    max_query_peers: int = 20
    maximum_payload_size: int = 1300
    max_response_size: int = 100  # Max number of entries returned by SQL query

    binary_fields: Sequence[str] = ("infohash", "channel_pk")
    deprecated_parameters: Sequence[str] = ('subscribed', 'attribute_ranges', 'complete_channel')

    metadata_store: MetadataStore
    torrent_checker: TorrentChecker
    tribler_db: TriblerDatabase | None = None
    notifier: Notifier | None = None
