from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker


class TorrentCheckerComponent(Component):
    torrent_checker: TorrentChecker

    @classmethod
    def should_be_enabled(cls, config):
        return config.torrent_checking.enabled

    @classmethod
    def make_implementation(cls, config, enable):
        if enable:
            from tribler_core.components.implementation.torrent_checker import TorrentCheckerComponentImp
            return TorrentCheckerComponentImp()
        return TorrentCheckerComponentMock()


@testcomponent
class TorrentCheckerComponentMock(TorrentCheckerComponent):
    torrent_checker = Mock()
