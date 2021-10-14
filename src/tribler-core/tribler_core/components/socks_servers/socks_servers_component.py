from typing import List

from tribler_core.components.base import Component
from tribler_core.components.reporter.reporter_component import ReporterComponent
from tribler_core.components.socks_servers.socks5.server import Socks5Server

NUM_SOCKS_PROXIES = 5


class SocksServersComponent(Component):
    socks_ports: List[int]
    socks_servers: List[Socks5Server]

    async def run(self):
        await self.get_component(ReporterComponent)
        self.socks_servers = []
        self.socks_ports = []
        # Start the SOCKS5 servers
        for _ in range(NUM_SOCKS_PROXIES):
            socks_server = Socks5Server()
            self.socks_servers.append(socks_server)
            await socks_server.start()
            self.socks_ports.append(socks_server.port)

        self.logger.info(f'Socks listen port: {self.socks_ports}')

    async def shutdown(self):
        for socks_server in self.socks_servers:
            await socks_server.stop()
