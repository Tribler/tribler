from tribler_core.components.base import Component
from tribler_core.modules.tunnel.community.community import TriblerTunnelCommunity


class TunnelsComponent(Component):
    community: TriblerTunnelCommunity
