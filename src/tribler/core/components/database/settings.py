from pydantic import Field

from tribler.core.config.tribler_config_section import TriblerConfigSection
from tribler.core.utilities.simpledefs import STATEDIR_CHANNELS_DIR


class ChantSettings(TriblerConfigSection):
    enabled: bool = True
    testnet: bool = Field(default=False, env='CHANT_TESTNET')
    channels_dir: str = STATEDIR_CHANNELS_DIR
