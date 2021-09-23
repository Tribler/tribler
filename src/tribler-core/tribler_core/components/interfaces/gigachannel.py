from unittest.mock import Mock

from ipv8_service import IPv8
from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity


class GigaChannelComponent(Component):
    enable_in_gui_test_mode = True

    community: GigaChannelCommunity
    _ipv8: IPv8


@testcomponent
class GigaChannelComponentMock(GigaChannelComponent):
    community = Mock()
