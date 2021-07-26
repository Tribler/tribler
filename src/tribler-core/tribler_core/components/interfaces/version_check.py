from tribler_core.components.base import Component
from tribler_core.modules.version_check.versioncheck_manager import VersionCheckManager


class VersionCheckComponent(Component):
    version_check_manager: VersionCheckManager
