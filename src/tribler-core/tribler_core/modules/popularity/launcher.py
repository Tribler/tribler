from ipv8.loader import overlay, precondition, set_in_session, walk_strategy
from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_core.modules.ipv8_module_catalog import INFINITE, IPv8CommunityLauncher
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers
from tribler_core.modules.popularity.community import PopularityCommunity


@set_in_session('popularity_community')
@overlay(PopularityCommunity)
@walk_strategy(RandomWalk, target_peers=30)
@walk_strategy(RemovePeers, target_peers=INFINITE)
class PopularityCommunityLauncher(IPv8CommunityLauncher):
    def get_kwargs(self, session):
        return {
            'settings': session.config.popularity_community,
            'rqc_settings': session.config.remote_query_community,

            'metadata_store': session.mds,
            'torrent_checker': session.torrent_checker,
        }
