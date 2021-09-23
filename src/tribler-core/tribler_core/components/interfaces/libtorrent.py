from typing import List
from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.libtorrent.download_manager import DownloadManager


class LibtorrentComponent(Component):
    enable_in_gui_test_mode = True

    download_manager: DownloadManager
    endpoints: List[str]


@testcomponent
class LibtorrentComponentMock(LibtorrentComponent):
    download_manager = Mock()
    endpoints = []
