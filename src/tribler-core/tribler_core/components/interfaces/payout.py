from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.payout.payout_manager import PayoutManager


class PayoutComponent(Component):
    payout_manager: PayoutManager


@testcomponent
class PayoutComponentMock(PayoutComponent):
    payout_manager = Mock()
