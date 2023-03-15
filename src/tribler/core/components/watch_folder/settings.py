from tribler.core.config.tribler_config_section import TriblerConfigSection


# pylint: disable=no-self-argument


class WatchFolderSettings(TriblerConfigSection):
    enabled: bool = False
    directory: str = ''
