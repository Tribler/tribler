from ipv8.community import Community, DEFAULT_MAX_PEERS

from tribler.core.config.tribler_config_section import TriblerConfigSection

def args_kwargs_to_community_settings(settings_class, args, kwargs):
    return settings_class(my_peer=args[0] if len(args) > 0 else kwargs.pop("my_peer"),
                          endpoint=args[1] if len(args) > 1 else kwargs.pop("endpoint"),
                          network=args[2] if len(args) > 2 else kwargs.pop("network"),
                          max_peers=args[4] if len(args) > 3 else kwargs.pop("max_peers", DEFAULT_MAX_PEERS),
                          anonymize=args[5] if len(args) > 4 else kwargs.pop("anonymize", True),
                          **kwargs)


class TriblerCommunity(Community):
    """Base class for Tribler communities.
    """

    def __init__(self, *args, settings: TriblerConfigSection = None, **kwargs):
        community_settings = args_kwargs_to_community_settings(self.settings_class, args, kwargs)
        super().__init__(community_settings)
        self.settings = settings
        self.logger.info(f'Init. Settings: {settings}.')
