from tribler_core.components.base import Component
from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity


class GigaChannelComponent(Component):
    community: GigaChannelCommunity
