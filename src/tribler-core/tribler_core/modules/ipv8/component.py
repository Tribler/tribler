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
from tribler_core.awaitable_resources import Resource, MY_PEER, IPV8_BOOTSTRAPPER, DHT_DISCOVERY_COMMUNITY, \
    DISCOVERY_COMMUNITY, IPV8_SERVICE

from tribler_core.modules.component import Component
from tribler_core.utilities.utilities import froze_it

INFINITE = -1


@froze_it
class Ipv8Component(Component):
    provided_futures = (Resource.IPV8_SERVICE, Resource.DHT_DISCOVERY_COMMUNITY)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ipv8_tasks = None

    async def run(self, mediator):
        await super().run(mediator)
        self.ipv8_tasks = TaskManager()

        ipv8 = await self.create_ipv8(self.config.ipv8, self.ipv8_tasks, self.config.core_test_mode)
        mediator.awaitable_components[Resource.IPV8_SERVICE].assign(ipv8)

        if api_manager := await mediator.awaitable_components[Resource.REST_MANAGER].add_user(Resource.IPV8_SERVICE):
            api_manager.get_endpoint('statistics').ipv8 = ipv8
            # api_manager.get_endpoint('ipv8').initialize(ipv8)

        await self.create_default_communities(peer, ipv8, bootstrapper, mediator)

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


    async def shutdown(self, mediator):
        mediator.notifier.notify_shutdown_state("Shutting down IPv8...")

        await mediator.awaitable_components[Resource.IPV8_SERVICE].no_users
        await self.ipv8_tasks.shutdown_task_manager()
        await self.ipv8.stop(stop_loop=False)
        mediator.awaitable_components[Resource.RESTManager].release(Resource.IPV8_SERVICE)

        await super().shutdown(mediator)


class MyPeerComponent(Component):
    resource_label = MY_PEER

    async def run(self, mediator):
        await super().run(mediator)
        peer = Peer(mediator.trustchain_keypair)
        self.provide(mediator, peer)


class BandwidthAccountingCommunityComponent(Component):
    resource_label = IPV8_BOOTSTRAPPER

    async def run(self, mediator):
        await super().run(mediator)

        args = DISPERSY_BOOTSTRAPPER['init']
        if bootstrap_override := self.config.ipv8.bootstrap_override:
            address, port = bootstrap_override.split(':')
            args = {'ip_addresses': [(address, int(port))], 'dns_addresses': []}

        bootstrapper = DispersyBootstrapper(**args)
        self.provide(mediator, bootstrapper)

class DHTDiscoveryCommunityComponent(Component):
    resource_label = DHT_DISCOVERY_COMMUNITY

    async def run(self, mediator):
        await super().run(mediator)

        ipv8 = await self.use(mediator, IPV8_SERVICE)
        peer = await self.use(mediator, MY_PEER)

        community = DHTDiscoveryCommunity(peer, ipv8.endpoint, ipv8.network, max_peers=60)
        ipv8.strategies.append((PingChurn(community), INFINITE))
        ipv8.strategies.append((RandomWalk(community), 20))

        bootstrapper = await self.use(mediator, IPV8_BOOTSTRAPPER)
        community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)
        self.provide(mediator, community)

class DiscoveryCommunityComponent(Component):
    role = DISCOVERY_COMMUNITY

    async def run(self, mediator):
        await super().run(mediator)

        ipv8 = await self.use(mediator, IPV8_SERVICE)
        peer = await self.use(mediator, MY_PEER)

        community = DiscoveryCommunity(peer, ipv8.endpoint, ipv8.network, max_peers=100)
        ipv8.strategies.append((RandomChurn(community), INFINITE))
        ipv8.strategies.append((PeriodicSimilarity(community), INFINITE))
        ipv8.strategies.append((RandomWalk(community), INFINITE))

        bootstrapper = await self.use(mediator, IPV8_BOOTSTRAPPER)
        community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)
        self.provide(mediator, community)

