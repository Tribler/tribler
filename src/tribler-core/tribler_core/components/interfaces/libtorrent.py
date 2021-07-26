from typing import List

from tribler_core.components.base import Component
from tribler_core.modules.libtorrent.download_manager import DownloadManager


class LibtorrentComponent(Component):
    download_manager: DownloadManager
    endpoints: List[str]
