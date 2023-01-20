from PyQt5.QtNetwork import QNetworkRequest

from tribler.gui.network.request.request import Request


class ShutdownRequest(Request):
    def __init__(self, *args, **kwargs):
        super().__init__("shutdown", *args, **kwargs, method="PUT", priority=QNetworkRequest.HighPriority)
