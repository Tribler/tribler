from typing import List

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.tunnel.socks5.server import Socks5Server


class SocksServersComponent(Component):
    socks_ports: List[int]
    socks_servers: List[Socks5Server]


@testcomponent
class SocksServersComponentMock(SocksServersComponent):
    socks_ports = []
    socks_servers = []
