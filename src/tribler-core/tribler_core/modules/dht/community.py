from ipv8.dht.discovery import DHTDiscoveryCommunity
from ipv8.peerdiscovery.churn import RandomChurn
from ipv8.peerdiscovery.community import PeriodicSimilarity
from ipv8.peerdiscovery.discovery import RandomWalk

from tribler_core.modules.community_di_mixin import (
    CommunityDIMixin,
    DEFAULT_TARGET_PEERS,
    INFINITE_TARGET_PEERS,
    StrategyFactory,
)
from tribler_core.session import Mediator


class DHTDiscoveryStrategies(CommunityDIMixin, DHTDiscoveryCommunity):
    def __init__(self, *args, mediator=None, **kwargs):
        kwargs['max_peers'] = 60
        super().__init__(*args, **kwargs)

        self.init_community_di_mixin(strategies=[
            StrategyFactory(create_class=RandomChurn, target_peers=INFINITE_TARGET_PEERS),
            StrategyFactory(create_class=PeriodicSimilarity, target_peers=INFINITE_TARGET_PEERS),
            StrategyFactory(create_class=RandomWalk, target_peers=DEFAULT_TARGET_PEERS),
        ])

    def fill_mediator(self, mediator: Mediator):
        super().fill_mediator(mediator)

        mediator.dictionary['dht_community'] = self
