from __future__ import annotations

from ipv8.community import Community, CommunitySettings

from tribler.core.config.tribler_config_section import TriblerConfigSection


class TriblerSettings(CommunitySettings):
    settings: TriblerConfigSection | None = None


class TriblerCommunity(Community):
    """Base class for Tribler communities.
    """

    settings_class = TriblerSettings

    def __init__(self, settings: TriblerSettings):
        super().__init__(settings)
        self.settings = settings.settings
        self.logger.info(f'Init. Settings: {settings}.')
