from unittest.mock import Mock

from ipv8_service import IPv8
from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.popularity.community import PopularityCommunity


class PopularityComponent(Component):
    enable_in_gui_test_mode = True

    community: PopularityCommunity
    _ipv8: IPv8


@testcomponent
class PopularityComponentMock(PopularityComponent):
    community = Mock()
