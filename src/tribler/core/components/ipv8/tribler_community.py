from ipv8.community import Community

from tribler_core.config.tribler_config_section import TriblerConfigSection


class TriblerCommunity(Community):
    """Base class for Tribler communities.
    """

    def __init__(self, *args, settings: TriblerConfigSection = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = settings
        self.logger.info(f'Init. Settings: {settings}.')
