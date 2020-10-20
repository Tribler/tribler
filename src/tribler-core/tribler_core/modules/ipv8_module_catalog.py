import inspect
import sys

from ipv8.loader import CommunityLauncher, after, kwargs, overlay, precondition, set_in_session, walk_strategy
from ipv8.peer import Peer


class IPv8CommunityLauncher(CommunityLauncher):

    def get_my_peer(self, ipv8, session):
        return (Peer(session.trustchain_testnet_keypair) if session.config.get_trustchain_testnet()
                else Peer(session.trustchain_keypair))


class TestnetMixIn:

    def should_launch(self, session):
        return True


@overlay('ipv8.peerdiscovery.community', 'DiscoveryCommunity')
@precondition('session.config.get_discovery_community_enabled()')
@walk_strategy('ipv8.peerdiscovery.churn', 'RandomChurn', target_peers=-1)
@walk_strategy('ipv8.peerdiscovery.discovery', 'RandomWalk')
@walk_strategy('ipv8.peerdiscovery.community', 'PeriodicSimilarity', target_peers=-1)
class IPv8DiscoveryCommunityLauncher(IPv8CommunityLauncher):

    def finalize(self, ipv8, session, community):
        community.resolve_dns_bootstrap_addresses()
        return super()


@overlay('ipv8.attestation.trustchain.community', 'TrustChainCommunity')
@precondition('session.config.get_trustchain_enabled()')
@precondition('not session.config.get_trustchain_testnet()')
@kwargs(working_directory='session.config.get_state_dir()')
@walk_strategy('ipv8.peerdiscovery.discovery', 'EdgeWalk')
@set_in_session('trustchain_community')
class TrustChainCommunityLauncher(IPv8CommunityLauncher):

    def finalize(self, ipv8, session, community):
        from anydex.wallet.tc_wallet import TrustchainWallet

        tc_wallet = TrustchainWallet(community)
        session.wallets[tc_wallet.get_identifier()] = tc_wallet

        return super()


@overlay('ipv8.attestation.trustchain.community', 'TrustChainTestnetCommunity')
@precondition('session.config.get_trustchain_enabled()')
@precondition('session.config.get_trustchain_testnet()')
class TrustChainTestnetCommunityLauncher(TestnetMixIn, TrustChainCommunityLauncher):
    pass


@overlay('ipv8.dht.discovery', 'DHTDiscoveryCommunity')
@precondition('session.config.get_dht_enabled()')
@walk_strategy('ipv8.dht.churn', 'PingChurn', target_peers=-1)
@walk_strategy('ipv8.peerdiscovery.discovery', 'RandomWalk')
@set_in_session('dht_community')
class DHTCommunityLauncher(IPv8CommunityLauncher):
    pass


@after('DHTDiscoveryCommunity', 'TrustChainCommunity', 'TrustChainTestnetCommunity')
@overlay('tribler_core.modules.tunnel.community.triblertunnel_community', 'TriblerTunnelCommunity')
@precondition('session.config.get_tunnel_community_enabled()')
@precondition('not session.config.get_tunnel_testnet()')
@kwargs(bandwidth_wallet='session.wallets["MB"]',
        competing_slots='session.config.get_tunnel_community_competing_slots()',
        ipv8='session.ipv8',
        random_slots='session.config.get_tunnel_community_random_slots()',
        tribler_session='session')
@walk_strategy('ipv8.peerdiscovery.discovery', 'RandomWalk')
@walk_strategy('tribler_core.modules.tunnel.community.discovery', 'GoldenRatioStrategy', target_peers=-1)
@set_in_session('tunnel_community')
class TriblerTunnelCommunityLauncher(IPv8CommunityLauncher):

    def get_kwargs(self, session):
        from ipv8.dht.provider import DHTCommunityProvider
        from ipv8.messaging.anonymization.community import TunnelSettings

        dht_provider = DHTCommunityProvider(session.dht_community, session.config.get_ipv8_port())
        settings = TunnelSettings()
        settings.min_circuits = 3
        settings.max_circuits = 10

        return {'dht_provider': dht_provider, 'settings': settings}


@overlay('tribler_core.modules.tunnel.community.triblertunnel_community', 'TriblerTunnelTestnetCommunity')
@precondition('session.config.get_tunnel_community_enabled()')
@precondition('session.config.get_tunnel_testnet()')
class TriblerTunnelTestnetCommunityLauncher(TestnetMixIn, TriblerTunnelCommunityLauncher):
    pass


