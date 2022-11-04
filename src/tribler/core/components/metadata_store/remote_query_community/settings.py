from tribler.core.config.tribler_config_section import TriblerConfigSection


class RemoteQueryCommunitySettings(TriblerConfigSection):
    minimal_blob_size: int = 200
    maximum_payload_size: int = 1300
    max_entries: int = maximum_payload_size // minimal_blob_size

    # The next option is currently used by GigaChannelCommunity only. We probably should move it to the
    # GigaChannelCommunity settings or to a dedicated search-related section. The value of the option is corresponding
    # with the TARGET_PEERS_NUMBER of src/tribler/core/components/gigachannel/community/sync_strategy.py, that is, to
    # the number of peers that GigaChannelCommunity will have after a long run (initially, the number of peers in
    # GigaChannelCommunity can rise up to several hundred due to DiscoveryBooster). The number of parallel remote
    # requests should be not too small (to have various results from remote peers) and not too big (to avoid flooding
    # the network with exceedingly high number of queries). TARGET_PEERS_NUMBER looks like a good middle ground here.
    max_query_peers: int = 20

    max_response_size: int = 100  # Max number of entries returned by SQL query
    max_channel_query_back: int = 4  # Max number of entries to query back on receiving an unknown channel
    push_updates_back_enabled = True

    @property
    def channel_query_back_enabled(self):
        return self.max_channel_query_back > 0
