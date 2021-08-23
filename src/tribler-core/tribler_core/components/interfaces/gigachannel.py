from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity


class GigaChannelComponent(Component):
    enable_in_gui_test_mode = True

    community: GigaChannelCommunity

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return config.ipv8.enabled and config.chant.enabled

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.gigachannel import GigaChannelComponentImp
            return GigaChannelComponentImp(cls)
        return GigaChannelComponentMock(cls)


@testcomponent
class GigaChannelComponentMock(GigaChannelComponent):
    community = Mock()
