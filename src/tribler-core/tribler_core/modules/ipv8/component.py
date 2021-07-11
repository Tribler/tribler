from ipv8.bootstrapping.dispersy.bootstrapper import DispersyBootstrapper
from ipv8.configuration import ConfigBuilder
from ipv8.dht.discovery import DHTDiscoveryCommunity
from ipv8.messaging.interfaces.dispatcher.endpoint import DispatcherEndpoint
from ipv8.peer import Peer
from ipv8.peerdiscovery.churn import RandomChurn
from ipv8.peerdiscovery.community import DiscoveryCommunity, PeriodicSimilarity
from ipv8.peerdiscovery.discovery import RandomWalk
from ipv8.taskmanager import TaskManager

from ipv8_service import IPv8

from tribler_core.modules.component import Component

INFINITE = -1


class Ipv8Component(Component):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = None
        self.ipv8 = None
        self.ipv8_tasks = None

    async def run(self, mediator):
        await super().run(mediator)
        self.config = mediator.config
        trustchain_keypair = mediator.trustchain_keypair

        peer = Peer(trustchain_keypair)
        ipv8_tasks = TaskManager()

        ipv8 = await self.create_ipv8(self.config.ipv8, ipv8_tasks, self.config.core_test_mode)
        bootstrapper = await self.create_bootstrapper(self.config.ipv8.bootstrap_override)
        await self.create_default_communities(peer, ipv8, bootstrapper, mediator)

        self.ipv8 = ipv8
        self.ipv8_tasks = ipv8_tasks

        mediator.optional['peer'] = peer
        mediator.optional['bootstrapper'] = bootstrapper
        mediator.optional['ipv8'].set_result(ipv8)

    async def shutdown(self, mediator):
        await super().shutdown(mediator)
        mediator.notifier.notify_shutdown_state("Shutting down IPv8...")
        await self.ipv8.stop(stop_loop=False)
        await self.ipv8_tasks.shutdown_task_manager()

    async def create_ipv8(self, config, ipv8_tasks, core_test_mode=False):
        port = config.port
        address = config.address
        self.logger.info('Starting ipv8')
        self.logger.info(f'Port: {port}. Address: {address}')
        ipv8_config_builder = (ConfigBuilder()
                               .set_port(port)
                               .set_address(address)
                               .clear_overlays()
                               .clear_keys()  # We load the keys ourselves
                               .set_working_directory(str(self.config.state_dir))
                               .set_walker_interval(config.walk_interval))

        if core_test_mode:
            endpoint = DispatcherEndpoint([])
        else:
            # IPv8 includes IPv6 support by default.
            # We only load IPv4 to not kill all Tribler overlays (currently, it would instantly crash all users).
            # If you want to test IPv6 in Tribler you can set ``endpoint = None`` here.
            endpoint = DispatcherEndpoint(["UDPIPv4"], UDPIPv4={'port': port,
                                                                'ip': address})
        ipv8 = IPv8(ipv8_config_builder.finalize(),
                    enable_statistics=config.statistics and not core_test_mode,
                    endpoint_override=endpoint)
        await ipv8.start()

        if config.statistics and not core_test_mode:
            # Enable gathering IPv8 statistics
            for overlay in ipv8.overlays:
                ipv8.endpoint.enable_community_statistics(overlay.get_prefix(), True)

        if config.walk_scaling_enabled and not core_test_mode:
            from tribler_core.modules.ipv8_health_monitor import IPv8Monitor
            IPv8Monitor(ipv8,
                        config.walk_interval,
                        config.walk_scaling_upper_limit).start(ipv8_tasks)

        return ipv8

    async def create_default_communities(self, peer, ipv8, bootstrapper, mediator):
        if self.config.discovery_community.enabled:
            community = DiscoveryCommunity(peer, ipv8.endpoint, ipv8.network, max_peers=100)
            ipv8.strategies.append((RandomChurn(community), INFINITE))
            ipv8.strategies.append((PeriodicSimilarity(community), INFINITE))
            ipv8.strategies.append((RandomWalk(community), INFINITE))

            if bootstrapper:
                community.bootstrappers.append(bootstrapper)

            ipv8.overlays.append(community)

        if self.config.dht.enabled:
            community = DHTDiscoveryCommunity(peer, ipv8.endpoint, ipv8.network, max_peers=60)
            ipv8.strategies.append((RandomChurn(community), INFINITE))
            ipv8.strategies.append((PeriodicSimilarity(community), INFINITE))
            ipv8.strategies.append((RandomWalk(community), 20))

            if bootstrapper:
                community.bootstrappers.append(bootstrapper)

            ipv8.overlays.append(community)
            mediator.optional['dht_community'] = community

    async def create_bootstrapper(self, bootstrap_override):
        if not bootstrap_override:
            return

        address, port = self.config.bootstrap_override.split(':')
        return DispersyBootstrapper(ip_addresses=[(address, int(port))], dns_addresses=[])
