from ipv8.bootstrapping.dispersy.bootstrapper import DispersyBootstrapper
from ipv8.configuration import ConfigBuilder, DISPERSY_BOOTSTRAPPER
from ipv8.dht.churn import PingChurn
from ipv8.dht.discovery import DHTDiscoveryCommunity
from ipv8.messaging.interfaces.dispatcher.endpoint import DispatcherEndpoint
from ipv8.peer import Peer
from ipv8.peerdiscovery.churn import RandomChurn
from ipv8.peerdiscovery.community import DiscoveryCommunity, PeriodicSimilarity
from ipv8.peerdiscovery.discovery import RandomWalk
from ipv8.taskmanager import TaskManager

from ipv8_service import IPv8
from tribler_core.awaitable_resources import MY_PEER, IPV8_BOOTSTRAPPER, DHT_DISCOVERY_COMMUNITY, \
    DISCOVERY_COMMUNITY, IPV8_SERVICE, REST_MANAGER

from tribler_core.modules.component import Component
from tribler_core.utilities.utilities import froze_it

INFINITE = -1


@froze_it
class Ipv8Component(Component):
    role = IPV8_SERVICE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ipv8_tasks = None
        self._rest_manager = None

    async def run(self, mediator):
        await super().run(mediator)
        config = mediator.config

        rest_manager = self._rest_manager = await self.use(mediator, REST_MANAGER)
        self._ipv8_tasks = TaskManager()

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

        if config.core_test_mode:
            endpoint = DispatcherEndpoint([])
        else:
            # IPv8 includes IPv6 support by default.
            # We only load IPv4 to not kill all Tribler overlays (currently, it would instantly crash all users).
            # If you want to test IPv6 in Tribler you can set ``endpoint = None`` here.
            endpoint = DispatcherEndpoint(["UDPIPv4"], UDPIPv4={'port': port,
                                                                'ip': address})
        ipv8 = IPv8(ipv8_config_builder.finalize(),
                    enable_statistics=config.ipv8.statistics and not config.core_test_mode,
                    endpoint_override=endpoint)
        await ipv8.start()
        self.provide(mediator, ipv8)

        if config.ipv8.statistics and not config.core_test_mode:
            # Enable gathering IPv8 statistics
            for overlay in ipv8.overlays:
                ipv8.endpoint.enable_community_statistics(overlay.get_prefix(), True)

        if config.ipv8.walk_scaling_enabled and not config.core_test_mode:
            from tribler_core.modules.ipv8_health_monitor import IPv8Monitor
            IPv8Monitor(ipv8,
                        config.ipv8.walk_interval,
                        config.ipv8.walk_scaling_upper_limit).start(self._ipv8_tasks)

        rest_manager.get_endpoint('statistics').ipv8 = ipv8

    async def shutdown(self, mediator):
        self._rest_manager.get_endpoint('statistics').ipv8 = None
        self.release_dependency(mediator, REST_MANAGER)

        await self.unused(mediator)
        mediator.notifier.notify_shutdown_state("Shutting down IPv8...")
        await self._ipv8_tasks.shutdown_task_manager()
        await self._provided_object.stop(stop_loop=False)

        await super().shutdown(mediator)


class MyPeerComponent(Component):
    role = MY_PEER

    async def run(self, mediator):
        await super().run(mediator)
        peer = Peer(mediator.trustchain_keypair)
        self.provide(mediator, peer)


class Ipv8BootstrapperComponent(Component):
    role = IPV8_BOOTSTRAPPER

    async def run(self, mediator):
        await super().run(mediator)

        args = DISPERSY_BOOTSTRAPPER['init']
        if bootstrap_override := mediator.config.ipv8.bootstrap_override:
            address, port = bootstrap_override.split(':')
            args = {'ip_addresses': [(address, int(port))], 'dns_addresses': []}

        bootstrapper = DispersyBootstrapper(**args)
        self.provide(mediator, bootstrapper)


class DHTDiscoveryCommunityComponent(Component):
    role = DHT_DISCOVERY_COMMUNITY

    async def run(self, mediator):
        await super().run(mediator)

        ipv8 = await self.use(mediator, IPV8_SERVICE)
        peer = await self.use(mediator, MY_PEER)
        bootstrapper = await self.use(mediator, IPV8_BOOTSTRAPPER)

        community = DHTDiscoveryCommunity(peer, ipv8.endpoint, ipv8.network, max_peers=60)
        ipv8.strategies.append((PingChurn(community), INFINITE))
        ipv8.strategies.append((RandomWalk(community), 20))

        community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)
        self.provide(mediator, community)


class DiscoveryCommunityComponent(Component):
    role = DISCOVERY_COMMUNITY

    async def run(self, mediator):
        await super().run(mediator)

        ipv8 = await self.use(mediator, IPV8_SERVICE)
        peer = await self.use(mediator, MY_PEER)
        bootstrapper = await self.use(mediator, IPV8_BOOTSTRAPPER)

        community = DiscoveryCommunity(peer, ipv8.endpoint, ipv8.network, max_peers=100)
        ipv8.strategies.append((RandomChurn(community), INFINITE))
        ipv8.strategies.append((PeriodicSimilarity(community), INFINITE))
        ipv8.strategies.append((RandomWalk(community), INFINITE))

        community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)
        self.provide(mediator, community)
