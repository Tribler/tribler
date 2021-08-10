from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity


class GigaChannelComponent(Component):
    core = True

    community: GigaChannelCommunity

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return config.chant.enabled

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.gigachannel import GigaChannelComponentImp
            return GigaChannelComponentImp()
        return GigaChannelComponentMock()


@testcomponent
class GigaChannelComponentMock(GigaChannelComponent):
    community = Mock()
