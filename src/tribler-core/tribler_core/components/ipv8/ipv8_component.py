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

from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.restapi.restapi_component import RestfulComponent

INFINITE = -1


# pylint: disable=import-outside-toplevel

class Ipv8Component(RestfulComponent):
    ipv8: IPv8 = None
    peer: Peer
    dht_discovery_community: Optional[DHTDiscoveryCommunity] = None

    _task_manager: TaskManager
    _peer_discovery_community: Optional[DiscoveryCommunity] = None

    async def run(self):
        await super().run()

        config = self.session.config

        self._task_manager = TaskManager()

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

        key_component = await self.require_component(KeyComponent)
        self.peer = Peer(key_component.primary_key)

        if config.ipv8.statistics and not config.gui_test_mode:
            # Enable gathering IPv8 statistics
            for overlay in ipv8.overlays:
                ipv8.endpoint.enable_community_statistics(overlay.get_prefix(), True)

        if config.ipv8.walk_scaling_enabled and not config.gui_test_mode:
            from tribler_core.components.ipv8.ipv8_health_monitor import IPv8Monitor
            IPv8Monitor(ipv8,
                        config.ipv8.walk_interval,
                        config.ipv8.walk_scaling_upper_limit).start(self._task_manager)

        if config.dht.enabled:
            self._init_dht_discovery_community()

        if not config.gui_test_mode:
            if config.discovery_community.enabled:
                self._init_peer_discovery_community()
        else:
            if config.dht.enabled:
                self.dht_discovery_community.routing_tables[UDPv4Address] = RoutingTable('\x00' * 20)

        await self.init_endpoints(endpoints=['statistics'], values={'ipv8': ipv8})
        await self.init_ipv8_endpoints(ipv8, endpoints=[
            'asyncio', 'attestation', 'dht', 'identity', 'isolation', 'network', 'noblockdht', 'overlays'
        ])

    def initialise_community_by_default(self, community, default_random_walk_max_peers=20):
        community.bootstrappers.append(self.make_bootstrapper())

        # Value of `target_peers` must not be equal to the value of `max_peers` for the community.
        # This causes a deformed network topology and makes it harder for peers to connect to others.
        # More information: https://github.com/Tribler/py-ipv8/issues/979#issuecomment-896643760
        #
        # Then:
        # random_walk_max_peers should be less than community.max_peers:
        random_walk_max_peers = min(default_random_walk_max_peers, community.max_peers - 10)

        # random_walk_max_peers should be greater than 0
        random_walk_max_peers = max(0, random_walk_max_peers)
        self.ipv8.add_strategy(community, RandomWalk(community), random_walk_max_peers)

    async def unload_community(self, community):
        await self.ipv8.unload_overlay(community)

    def make_bootstrapper(self) -> DispersyBootstrapper:
        args = DISPERSY_BOOTSTRAPPER['init']
        if bootstrap_override := self.session.config.ipv8.bootstrap_override:
            address, port = bootstrap_override.split(':')
            args = {'ip_addresses': [(address, int(port))], 'dns_addresses': []}
        return DispersyBootstrapper(**args)

    def _init_peer_discovery_community(self):
        ipv8 = self.ipv8
        community = DiscoveryCommunity(self.peer, ipv8.endpoint, ipv8.network, max_peers=100)
        self.initialise_community_by_default(community)
        ipv8.add_strategy(community, RandomChurn(community), INFINITE)
        ipv8.add_strategy(community, PeriodicSimilarity(community), INFINITE)
        self._peer_discovery_community = community

    def _init_dht_discovery_community(self):
        ipv8 = self.ipv8
        community = DHTDiscoveryCommunity(self.peer, ipv8.endpoint, ipv8.network, max_peers=60)
        self.initialise_community_by_default(community)
        ipv8.add_strategy(community, PingChurn(community), INFINITE)
        self.dht_discovery_community = community

    async def shutdown(self):
        await super().shutdown()

        if not self.ipv8:
            return

        for overlay in (self.dht_discovery_community, self._peer_discovery_community):
            if overlay:
                await self.ipv8.unload_overlay(overlay)

        await self._task_manager.shutdown_task_manager()
        await self.ipv8.stop(stop_loop=False)
