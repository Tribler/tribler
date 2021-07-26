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

from tribler_core.components.interfaces.ipv8 import (
    DHTDiscoveryCommunityComponent,
    DiscoveryCommunityComponent,
    Ipv8BootstrapperComponent,
    Ipv8Component,
    Ipv8PeerComponent,
)
from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.restapi.rest_manager import RESTManager
from tribler_core.utilities.utilities import froze_it

INFINITE = -1


@froze_it
class Ipv8ComponentImp(Ipv8Component):
    task_manager: TaskManager
    rest_manager: RESTManager

    async def run(self):
        config = self.session.config

        rest_component = await self.use(RESTComponent)
        rest_manager = self.rest_manager = rest_component.rest_manager
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
        self.ipv8 = ipv8
        # self.provide(mediator, ipv8)

        if config.ipv8.statistics and not config.core_test_mode:
            # Enable gathering IPv8 statistics
            for overlay in ipv8.overlays:
                ipv8.endpoint.enable_community_statistics(overlay.get_prefix(), True)

        if config.ipv8.walk_scaling_enabled and not config.core_test_mode:
            from tribler_core.modules.ipv8_health_monitor import IPv8Monitor
            IPv8Monitor(ipv8,
                        config.ipv8.walk_interval,
                        config.ipv8.walk_scaling_upper_limit).start(self.task_manager)

        rest_manager.get_endpoint('statistics').ipv8 = ipv8

    async def shutdown(self):
        self.rest_manager.get_endpoint('statistics').ipv8 = None
        await self.unuse(RESTComponent)

        await self.unused.wait()
        self.session.notifier.notify_shutdown_state("Shutting down IPv8...")
        await self.task_manager.shutdown_task_manager()
        await self.ipv8.stop(stop_loop=False)


class Ipv8PeerComponentImp(Ipv8PeerComponent):
    async def run(self):
        self.peer = Peer(self.session.trustchain_keypair)
        # self.provide(mediator, peer)


class Ipv8BootstrapperComponentImp(Ipv8BootstrapperComponent):
    async def run(self):
        args = DISPERSY_BOOTSTRAPPER['init']
        if bootstrap_override := self.session.config.ipv8.bootstrap_override:
            address, port = bootstrap_override.split(':')
            args = {'ip_addresses': [(address, int(port))], 'dns_addresses': []}

        self.bootstrapper = DispersyBootstrapper(**args)
        # self.provide(mediator, bootstrapper)


class DHTDiscoveryCommunityComponentImp(DHTDiscoveryCommunityComponent):
    async def run(self):
        ipv8 = (await self.use(Ipv8Component)).ipv8
        peer = (await self.use(Ipv8PeerComponent)).peer
        bootstrapper = (await self.use(Ipv8BootstrapperComponent)).bootstrapper

        community = DHTDiscoveryCommunity(peer, ipv8.endpoint, ipv8.network, max_peers=60)
        ipv8.strategies.append((PingChurn(community), INFINITE))
        ipv8.strategies.append((RandomWalk(community), 20))

        community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)
        # self.provide(mediator, community)


class DiscoveryCommunityComponentImp(DiscoveryCommunityComponent):
    async def run(self):
        ipv8 = (await self.use(Ipv8Component)).ipv8
        peer = (await self.use(Ipv8PeerComponent)).peer
        bootstrapper = (await self.use(Ipv8BootstrapperComponent)).bootstrapper

        community = DiscoveryCommunity(peer, ipv8.endpoint, ipv8.network, max_peers=100)
        ipv8.strategies.append((RandomChurn(community), INFINITE))
        ipv8.strategies.append((PeriodicSimilarity(community), INFINITE))
        ipv8.strategies.append((RandomWalk(community), INFINITE))

        community.bootstrappers.append(bootstrapper)

        ipv8.overlays.append(community)
        # self.provide(mediator, community)
