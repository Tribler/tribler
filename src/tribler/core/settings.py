from pydantic import Field

from tribler.core.config.tribler_config_section import TriblerConfigSection


class GeneralSettings(TriblerConfigSection):
    version: str = ""
    log_dir: str = "log"
    version_checker_enabled: bool = True
    testnet: bool = Field(default=False, env='TESTNET')
