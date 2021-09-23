from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.metadata_store.manager.gigachannel_manager import GigaChannelManager


class GigachannelManagerComponent(Component):
    gigachannel_manager: GigaChannelManager


@testcomponent
class GigachannelManagerComponentMock(GigachannelManagerComponent):
    gigachannel_manager = Mock()
