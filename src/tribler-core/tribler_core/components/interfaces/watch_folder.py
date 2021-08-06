from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.watch_folder.watch_folder import WatchFolder


class WatchFolderComponent(Component):
    watch_folder: WatchFolder

    @classmethod
    def should_be_enabled(cls, config):
        return config.watch_folder.enabled

    @classmethod
    def make_implementation(cls, config, enable):
        if enable:
            from tribler_core.components.implementation.watch_folder import WatchFolderComponentImp
            return WatchFolderComponentImp()
        return WatchFolderComponentMock()


@testcomponent
class WatchFolderComponentMock(WatchFolderComponent):
    watch_folder = Mock()