@after('DHTDiscoveryCommunity', 'TrustChainCommunity', 'TrustChainTestnetCommunity')
@overlay('anydex.core.community', 'MarketCommunity')
@precondition('session.config.get_market_community_enabled()')
@precondition('not session.config.get_trustchain_testnet()')
@kwargs(trustchain='session.trustchain_community',
        dht='session.dht_community',
        wallets='session.wallets',
        working_directory='session.config.get_state_dir()',
        record_transactions='session.config.get_record_transactions()')
@walk_strategy('ipv8.peerdiscovery.discovery', 'RandomWalk')
@set_in_session('market_community')
class MarketCommunityLauncher(IPv8CommunityLauncher):
    pass


@overlay('anydex.core.community', 'MarketTestnetCommunity')
@precondition('session.config.get_market_community_enabled()')
@precondition('session.config.get_trustchain_testnet()')
class MarketTestnetCommunityLauncher(TestnetMixIn, MarketCommunityLauncher):
    pass


@overlay('tribler_core.modules.popularity.popularity_community', 'PopularityCommunity')
@precondition('session.config.get_popularity_community_enabled()')
@kwargs(metadata_store='session.mds', torrent_checker='session.torrent_checker',
        notifier='session.notifier')
@walk_strategy('ipv8.peerdiscovery.discovery', 'RandomWalk')
@set_in_session('popularity_community')
class PopularityCommunityLauncher(IPv8CommunityLauncher):
    pass


@after('TrustChainCommunity', 'TrustChainTestnetCommunity')
@overlay('tribler_core.modules.metadata_store.community.gigachannel_community', 'GigaChannelCommunity')
@precondition('session.config.get_chant_enabled()')
@precondition('not session.config.get_chant_testnet()')
@kwargs(metadata_store='session.mds', notifier='session.notifier')
@walk_strategy('ipv8.peerdiscovery.discovery', 'RandomWalk')
@walk_strategy('tribler_core.modules.metadata_store.community.sync_strategy', 'SyncChannels')
@set_in_session('gigachannel_community')
class GigaChannelCommunityLauncher(IPv8CommunityLauncher):
    pass


@overlay('tribler_core.modules.metadata_store.community.gigachannel_community', 'GigaChannelTestnetCommunity')
@precondition('session.config.get_chant_enabled()')
@precondition('session.config.get_chant_testnet()')
class GigaChannelTestnetCommunityLauncher(TestnetMixIn, GigaChannelCommunityLauncher):
    pass


@after('GigaChannelCommunity', 'GigaChannelTestnetCommunity')
@overlay('tribler_core.modules.metadata_store.community.remote_query_community', 'RemoteQueryCommunity')
@precondition('session.config.get_chant_enabled()')
@precondition('not session.config.get_chant_testnet()')
@kwargs(metadata_store='session.mds', notifier='session.notifier')
@walk_strategy('ipv8.peerdiscovery.discovery', 'RandomWalk', target_peers=50)
@set_in_session('remote_query_community')
class RemoteQueryCommunityLauncher(IPv8CommunityLauncher):
    pass


@overlay('tribler_core.modules.metadata_store.community.remote_query_community', 'RemoteQueryTestnetCommunity')
@precondition('session.config.get_chant_enabled()')
@precondition('session.config.get_chant_testnet()')
class RemoteQueryTestnetCommunityLauncher(TestnetMixIn, RemoteQueryCommunityLauncher):
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
    loader.set_launcher(TrustChainCommunityLauncher())
    loader.set_launcher(TrustChainTestnetCommunityLauncher())
    loader.set_launcher(DHTCommunityLauncher())
    loader.set_launcher(TriblerTunnelCommunityLauncher())
    loader.set_launcher(TriblerTunnelTestnetCommunityLauncher())
    loader.set_launcher(MarketCommunityLauncher())
    loader.set_launcher(MarketTestnetCommunityLauncher())
    loader.set_launcher(PopularityCommunityLauncher())
    loader.set_launcher(GigaChannelCommunityLauncher())
    loader.set_launcher(GigaChannelTestnetCommunityLauncher())
    loader.set_launcher(RemoteQueryCommunityLauncher())
    loader.set_launcher(RemoteQueryTestnetCommunityLauncher())
