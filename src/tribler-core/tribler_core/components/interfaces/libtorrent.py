from typing import List
from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.libtorrent.download_manager import DownloadManager


class LibtorrentComponent(Component):
    core = True

    download_manager: DownloadManager
    endpoints: List[str]

    @classmethod
    def should_be_enabled(cls, config):
        return config.libtorrent.enabled

    @classmethod
    def make_implementation(cls, config, enable):
        if enable:
            from tribler_core.components.implementation.libtorrent import LibtorrentComponentImp
            return LibtorrentComponentImp()
        return LibtorrentComponentMock()


@testcomponent
class LibtorrentComponentMock(LibtorrentComponent):
    download_manager = Mock
    endpoints = []
