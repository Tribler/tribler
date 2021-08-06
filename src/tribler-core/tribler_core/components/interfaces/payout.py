from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.payout.payout_manager import PayoutManager


class PayoutComponent(Component):
    payout_manager: PayoutManager

    @classmethod
    def should_be_enabled(cls, config):
        return config.ipv8.enabled

    @classmethod
    def make_implementation(cls, config, enable):
        if enable:
            from tribler_core.components.implementation.payout import PayoutComponentImp
            return PayoutComponentImp()
        return PayoutComponentMock()


@testcomponent
class PayoutComponentMock(PayoutComponent):
    payout_manager = Mock()
