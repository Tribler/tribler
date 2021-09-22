from unittest.mock import Mock

from ipv8_service import IPv8

from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.popularity.community import PopularityCommunity


class PopularityComponent(Component):
    enable_in_gui_test_mode = True

    community: PopularityCommunity
    _ipv8: IPv8

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return config.ipv8.enabled and config.popularity_community.enabled

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.popularity import PopularityComponentImp
            return PopularityComponentImp(cls)
        return PopularityComponentMock(cls)


@testcomponent
class PopularityComponentMock(PopularityComponent):
    community = Mock()
