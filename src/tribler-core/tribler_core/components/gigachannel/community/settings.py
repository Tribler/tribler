from pydantic import Field

from tribler_common.simpledefs import STATEDIR_CHANNELS_DIR
from tribler_core.config.tribler_config_section import TriblerConfigSection


class ChantSettings(TriblerConfigSection):
    enabled: bool = True
    manager_enabled: bool = True
    channel_edit: bool = False
    channels_dir: str = STATEDIR_CHANNELS_DIR
    testnet: bool = Field(default=False, env='CHANT_TESTNET')

    queried_peers_limit: int = 1000
    # The maximum number of peers that we got from channels to peers mapping,
    # that must be queried in addition to randomly queried peers
    max_mapped_query_peers = 3
