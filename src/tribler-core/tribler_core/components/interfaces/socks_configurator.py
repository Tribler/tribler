from typing import List, Tuple

from tribler_core.components.base import Component
from tribler_core.modules.tunnel.socks5.server import Socks5Server


class SocksServersComponent(Component):
    socks_ports: List[int]
    socks_servers: List[Socks5Server]
