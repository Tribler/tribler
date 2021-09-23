from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker


class TorrentCheckerComponent(Component):
    torrent_checker: TorrentChecker


@testcomponent
class TorrentCheckerComponentMock(TorrentCheckerComponent):
    torrent_checker = Mock()
