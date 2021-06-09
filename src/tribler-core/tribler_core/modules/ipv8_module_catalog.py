# pylint: disable=import-outside-toplevel
import inspect
import sys

from ipv8.loader import CommunityLauncher, after, kwargs, overlay, precondition, set_in_session, walk_strategy
from ipv8.peer import Peer

INFINITE = -1
"""
The amount of target_peers for a walk_strategy definition to never stop.
"""


class IPv8CommunityLauncher(CommunityLauncher):
    def get_my_peer(self, ipv8, session):
        return (Peer(session.trustchain_testnet_keypair) if session.config.get_trustchain_testnet()
                else Peer(session.trustchain_keypair))

    def get_bootstrappers(self, session):
        from ipv8.bootstrapping.dispersy.bootstrapper import DispersyBootstrapper
        from ipv8.configuration import DISPERSY_BOOTSTRAPPER
        if session.config.get_ipv8_bootstrap_override():
            return [(DispersyBootstrapper, {"ip_addresses": [session.config.get_ipv8_bootstrap_override()],
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


def tribler_tunnel_community():
    from tribler_core.modules.tunnel.community.triblertunnel_community import TriblerTunnelCommunity
    return TriblerTunnelCommunity


def bandwidth_accounting_community():
    from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity
    return BandwidthAccountingCommunity


def bandwidth_accounting_testnet_community():
    from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingTestnetCommunity
    return BandwidthAccountingTestnetCommunity


def popularity_community():
    from tribler_core.modules.popularity.popularity_community import PopularityCommunity
    return PopularityCommunity


def giga_channel_community():
    from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity
    return GigaChannelCommunity


def giga_channel_testnet_community():
    from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelTestnetCommunity
    return GigaChannelTestnetCommunity


def tribler_tunnel_testnet_community():
    from tribler_core.modules.tunnel.community.triblertunnel_community import TriblerTunnelTestnetCommunity
    return TriblerTunnelTestnetCommunity


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


def golden_ratio_strategy():
    from tribler_core.modules.tunnel.community.discovery import GoldenRatioStrategy
    return GoldenRatioStrategy


def remove_peers():
    from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
    return RemovePeers


@precondition('session.config.get_discovery_community_enabled()')
@overlay(discovery_community)
@kwargs(max_peers='100')
@walk_strategy(random_churn, target_peers=INFINITE)
@walk_strategy(random_walk)
@walk_strategy(periodic_similarity, target_peers=INFINITE)
class IPv8DiscoveryCommunityLauncher(IPv8CommunityLauncher):
    pass


@overlay(bandwidth_accounting_community)
@precondition('not session.config.get_bandwidth_testnet()')
@kwargs(database_path='session.config.state_dir / "sqlite" / "bandwidth.db"')
@walk_strategy(random_walk)
@set_in_session('bandwidth_community')
class BandwidthCommunityLauncher(IPv8CommunityLauncher):
    pass


@overlay(bandwidth_accounting_testnet_community)
@precondition('session.config.get_bandwidth_testnet()')
class BandwidthTestnetCommunityLauncher(TestnetMixIn, BandwidthCommunityLauncher):
    pass


@precondition('session.config.get_dht_enabled()')
@set_in_session('dht_community')
@overlay(dht_discovery_community)
@kwargs(max_peers='60')
@walk_strategy(ping_churn, target_peers=INFINITE)
@walk_strategy(random_walk)
class DHTCommunityLauncher(IPv8CommunityLauncher):
    pass


@after('DHTCommunityLauncher', 'BandwidthCommunityLauncher', 'BandwidthTestnetCommunityLauncher')
@precondition('session.config.get_tunnel_community_enabled()')
@precondition('not session.config.get_tunnel_testnet()')
@set_in_session('tunnel_community')
@overlay(tribler_tunnel_community)
@kwargs(bandwidth_community='session.bandwidth_community',
        competing_slots='session.config.get_tunnel_community_competing_slots()',
        ipv8='session.ipv8',
        random_slots='session.config.get_tunnel_community_random_slots()',
        tribler_session='session')
@walk_strategy(random_walk)
@walk_strategy(golden_ratio_strategy, target_peers=INFINITE)
class TriblerTunnelCommunityLauncher(IPv8CommunityLauncher):
    def get_kwargs(self, session):
        from ipv8.dht.provider import DHTCommunityProvider
        from ipv8.messaging.anonymization.community import TunnelSettings

        dht_provider = DHTCommunityProvider(session.dht_community, session.config.get_ipv8_port())
        settings = TunnelSettings()
        settings.min_circuits = 3
        settings.max_circuits = 10

        return {'dht_provider': dht_provider, 'settings': settings}


@precondition('session.config.get_tunnel_community_enabled()')
@precondition('session.config.get_tunnel_testnet()')
@overlay(tribler_tunnel_testnet_community)
class TriblerTunnelTestnetCommunityLauncher(TestnetMixIn, TriblerTunnelCommunityLauncher):
    pass


@precondition('session.config.get_popularity_community_enabled()')
@set_in_session('popularity_community')
@overlay(popularity_community)
@kwargs(metadata_store='session.mds', torrent_checker='session.torrent_checker')
@walk_strategy(random_walk, target_peers=30)
@walk_strategy(remove_peers, target_peers=INFINITE)
class PopularityCommunityLauncher(IPv8CommunityLauncher):
    pass


@overlay(giga_channel_community)
@precondition('session.config.get_chant_enabled()')
@precondition('not session.config.get_chant_testnet()')
@set_in_session('gigachannel_community')
@overlay(giga_channel_community)
@kwargs(metadata_store='session.mds', notifier='session.notifier', max_peers='50')
# GigaChannelCommunity remote search feature works better with higher amount of connected peers
@walk_strategy(random_walk, target_peers=30)
@walk_strategy(remove_peers, target_peers=INFINITE)
class GigaChannelCommunityLauncher(IPv8CommunityLauncher):
    pass


@precondition('session.config.get_chant_enabled()')
@precondition('session.config.get_chant_testnet()')
@overlay(giga_channel_testnet_community)
class GigaChannelTestnetCommunityLauncher(TestnetMixIn, GigaChannelCommunityLauncher):
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
    loader.set_launcher(BandwidthCommunityLauncher())
    loader.set_launcher(BandwidthTestnetCommunityLauncher())
    loader.set_launcher(DHTCommunityLauncher())
    loader.set_launcher(TriblerTunnelCommunityLauncher())
    loader.set_launcher(TriblerTunnelTestnetCommunityLauncher())
    loader.set_launcher(PopularityCommunityLauncher())
    loader.set_launcher(GigaChannelCommunityLauncher())
    loader.set_launcher(GigaChannelTestnetCommunityLauncher())
