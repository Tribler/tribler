from ipv8.loader import overlay, set_in_session, walk_strategy
from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_core.modules.bandwidth_accounting.community import (
    BandwidthAccountingCommunity,
    BandwidthAccountingTestnetCommunity,
)
from tribler_core.modules.community_loader import TestnetMixIn, TriblerCommunityLauncher


@overlay(BandwidthAccountingCommunity)
@walk_strategy(RandomWalk)
@set_in_session('bandwidth_community')
class BandwidthCommunityLauncher(TriblerCommunityLauncher):
    def get_kwargs(self, session):
        return {
            'settings': session.config.bandwidth_accounting,
            'database_path': session.config.state_dir / "sqlite" / "bandwidth.db",
        }


@overlay(BandwidthAccountingTestnetCommunity)
class BandwidthTestnetCommunityLauncher(TestnetMixIn, BandwidthCommunityLauncher):
    pass
