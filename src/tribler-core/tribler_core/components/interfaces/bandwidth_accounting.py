from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity


class BandwidthAccountingComponent(Component):
    community: BandwidthAccountingCommunity

    @classmethod
    def should_be_enabled(cls, config):
        return config.ipv8.enabled

    @classmethod
    def make_implementation(cls, config, enable):
        if enable:
            from tribler_core.components.implementation.bandwidth_accounting import BandwidthAccountingComponentImp
            return BandwidthAccountingComponentImp()
        return BandwidthAccountingComponentMock()

@testcomponent
class BandwidthAccountingComponentMock(BandwidthAccountingComponent):
    community = Mock()
