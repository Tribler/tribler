import ipaddress
from enum import Enum
from typing import List, Optional

from pydantic import validator

from tribler_common.network_utils import NetworkUtils
from tribler_core.config.tribler_config_section import TriblerConfigSection


# pylint: disable=no-self-argument
@validator('port', 'anon_listen_port')
def validate_port_with_minus_one(v):
    assert v is None or -1 <= v <= NetworkUtils.MAX_PORT, 'Port must be in range [-1..65535]'
    return v


class LibtorrentSettings(TriblerConfigSection):
    enabled: bool = True
    port: Optional[int] = None
    proxy_type: int = 0
    proxy_server: str = ':'
    proxy_auth: str = ':'
    max_connections_download: int = -1
    max_download_rate: int = 0
    max_upload_rate: int = 0
    utp: bool = True
    dht: bool = True
    dht_readiness_timeout: int = 30

    anon_listen_port: Optional[int] = None
    anon_proxy_type = 0

    anon_proxy_server_ip: str = '127.0.0.1'
    anon_proxy_server_ports: List[str] = ['-1', '-1', '-1', '-1', '-1']
    anon_proxy_auth: Optional[str] = None

    _port_validator = validator('port', 'anon_listen_port', allow_reuse=True)(validate_port_with_minus_one)

    @validator('anon_proxy_server_ip')
    def validate_ip_address(cls, v):
        return v if ipaddress.IPv4Network(v) else None

    @validator('proxy_type', 'anon_proxy_type')
    def validate_proxy_type(cls, v):
        assert v is None or 0 <= v <= 5, 'Proxy type must be in range [0..5]'
        return v


class SeedingMode(str, Enum):
    forever = 'forever'
    never = 'never'
    ratio = 'ratio'
    time = 'time'


class DownloadDefaultsSettings(TriblerConfigSection):
    anonymity_enabled: bool = True
    number_hops: int = 1
    safeseeding_enabled: bool = True
    saveas: Optional[str] = None
    seeding_mode: SeedingMode = SeedingMode.forever
    seeding_ratio: float = 2.0
    seeding_time: float = 60
    channel_download: bool = False
    add_download_to_channel: bool = False

    @validator('number_hops')
    def validate_number_hops(cls, v):
        assert 0 <= v <= 3, 'Number hops must be in range [0..3]'
        return v
