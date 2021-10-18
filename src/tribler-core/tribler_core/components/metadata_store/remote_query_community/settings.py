from tribler_core.config.tribler_config_section import TriblerConfigSection


class RemoteQueryCommunitySettings(TriblerConfigSection):
    minimal_blob_size: int = 200
    maximum_payload_size: int = 1300
    max_entries: int = maximum_payload_size // minimal_blob_size
    max_query_peers: int = 5
    max_response_size: int = 100  # Max number of entries returned by SQL query
    max_channel_query_back: int = 4  # Max number of entries to query back on receiving an unknown channel
    push_updates_back_enabled = True

    @property
    def channel_query_back_enabled(self):
        return self.max_channel_query_back > 0
