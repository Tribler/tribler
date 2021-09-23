from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.upgrade.upgrade import TriblerUpgrader


class UpgradeComponent(Component):
    upgrader: TriblerUpgrader


@testcomponent
class UpgradeComponentMock(UpgradeComponent):
    upgrader = Mock()
