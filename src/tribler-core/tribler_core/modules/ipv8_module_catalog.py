from abc import ABC

from ipv8.loader import CommunityLauncher
from ipv8.peer import Peer
from ipv8.peerdiscovery.discovery import EdgeWalk, RandomWalk


# The lazy-loading of Community-specific files triggers Pylint, this is expected:
# pylint: disable=C0415


class IPv8CommunityLauncher(CommunityLauncher, ABC):

    def get_my_peer(self, ipv8, session):
        return (Peer(session.trustchain_testnet_keypair) if session.config.get_trustchain_testnet()
                else Peer(session.trustchain_keypair))


class IPv8DiscoveryCommunityLauncher(IPv8CommunityLauncher):

    def get_overlay_class(self):
        from ipv8.peerdiscovery.community import DiscoveryCommunity
        return DiscoveryCommunity

    def should_launch(self, session):
        return True

    def get_kwargs(self, session):
        return {}

    def get_walk_strategies(self):
        from ipv8.peerdiscovery.churn import RandomChurn
        from ipv8.peerdiscovery.community import PeriodicSimilarity
        return [(RandomChurn, {}, -1), (PeriodicSimilarity, {}, -1), (RandomWalk, {}, 20)]

    def finalize(self, ipv8, session, community):
        community.resolve_dns_bootstrap_addresses()
        return super()


class TrustChainCommunityLauncher(IPv8CommunityLauncher):

    def should_launch(self, session):
        return session.config.get_trustchain_enabled() and not session.config.get_trustchain_testnet()

    def get_overlay_class(self):
        from ipv8.attestation.trustchain.community import TrustChainCommunity
        return TrustChainCommunity

    def get_kwargs(self, session):
        return {'working_directory': session.config.get_state_dir()}

    def get_walk_strategies(self):
        return [(EdgeWalk, {}, 20)]

    def finalize(self, ipv8, session, community):
        session.trustchain_community = community

        from anydex.wallet.tc_wallet import TrustchainWallet

        tc_wallet = TrustchainWallet(community)
        session.wallets[tc_wallet.get_identifier()] = tc_wallet
        return super()


class TrustChainTestnetCommunityLauncher(TrustChainCommunityLauncher):

    def should_launch(self, session):
        return session.config.get_trustchain_enabled() and session.config.get_trustchain_testnet()

    def get_overlay_class(self):
        from ipv8.attestation.trustchain.community import TrustChainTestnetCommunity
        return TrustChainTestnetCommunity


class DHTCommunityLauncher(IPv8CommunityLauncher):

    def should_launch(self, session):
        return session.config.get_dht_enabled()

    def get_overlay_class(self):
        from ipv8.dht.discovery import DHTDiscoveryCommunity
        return DHTDiscoveryCommunity

    def get_kwargs(self, session):
        return {}

    def get_walk_strategies(self):
        from ipv8.dht.churn import PingChurn
        return [(RandomWalk, {}, 20), (PingChurn, {}, -1)]

    def finalize(self, ipv8, session, community):
        session.dht_community = community
        return super()


class TriblerTunnelCommunityLauncher(IPv8CommunityLauncher):

    def not_before(self):
        return ['DHTDiscoveryCommunity', 'TrustChainCommunity', 'TrustChainTestnetCommunity']

    def should_launch(self, session):
        return session.config.get_tunnel_community_enabled() and not session.config.get_tunnel_testnet()

    def get_overlay_class(self):
        from tribler_core.modules.tunnel.community.triblertunnel_community import TriblerTunnelCommunity
        return TriblerTunnelCommunity

    def get_kwargs(self, session):
        from ipv8.dht.provider import DHTCommunityProvider
        from ipv8.messaging.anonymization.community import TunnelSettings

        random_slots = session.config.get_tunnel_community_random_slots()
        competing_slots = session.config.get_tunnel_community_competing_slots()

        dht_provider = DHTCommunityProvider(session.dht_community, session.config.get_ipv8_port())
        settings = TunnelSettings()
        settings.min_circuits = 3
        settings.max_circuits = 10

        return {
            'tribler_session': session,
            'dht_provider': dht_provider,
            'ipv8': session.ipv8,
            'bandwidth_wallet': session.wallets["MB"],
            'random_slots': random_slots,
            'competing_slots': competing_slots,
            'settings': settings
        }

    def get_walk_strategies(self):
        from tribler_core.modules.tunnel.community.discovery import GoldenRatioStrategy
        return [(RandomWalk, {}, 20), (GoldenRatioStrategy, {}, -1)]

    def finalize(self, ipv8, session, community):
        session.tunnel_community = community
        return super()


