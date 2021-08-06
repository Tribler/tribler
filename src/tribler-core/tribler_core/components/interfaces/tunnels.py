from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.tunnel.community.community import TriblerTunnelCommunity


class TunnelsComponent(Component):
    community: TriblerTunnelCommunity

    @classmethod
    def should_be_enabled(cls, config):
        return config.ipv8.enabled and config.tunnel_community.enabled

    @classmethod
    def make_implementation(cls, config, enable):
        if enable:
            from tribler_core.components.implementation.tunnels import TunnelsComponentImp
            return TunnelsComponentImp()
        return TunnelsComponentMock()


@testcomponent
class TunnelsComponentMock(TunnelsComponent):
    community = Mock()
