from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.version_check.versioncheck_manager import VersionCheckManager


class VersionCheckComponent(Component):
    version_check_manager: VersionCheckManager

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return config.general.version_checker_enabled

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.version_check import VersionCheckComponentImp
            return VersionCheckComponentImp()
        return VersionCheckComponentMock()


@testcomponent
class VersionCheckComponentMock(VersionCheckComponent):
    version_check_manager = Mock()
