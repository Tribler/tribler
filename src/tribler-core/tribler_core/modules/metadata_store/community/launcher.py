from ipv8.loader import overlay, precondition, set_in_session, walk_strategy
from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_core.modules.ipv8_module_catalog import INFINITE, IPv8CommunityLauncher, TestnetMixIn
from tribler_core.modules.metadata_store.community.gigachannel_community import (
    GigaChannelCommunity,
    GigaChannelTestnetCommunity,
)
from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers


@overlay(GigaChannelCommunity)
@precondition('session.config.chant.enabled')
@precondition('not session.chant_testnet()')
@set_in_session('gigachannel_community')
# GigaChannelCommunity remote search feature works better with higher amount of connected peers
@walk_strategy(RandomWalk, target_peers=30)
@walk_strategy(RemovePeers, target_peers=INFINITE)
class GigaChannelCommunityLauncher(IPv8CommunityLauncher):
    def get_kwargs(self, session):
        return {
            'settings': session.config.chant,
            'rqc_settings': session.config.remote_query_community,
            'metadata_store': session.mds,
            'notifier': session.notifier,
            'max_peers': 50,
        }


@precondition('session.config.chant.enabled')
@precondition('session.chant_testnet()')
@overlay(GigaChannelTestnetCommunity)
class GigaChannelTestnetCommunityLauncher(TestnetMixIn, GigaChannelCommunityLauncher):
    pass
