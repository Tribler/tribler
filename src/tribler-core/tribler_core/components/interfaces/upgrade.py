from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.upgrade.upgrade import TriblerUpgrader


class UpgradeComponent(Component):
    upgrader: TriblerUpgrader

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return config.upgrader_enabled

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.upgrade import UpgradeComponentImp
            return UpgradeComponentImp(cls)
        return UpgradeComponentMock(cls)


@testcomponent
class UpgradeComponentMock(UpgradeComponent):
    upgrader = Mock()
