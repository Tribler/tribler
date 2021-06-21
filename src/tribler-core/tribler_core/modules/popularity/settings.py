from tribler_core.config.tribler_config_section import TriblerConfigSection


class PopularityCommunitySettings(TriblerConfigSection):
    enabled: bool = True
    cache_dir: str = 'health_cache'
