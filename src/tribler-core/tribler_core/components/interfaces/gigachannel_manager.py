from tribler_core.components.base import Component
from tribler_core.modules.metadata_store.manager.gigachannel_manager import GigaChannelManager


class GigachannelManagerComponent(Component):
    gigachannel_manager: GigaChannelManager
