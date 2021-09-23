from unittest.mock import Mock

from ipv8_service import IPv8
from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.tunnel.community.community import TriblerTunnelCommunity


class TunnelsComponent(Component):
    community: TriblerTunnelCommunity
    _ipv8: IPv8


@testcomponent
class TunnelsComponentMock(TunnelsComponent):
    community = Mock()
