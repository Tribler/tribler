from enum import Enum
from typing import Optional

from pydantic import validator

from tribler.core.config.tribler_config_section import TriblerConfigSection
from tribler.core.utilities.network_utils import NetworkUtils
from tribler.core.utilities.osutils import get_home_dir
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.utilities import INT32_MAX

TRIBLER_DOWNLOADS_DEFAULT = "TriblerDownloads"


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
    upnp: bool = True
    natpmp: bool = True
    lsd: bool = True

    _port_validator = validator('port', allow_reuse=True)(validate_port_with_minus_one)

    @validator('proxy_type')
    def validate_proxy_type(cls, v):
        assert v is None or 0 <= v <= 5, 'Proxy type must be in range [0..5]'
        return v

    def __setattr__(self, key, value):
        """Override __setattr__ to limit the max int value to `INT_MAX` (the max int value for C)"""
        if isinstance(value, int):
            value = min(INT32_MAX, value)
        super().__setattr__(key, value)


class SeedingMode(str, Enum):
    forever = 'forever'
    never = 'never'
    ratio = 'ratio'
    time = 'time'


def get_default_download_dir(home: Optional[Path] = None, tribler_downloads_name=TRIBLER_DOWNLOADS_DEFAULT) -> Path:
    """
    Returns the default dir to save content to.
    Could be one of:
        - TriblerDownloads
        - $HOME/Downloads/TriblerDownloads
        - $HOME/TriblerDownloads
    """
    path = Path(tribler_downloads_name)
    if path.is_dir():
        return path.resolve()

    home = home or get_home_dir()
    downloads = home / "Downloads"
    if downloads.is_dir():
        return downloads.resolve() / tribler_downloads_name

    return home.resolve() / tribler_downloads_name


class DownloadDefaultsSettings(TriblerConfigSection):
    anonymity_enabled: bool = True
    number_hops: int = 1
    safeseeding_enabled: bool = True
    saveas: str = str(get_default_download_dir())
    seeding_mode: SeedingMode = SeedingMode.forever
    seeding_ratio: float = 2.0
    seeding_time: float = 60
    channel_download: bool = False
    add_download_to_channel: bool = False

    @validator('number_hops')
    def validate_number_hops(cls, v):
        assert 0 <= v <= 3, 'Number hops must be in range [0..3]'
        return v
