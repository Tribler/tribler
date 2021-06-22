from typing import List, Optional

from tribler_core.config.tribler_config_section import TriblerConfigSection


class TunnelCommunitySettings(TriblerConfigSection):
    enabled: bool = True
    socks5_listen_ports: Optional[List[int]] = None
    exitnode_enabled: bool = False
    random_slots: int = 5
    competing_slots: int = 15
    testnet: bool = False
