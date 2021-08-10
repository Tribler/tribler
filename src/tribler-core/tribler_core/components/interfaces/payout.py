from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.payout.payout_manager import PayoutManager


class PayoutComponent(Component):
    payout_manager: PayoutManager

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return config.ipv8.enabled

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.payout import PayoutComponentImp
            return PayoutComponentImp(cls)
        return PayoutComponentMock(cls)


@testcomponent
class PayoutComponentMock(PayoutComponent):
    payout_manager = Mock()
