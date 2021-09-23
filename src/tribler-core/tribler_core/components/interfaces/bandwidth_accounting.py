from unittest.mock import Mock

from ipv8_service import IPv8
from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity


class BandwidthAccountingComponent(Component):
    community: BandwidthAccountingCommunity
    enable_in_gui_test_mode = True
    _ipv8: IPv8


@testcomponent
class BandwidthAccountingComponentMock(BandwidthAccountingComponent):
    community = Mock()
