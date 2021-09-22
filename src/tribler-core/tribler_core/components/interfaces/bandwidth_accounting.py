from unittest.mock import Mock

from ipv8_service import IPv8

from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity


class BandwidthAccountingComponent(Component):
    community: BandwidthAccountingCommunity
    enable_in_gui_test_mode = True
    _ipv8: IPv8

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return config.ipv8.enabled

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.bandwidth_accounting import BandwidthAccountingComponentImp
            return BandwidthAccountingComponentImp(cls)
        return BandwidthAccountingComponentMock(cls)

@testcomponent
class BandwidthAccountingComponentMock(BandwidthAccountingComponent):
    community = Mock()
