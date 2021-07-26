from tribler_core.components.base import Component
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker


class TorrentCheckerComponent(Component):
    torrent_checker: TorrentChecker
