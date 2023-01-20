from __future__ import annotations

from PyQt5.QtNetwork import QNetworkRequest

from tribler.gui.network.request.request import Request


class FileDownloadRequest(Request):
    def __init__(self, *args, **kwargs):
        super().__init__(
            priority=QNetworkRequest.LowPriority,
            raw_response=True,
            *args, **kwargs
        )
