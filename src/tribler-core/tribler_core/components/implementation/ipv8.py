from typing import Optional

from ipv8.bootstrapping.dispersy.bootstrapper import DispersyBootstrapper
from ipv8.configuration import ConfigBuilder, DISPERSY_BOOTSTRAPPER
from ipv8.dht.churn import PingChurn
from ipv8.dht.discovery import DHTDiscoveryCommunity
from ipv8.dht.routing import RoutingTable
from ipv8.messaging.interfaces.dispatcher.endpoint import DispatcherEndpoint
from ipv8.messaging.interfaces.udp.endpoint import UDPv4Address
from ipv8.peer import Peer
from ipv8.peerdiscovery.churn import RandomChurn
from ipv8.peerdiscovery.community import DiscoveryCommunity, PeriodicSimilarity
from ipv8.peerdiscovery.discovery import RandomWalk
from ipv8.taskmanager import TaskManager
from ipv8_service import IPv8
from tribler_core.components.base import Component
from tribler_core.components.implementation.masterkey import MasterKeyComponent
from tribler_core.components.implementation.reporter import ReporterComponent
from tribler_core.components.implementation.restapi import RESTComponent
from tribler_core.restapi.rest_manager import RESTManager

INFINITE = -1


class Ipv8Component(Component):
    task_manager: TaskManager
    rest_manager: Optional[RESTManager]

    ipv8: IPv8
    peer: Peer
    peer_discovery_community: Optional[DiscoveryCommunity]
    dht_discovery_community: Optional[DHTDiscoveryCommunity]

    async def run(self):
        await self.use(ReporterComponent, required=False)

        config = self.session.config

        rest_component = await self.use(RESTComponent, required=False)
        rest_manager = self.rest_manager = rest_component.rest_manager if rest_component.enabled else None

        self.task_manager = TaskManager()

        port = config.ipv8.port
        address = config.ipv8.address
        self.logger.info('Starting ipv8')
        self.logger.info(f'Port: {port}. Address: {address}')
        ipv8_config_builder = (ConfigBuilder()
                               .set_port(port)
                               .set_address(address)
                               .clear_overlays()
                               .clear_keys()  # We load the keys ourselves
                               .set_working_directory(str(config.state_dir))
                               .set_walker_interval(config.ipv8.walk_interval))

        if config.gui_test_mode:
            endpoint = DispatcherEndpoint([])
        else:
            # IPv8 includes IPv6 support by default.
            # We only load IPv4 to not kill all Tribler overlays (currently, it would instantly crash all users).
            # If you want to test IPv6 in Tribler you can set ``endpoint = None`` here.
            endpoint = DispatcherEndpoint(["UDPIPv4"], UDPIPv4={'port': port,
                                                                'ip': address})
        ipv8 = IPv8(ipv8_config_builder.finalize(),
                    enable_statistics=config.ipv8.statistics and not config.gui_test_mode,
                    endpoint_override=endpoint)
        await ipv8.start()
        self.ipv8 = ipv8

        masterkey = await self.use(MasterKeyComponent)

        self.peer = Peer(masterkey.keypair)

        if config.ipv8.statistics and not config.gui_test_mode:
            # Enable gathering IPv8 statistics
            for overlay in ipv8.overlays:
                ipv8.endpoint.enable_community_statistics(overlay.get_prefix(), True)

        if config.ipv8.walk_scaling_enabled and not config.gui_test_mode:
            from tribler_core.modules.ipv8_health_monitor import IPv8Monitor
            IPv8Monitor(ipv8,
                        config.ipv8.walk_interval,
                        config.ipv8.walk_scaling_upper_limit).start(self.task_manager)

        if rest_manager:
            rest_manager.get_endpoint('statistics').ipv8 = ipv8

        self.peer_discovery_community = self.dht_discovery_community = None

        if config.dht.enabled:
            self.init_dht_discovery_community()

        if not self.session.config.gui_test_mode:
            if config.discovery_community.enabled:
                self.init_peer_discovery_community()
        else:
            if config.dht.enabled:
                self.dht_discovery_community.routing_tables[UDPv4Address] = RoutingTable('\x00' * 20)

        endpoints_to_init = ['/asyncio', '/attestation', '/dht', '/identity',
                             '/isolation', '/network', '/noblockdht', '/overlays']

        if rest_manager:
            for path, endpoint in rest_manager.get_endpoint('ipv8').endpoints.items():
                if path in endpoints_to_init:
                    endpoint.initialize(ipv8)

    def make_bootstrapper(self) -> DispersyBootstrapper:
        args = DISPERSY_BOOTSTRAPPER['init']
        if bootstrap_override := self.session.config.ipv8.bootstrap_override:
            address, port = bootstrap_override.split(':')
            args = {'ip_addresses': [(address, int(port))], 'dns_addresses': []}
        return DispersyBootstrapper(**args)

    def init_peer_discovery_community(self):
        ipv8 = self.ipv8
        community = DiscoveryCommunity(self.peer, ipv8.endpoint, ipv8.network, max_peers=100)
        ipv8.add_strategy(community, RandomChurn(community), INFINITE)
        ipv8.add_strategy(community, PeriodicSimilarity(community), INFINITE)
        ipv8.add_strategy(community, RandomWalk(community), 20)
        community.bootstrappers.append(self.make_bootstrapper())
        self.peer_discovery_community = community

    def init_dht_discovery_community(self):
        ipv8 = self.ipv8
        community = DHTDiscoveryCommunity(self.peer, ipv8.endpoint, ipv8.network, max_peers=60)
        ipv8.add_strategy(community, PingChurn(community), INFINITE)
        ipv8.add_strategy(community, RandomWalk(community), 20)
        community.bootstrappers.append(self.make_bootstrapper())
        self.dht_discovery_community = community

    async def shutdown(self):
        if self.rest_manager:
            self.rest_manager.get_endpoint('statistics').ipv8 = None
        await self.release(RESTComponent)

        for overlay in (self.dht_discovery_community, self.peer_discovery_community):
            if overlay:
                await self.ipv8.unload_overlay(overlay)

        await self.unused.wait()
        self.session.notifier.notify_shutdown_state("Shutting down IPv8...")
        await self.task_manager.shutdown_task_manager()
        await self.ipv8.stop(stop_loop=False)
