from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.watch_folder.watch_folder import WatchFolder


class WatchFolderComponent(Component):
    watch_folder: WatchFolder

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return config.watch_folder.enabled

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.watch_folder import WatchFolderComponentImp
            return WatchFolderComponentImp()
        return WatchFolderComponentMock()


@testcomponent
class WatchFolderComponentMock(WatchFolderComponent):
    watch_folder = Mock()
