from typing import List

from ipv8.messaging.interfaces.dispatcher.endpoint import DispatcherEndpoint

from ipv8_rust_tunnels.endpoint import RustEndpoint

from tribler.core.components.component import Component
from tribler.core.components.exceptions import NoneComponent
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.reporter.reporter_component import ReporterComponent
from tribler.core.components.socks_servers.socks5.server import Socks5Server
from tribler.core.utilities.network_utils import default_network_utils


NUM_SOCKS_PROXIES = 3
SOCKS5_SERVER_PORTS = 'socks5_server_ports'


class SocksServersComponent(Component):
    socks_ports: List[int]
    socks_servers: List[Socks5Server]

    async def run(self):
        await self.get_component(ReporterComponent)
        self.socks_servers = []
        self.socks_ports = []

        # If IPv8 has been started using the RustEndpoint, find it
        ipv8_component = await self.maybe_component(Ipv8Component)
        rust_endpoint = None
        if not isinstance(ipv8_component, NoneComponent):
            ipv4_endpoint = ipv8_component.ipv8.endpoint
            if isinstance(ipv4_endpoint, DispatcherEndpoint):
                ipv4_endpoint = ipv4_endpoint.interfaces.get("UDPIPv4", None)
            rust_endpoint = ipv4_endpoint if isinstance(ipv4_endpoint, RustEndpoint) else None

        # Start the SOCKS5 servers
        for hops in range(NUM_SOCKS_PROXIES):
            socks_server = Socks5Server(hops + 1, rust_endpoint=rust_endpoint)
            self.socks_servers.append(socks_server)
            await socks_server.start()
            socks_port = socks_server.port
            self.socks_ports.append(socks_port)

            # To prevent a once-in-a-blue-moon situation when a server accidentally occupies
            # the port reserved by other services (e.g. REST API), we track our ports usage
            # and assign ports through a single, default NetworkUtils instance
            default_network_utils.remember(socks_port)

        self.logger.info(f'Socks listen port: {self.socks_ports}')

        # Set the SOCKS5 server ports in the reporter for debugging Network errors
        self.reporter.additional_information[SOCKS5_SERVER_PORTS] = self.socks_ports

    async def shutdown(self):
        for socks_server in self.socks_servers:
            await socks_server.stop()
