from pydantic import Field

from tribler.core.config.tribler_config_section import TriblerConfigSection


class ContentDiscoveryComponentConfig(TriblerConfigSection):
    enabled: bool = True
    testnet: bool = Field(default=False, env='CHANT_TESTNET')
    maximum_payload_size: int = 1300
