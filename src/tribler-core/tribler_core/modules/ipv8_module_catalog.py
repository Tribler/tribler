# pylint: disable=import-outside-toplevel
import inspect
import sys

from ipv8.loader import CommunityLauncher, kwargs, overlay, precondition, set_in_session, walk_strategy
from ipv8.peer import Peer

INFINITE = -1
"""
The amount of target_peers for a walk_strategy definition to never stop.
"""


class IPv8CommunityLauncher(CommunityLauncher):
    def get_my_peer(self, ipv8, session):
        return (Peer(session.trustchain_testnet_keypair) if session.trustchain_testnet()
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
    def should_launch(self, session):
        return True


# communities
def discovery_community():
    from ipv8.peerdiscovery.community import DiscoveryCommunity
    return DiscoveryCommunity


def dht_discovery_community():
    from ipv8.dht.discovery import DHTDiscoveryCommunity
    return DHTDiscoveryCommunity


# strategies
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
class IPv8DiscoveryCommunityLauncher(IPv8CommunityLauncher):
    pass


@precondition('session.config.dht.enabled')
@set_in_session('dht_community')
@overlay(dht_discovery_community)
@kwargs(max_peers='60')
@walk_strategy(ping_churn, target_peers=INFINITE)
@walk_strategy(random_walk)
class DHTCommunityLauncher(IPv8CommunityLauncher):
    pass


def get_hiddenimports():
    """
    Return the set of all hidden imports defined by all CommunityLaunchers in this file.
    """
    hiddenimports = set()

    for _, obj in inspect.getmembers(sys.modules[__name__]):
        hiddenimports.update(getattr(obj, "hiddenimports", set()))

    return hiddenimports


def register_default_launchers(loader):
    """
    Register the default CommunityLaunchers into the given CommunityLoader.
    If you define a new default CommunityLauncher, add it here.

    = Warning =
     Do not perform any state changes in this function. All imports and state changes should be performed within
     the CommunityLaunchers themselves to be properly scoped and lazy-loaded.
    """
    loader.set_launcher(IPv8DiscoveryCommunityLauncher())
    loader.set_launcher(DHTCommunityLauncher())

    from tribler_core.modules.bandwidth_accounting.launcher import BandwidthCommunityLauncher
    loader.set_launcher(BandwidthCommunityLauncher())

    from tribler_core.modules.bandwidth_accounting.launcher import BandwidthTestnetCommunityLauncher
    loader.set_launcher(BandwidthTestnetCommunityLauncher())

    from tribler_core.modules.tunnel.community.launcher import TriblerTunnelCommunityLauncher
    loader.set_launcher(TriblerTunnelCommunityLauncher())

    from tribler_core.modules.tunnel.community.launcher import TriblerTunnelTestnetCommunityLauncher
    loader.set_launcher(TriblerTunnelTestnetCommunityLauncher())

    from tribler_core.modules.popularity.launcher import PopularityCommunityLauncher
    loader.set_launcher(PopularityCommunityLauncher())

    from tribler_core.modules.metadata_store.community.launcher import GigaChannelCommunityLauncher
    loader.set_launcher(GigaChannelCommunityLauncher())

    from tribler_core.modules.metadata_store.community.launcher import GigaChannelTestnetCommunityLauncher
    loader.set_launcher(GigaChannelTestnetCommunityLauncher())
