from pydantic import Field

from tribler.core.config.tribler_config_section import TriblerConfigSection


class TunnelCommunitySettings(TriblerConfigSection):
    enabled: bool = True
    exitnode_enabled: bool = False
    testnet: bool = Field(default=False, env='TUNNEL_TESTNET')
    min_circuits: int = 3
    max_circuits: int = 10
