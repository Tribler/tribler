from typing import List

from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.tunnel.socks5.server import Socks5Server


class SocksServersComponent(Component):
    socks_ports: List[int]
    socks_servers: List[Socks5Server]

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return config.tunnel_community.enabled and config.libtorrent.enabled

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.socks_configurator import SocksServersComponentImp
            return SocksServersComponentImp()
        return SocksServersComponentMock()


@testcomponent
class SocksServersComponentMock(SocksServersComponent):
    socks_ports = []
    socks_servers = []
