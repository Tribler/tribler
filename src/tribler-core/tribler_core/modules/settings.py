from typing import Optional

from pydantic import validator

from tribler_common.network_utils import NetworkUtils
from tribler_core.config.tribler_config_section import TriblerConfigSection


class BootstrapSettings(TriblerConfigSection):
    enabled: bool = True
    max_download_rate: int = 1000000
    infohash: str = 'b496932f32daad964e1b63188faabf74d22b45ea'


class Ipv8Settings(TriblerConfigSection):
    enabled: bool = True
    port: int = 7759
    address: str = '0.0.0.0'
    bootstrap_override: Optional[str] = None
    statistics: bool = False
    walk_interval: float = 0.5
    walk_scaling_enabled: bool = True
    walk_scaling_upper_limit: float = 3.0

    @validator('port')
    def validate_port(cls, v):
        assert 0 <= v <= NetworkUtils.MAX_PORT, 'Port must be in range [0..65535]'
        return v


class DiscoveryCommunitySettings(TriblerConfigSection):
    enabled: bool = True


class DHTSettings(TriblerConfigSection):
    enabled: bool = True


class TrustchainSettings(TriblerConfigSection):
    ec_keypair_filename: str = 'ec_multichain.pem'
    testnet_keypair_filename: str = 'ec_trustchain_testnet.pem'
    testnet: bool = False


class WatchFolderSettings(TriblerConfigSection):
    enabled: bool = False
    directory: str = ''
