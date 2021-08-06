from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.metadata_store.manager.gigachannel_manager import GigaChannelManager


class GigachannelManagerComponent(Component):
    gigachannel_manager: GigaChannelManager

    @classmethod
    def should_be_enabled(cls, config):
        return config.chant.enabled and config.chant.manager_enabled and config.libtorrent.enabled

    @classmethod
    def make_implementation(cls, config, enable):
        if enable:
            from tribler_core.components.implementation.gigachannel_manager import GigachannelManagerComponentImp
            return GigachannelManagerComponentImp()
        return GigachannelManagerComponentMock()


@testcomponent
class GigachannelManagerComponentMock(GigachannelManagerComponent):
    gigachannel_manager = Mock()
