from typing import List

from tribler.core.components.component import Component
from tribler.core.components.reporter.reporter_component import ReporterComponent
from tribler.core.components.socks_servers.socks5.server import Socks5Server
from tribler.core.utilities.network_utils import default_network_utils

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
            # To prevent a once-in-a-blue-moon situation when SOCKS server accidentally occupy
            # a port reserved by other services (e.g. REST API), we track our ports usage and assign
            # ports through a single, default NetworkUtils instance
            socks_server = Socks5Server(port=default_network_utils.get_random_free_port())
            self.socks_servers.append(socks_server)
            await socks_server.start()
            self.socks_ports.append(socks_server.port)

        self.logger.info(f'Socks listen port: {self.socks_ports}')

    async def shutdown(self):
        for socks_server in self.socks_servers:
            await socks_server.stop()
