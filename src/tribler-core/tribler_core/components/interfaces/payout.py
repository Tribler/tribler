from tribler_core.components.base import Component
from tribler_core.modules.payout.payout_manager import PayoutManager


class PayoutComponent(Component):
    payout_manager: PayoutManager
