from tribler_core.components.base import Component
from tribler_core.modules.popularity.community import PopularityCommunity


class PopularityComponent(Component):
    community: PopularityCommunity
