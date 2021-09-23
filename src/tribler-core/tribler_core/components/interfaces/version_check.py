from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.version_check.versioncheck_manager import VersionCheckManager


class VersionCheckComponent(Component):
    version_check_manager: VersionCheckManager


@testcomponent
class VersionCheckComponentMock(VersionCheckComponent):
    version_check_manager = Mock()
