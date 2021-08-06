from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.upgrade.upgrade import TriblerUpgrader


class UpgradeComponent(Component):
    upgrader: TriblerUpgrader

    @classmethod
    def should_be_enabled(cls, config):
        return config.upgrader_enabled

    @classmethod
    def make_implementation(cls, config, enable):
        if enable:
            from tribler_core.components.implementation.upgrade import UpgradeComponentImp
            return UpgradeComponentImp()
        return UpgradeComponentMock()


@testcomponent
class UpgradeComponentMock(UpgradeComponent):
    upgrader = Mock()
