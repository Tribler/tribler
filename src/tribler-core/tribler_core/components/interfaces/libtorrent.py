from typing import List
from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.libtorrent.download_manager import DownloadManager


class LibtorrentComponent(Component):
    enable_in_gui_test_mode = True

    download_manager: DownloadManager
    endpoints: List[str]

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return config.libtorrent.enabled

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.libtorrent import LibtorrentComponentImp
            return LibtorrentComponentImp(cls)
        return LibtorrentComponentMock(cls)


@testcomponent
class LibtorrentComponentMock(LibtorrentComponent):
    download_manager = Mock
    endpoints = []
