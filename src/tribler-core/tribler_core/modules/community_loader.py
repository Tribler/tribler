# pylint: disable=import-outside-toplevel
import inspect
import sys

from ipv8.loader import (
    CommunityLauncher,
    IPv8CommunityLoader,
    kwargs,
    overlay,
    precondition,
    set_in_session,
    walk_strategy,
)
from ipv8.peer import Peer

from tribler_core.config.tribler_config import TriblerConfig

INFINITE = -1
"""
The amount of target_peers for a walk_strategy definition to never stop.
"""


class TriblerCommunityLauncher(CommunityLauncher):
    def get_my_peer(self, ipv8, session):
        return (Peer(session.trustchain_testnet_keypair) if session.trustchain_testnet
                else Peer(session.trustchain_keypair))

    def get_bootstrappers(self, session):
        from ipv8.bootstrapping.dispersy.bootstrapper import DispersyBootstrapper
        from ipv8.configuration import DISPERSY_BOOTSTRAPPER
        bootstrap_override = session.config.ipv8.bootstrap_override
        if bootstrap_override:
            address, port = bootstrap_override.split(':')
            return [(DispersyBootstrapper, {"ip_addresses": [(address, int(port))],
                                            "dns_addresses": []})]
        return [(DispersyBootstrapper, DISPERSY_BOOTSTRAPPER['init'])]


class TestnetMixIn:
    def should_launch(self, _):
        return True


def discovery_community():
    from ipv8.peerdiscovery.community import DiscoveryCommunity
    return DiscoveryCommunity


def dht_discovery_community():
    from ipv8.dht.discovery import DHTDiscoveryCommunity
    return DHTDiscoveryCommunity


def random_churn():
    from ipv8.peerdiscovery.churn import RandomChurn
    return RandomChurn


def ping_churn():
    from ipv8.dht.churn import PingChurn
    return PingChurn


def random_walk():
    from ipv8.peerdiscovery.discovery import RandomWalk
    return RandomWalk


def periodic_similarity():
    from ipv8.peerdiscovery.community import PeriodicSimilarity
    return PeriodicSimilarity


@precondition('session.config.discovery_community.enabled')
@overlay(discovery_community)
@kwargs(max_peers='100')
@walk_strategy(random_churn, target_peers=INFINITE)
@walk_strategy(random_walk)
@walk_strategy(periodic_similarity, target_peers=INFINITE)
class IPv8DiscoveryCommunityLauncher(TriblerCommunityLauncher):
    pass


@precondition('session.config.dht.enabled')
@set_in_session('dht_community')
@overlay(dht_discovery_community)
@kwargs(max_peers='60')
@walk_strategy(ping_churn, target_peers=INFINITE)
@walk_strategy(random_walk)
class DHTCommunityLauncher(TriblerCommunityLauncher):
    pass


def create_default_loader(config: TriblerConfig, tunnel_testnet: bool = False,
                          bandwidth_testnet: bool = False, chant_testnet: bool = False):
    loader = IPv8CommunityLoader()

    loader.set_launcher(IPv8DiscoveryCommunityLauncher())
    loader.set_launcher(DHTCommunityLauncher())

    if bandwidth_testnet:
        from tribler_core.modules.bandwidth_accounting.launcher import BandwidthTestnetCommunityLauncher
        loader.set_launcher(BandwidthTestnetCommunityLauncher())
    else:
        from tribler_core.modules.bandwidth_accounting.launcher import BandwidthCommunityLauncher
        loader.set_launcher(BandwidthCommunityLauncher())

    if config.tunnel_community.enabled and not tunnel_testnet:
        from tribler_core.modules.tunnel.community.launcher import TriblerTunnelCommunityLauncher
        loader.set_launcher(TriblerTunnelCommunityLauncher())

    if config.tunnel_community.enabled and tunnel_testnet:
        from tribler_core.modules.tunnel.community.launcher import TriblerTunnelTestnetCommunityLauncher
        loader.set_launcher(TriblerTunnelTestnetCommunityLauncher())

    if config.popularity_community.enabled:
        from tribler_core.modules.popularity.launcher import PopularityCommunityLauncher
        loader.set_launcher(PopularityCommunityLauncher())

    if config.chant.enabled and not chant_testnet:
        from tribler_core.modules.metadata_store.community.launcher import GigaChannelCommunityLauncher
        loader.set_launcher(GigaChannelCommunityLauncher())

    if config.chant.enabled and chant_testnet:
        from tribler_core.modules.metadata_store.community.launcher import GigaChannelTestnetCommunityLauncher
        loader.set_launcher(GigaChannelTestnetCommunityLauncher())

    return loader
