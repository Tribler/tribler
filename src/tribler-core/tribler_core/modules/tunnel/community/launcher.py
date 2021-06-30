from ipv8.loader import after, overlay, set_in_session, walk_strategy
from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_core.modules.community_loader import INFINITE, TestnetMixIn, TriblerCommunityLauncher
from tribler_core.modules.tunnel.community.community import TriblerTunnelCommunity, TriblerTunnelTestnetCommunity
from tribler_core.modules.tunnel.community.discovery import GoldenRatioStrategy


# pylint: disable=import-outside-toplevel
@after('DHTCommunityLauncher', 'BandwidthCommunityLauncher', 'BandwidthTestnetCommunityLauncher')
@set_in_session('tunnel_community')
@overlay(TriblerTunnelCommunity)
@walk_strategy(RandomWalk)
@walk_strategy(GoldenRatioStrategy, target_peers=INFINITE)
class TriblerTunnelCommunityLauncher(TriblerCommunityLauncher):
    def get_kwargs(self, session):
        from ipv8.dht.provider import DHTCommunityProvider
        from ipv8.messaging.anonymization.community import TunnelSettings

        settings = TunnelSettings()
        settings.min_circuits = session.config.tunnel_community.min_circuits
        settings.max_circuits = session.config.tunnel_community.max_circuits

        return {
            'bandwidth_community': session.bandwidth_community,
            'competing_slots': session.config.tunnel_community.competing_slots,
            'ipv8': session.ipv8,
            'random_slots': session.config.tunnel_community.random_slots,
            'tribler_session': session,
            'dht_provider': DHTCommunityProvider(session.dht_community, session.config.ipv8.port),
            'settings': settings
        }


@overlay(TriblerTunnelTestnetCommunity)
class TriblerTunnelTestnetCommunityLauncher(TestnetMixIn, TriblerTunnelCommunityLauncher):
    pass