class TriblerTunnelTestnetCommunityLauncher(TriblerTunnelCommunityLauncher):

    def should_launch(self, session):
        return session.config.get_tunnel_community_enabled() and session.config.get_tunnel_testnet()

    def get_overlay_class(self):
        from tribler_core.modules.tunnel.community.triblertunnel_community import TriblerTunnelTestnetCommunity
        return TriblerTunnelTestnetCommunity


class MarketCommunityLauncher(IPv8CommunityLauncher):

    def not_before(self):
        return ['DHTDiscoveryCommunity', 'TrustChainCommunity', 'TrustChainTestnetCommunity']

    def should_launch(self, session):
        return session.config.get_market_community_enabled() and not session.config.get_trustchain_testnet()

    def get_overlay_class(self):
        from anydex.core.community import MarketCommunity
        return MarketCommunity

    def get_kwargs(self, session):
        return {
            'trustchain': session.trustchain_community,
            'dht': session.dht_community,
            'wallets': session.wallets,
            'working_directory': session.config.get_state_dir(),
            'record_transactions': session.config.get_record_transactions()
        }

    def get_walk_strategies(self):
        return [(RandomWalk, {}, 20)]

    def finalize(self, ipv8, session, community):
        session.market_community = community
        return super()


class MarketTestnetCommunityLauncher(MarketCommunityLauncher):

    def should_launch(self, session):
        return session.config.get_market_community_enabled() and session.config.get_trustchain_testnet()

    def get_overlay_class(self):
        from anydex.core.community import MarketTestnetCommunity
        return MarketTestnetCommunity


class PopularityCommunityLauncher(IPv8CommunityLauncher):

    def should_launch(self, session):
        return session.config.get_popularity_community_enabled()

    def get_overlay_class(self):
        from tribler_core.modules.popularity.popularity_community import PopularityCommunity
        return PopularityCommunity

    def get_kwargs(self, session):
        return {'metadata_store': session.mds, 'torrent_checker': session.torrent_checker}

    def get_walk_strategies(self):
        return [(RandomWalk, {}, 20)]

    def finalize(self, ipv8, session, community):
        session.popularity_community = community
        return super()


class GigaChannelCommunityLauncher(IPv8CommunityLauncher):

    def not_before(self):
        return ['TrustChainCommunity', 'TrustChainTestnetCommunity']

    def should_launch(self, session):
        return session.config.get_chant_enabled() and not session.config.get_chant_testnet()

    def get_overlay_class(self):
        from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity
        return GigaChannelCommunity

    def get_args(self, session):
        return [session.mds]

    def get_kwargs(self, session):
        return {'notifier': session.notifier}

    def get_walk_strategies(self):
        from tribler_core.modules.metadata_store.community.sync_strategy import SyncChannels
        return [(RandomWalk, {}, 20), (SyncChannels, {}, 20)]

    def finalize(self, ipv8, session, community):
        session.gigachannel_community = community
        return super()


class GigaChannelTestnetCommunityLauncher(GigaChannelCommunityLauncher):

    def should_launch(self, session):
        return session.config.get_chant_enabled() and session.config.get_chant_testnet()

    def get_overlay_class(self):
        from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelTestnetCommunity
        return GigaChannelTestnetCommunity


class RemoteQueryCommunityLauncher(IPv8CommunityLauncher):

    def not_before(self):
        return ['GigaChannelCommunity', 'GigaChannelTestnetCommunity']

    def should_launch(self, session):
        return session.config.get_chant_enabled() and not session.config.get_chant_testnet()

    def get_overlay_class(self):
        from tribler_core.modules.metadata_store.community.remote_query_community import RemoteQueryCommunity
        return RemoteQueryCommunity

    def get_args(self, session):
        return [session.mds]

    def get_kwargs(self, session):
        return {'notifier': session.notifier}

    def get_walk_strategies(self):
        return [(RandomWalk, {}, 50)]

    def finalize(self, ipv8, session, community):
        session.remote_query_community = community
        return super()


class RemoteQueryTestnetCommunityLauncher(RemoteQueryCommunityLauncher):

    def should_launch(self, session):
        return session.config.get_chant_enabled() and session.config.get_chant_testnet()

    def get_overlay_class(self):
        from tribler_core.modules.metadata_store.community.remote_query_community import RemoteQueryTestnetCommunity
        return RemoteQueryTestnetCommunity


def register_default_launchers(loader):
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
