from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.watch_folder.watch_folder import WatchFolder


class WatchFolderComponent(Component):
    watch_folder: WatchFolder


@testcomponent
class WatchFolderComponentMock(WatchFolderComponent):
    watch_folder = Mock()
