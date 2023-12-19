from tribler.core.config.tribler_config_section import TriblerConfigSection


class UserActivitySettings(TriblerConfigSection):
    enabled: bool = False
    max_query_history: int = 500
    health_check_interval: float = 5.0
