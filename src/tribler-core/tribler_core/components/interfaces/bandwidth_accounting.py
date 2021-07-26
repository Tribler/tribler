from tribler_core.components.base import Component
from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity


class BandwidthAccountingComponent(Component):
    community: BandwidthAccountingCommunity
