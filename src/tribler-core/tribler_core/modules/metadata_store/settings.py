from tribler_core.config.tribler_config_section import TriblerConfigSection


class ChantSettings(TriblerConfigSection):
    enabled: bool = True
    manager_enabled: bool = True
    channel_edit: bool = False
    channels_dir: str = 'channels'
    testnet: bool = False
