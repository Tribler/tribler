from dataclasses import dataclass

from ipv8.peerdiscovery.discovery import RandomWalk

DEFAULT_TARGET_PEERS = 20
INFINITE_TARGET_PEERS = -1


@dataclass
class StrategyFactory:
    create_class: type = RandomWalk
    target_peers: int = 20


class CommunityDIMixin:
    """Mixin for Dependency Injection
    """

    def init_community_di_mixin(self, strategies=None):
        self.strategies = strategies

    def fill_mediator(self, mediator):
        ...
