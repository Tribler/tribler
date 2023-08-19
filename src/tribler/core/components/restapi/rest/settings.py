from typing import Optional

from pydantic import validator

from tribler.core.components.libtorrent.settings import validate_port_with_minus_one
from tribler.core.config.tribler_config_section import TriblerConfigSection


class APISettings(TriblerConfigSection):
    http_enabled: bool = False
    http_port: int = -1
    http_host: str = "127.0.0.1"
    https_enabled: bool = False
    https_host: str = "127.0.0.1"
    https_port: int = -1
    https_certfile: str = ''
    key: Optional[str] = None
    retry_port: bool = True

    _port_validator = validator('http_port', 'https_port', allow_reuse=True)(validate_port_with_minus_one)
