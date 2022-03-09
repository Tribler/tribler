from typing import Optional

from pydantic import validator

from tribler_core.config.tribler_config_section import TriblerConfigSection
from tribler_core.components.libtorrent.settings import validate_port_with_minus_one


class APISettings(TriblerConfigSection):
    http_enabled: bool = False
    http_port: int = -1
    https_enabled: bool = False
    https_port: int = -1
    https_certfile: str = ''
    key: Optional[str] = None
    retry_port: bool = False

    _port_validator = validator('http_port', 'https_port', allow_reuse=True)(validate_port_with_minus_one)
