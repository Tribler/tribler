from __future__ import annotations

import json
import logging
from time import time
from typing import Dict, TYPE_CHECKING
from urllib.parse import quote_plus

from PyQt5.QtCore import QBuffer, QIODevice, QUrl
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

from tribler.core.utilities.limited_ordered_dict import LimitedOrderedDict
from tribler.gui.defs import BUTTON_TYPE_NORMAL, DEFAULT_API_HOST, DEFAULT_API_PORT, DEFAULT_API_PROTOCOL
from tribler.gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler.gui.network.request.shutdown_request import ShutdownRequest
from tribler.gui.utilities import connect

if TYPE_CHECKING:
    from tribler.gui.network.request.request import Request


class RequestManager(QNetworkAccessManager):
    """
    This class is responsible for all the requests made to the Tribler REST API.
    All requests are asynchronous so the caller object should keep track of response (QNetworkReply) object. A finished
    pyqt signal is fired when the response data is ready.
    """

    window = None

    def __init__(self, limit: int = 50, timeout_interval: int = 15):
        QNetworkAccessManager.__init__(self)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.active_requests = {}
        self.performed_requests: Dict[Request, int] = LimitedOrderedDict(limit=200)

        self.protocol = DEFAULT_API_PROTOCOL
        self.host = DEFAULT_API_HOST
        self.port = DEFAULT_API_PORT
        self.key = b""
        self.limit = limit
        self.timeout_interval = timeout_interval

    def add(self, request: Request):
        if len(self.active_requests) > self.limit:
            self._drop_timed_out_requests()

        self.active_requests[request] = request
        self.performed_requests[request] = 0
        request.manager = self
        request.url = self._get_base_url() + request.endpoint
        request.url += f'?{self._urlencode(request.url_params)}' if request.url_params else ''
        self.logger.info(f'Request: {request}')

        qt_request = QNetworkRequest(QUrl(request.url))
        qt_request.setPriority(request.priority)
        qt_request.setHeader(QNetworkRequest.ContentTypeHeader, 'application/x-www-form-urlencoded')
        qt_request.setRawHeader(b'X-Api-Key', self.key.encode('ascii'))

        buf = QBuffer()
        if request.data:
            buf.setData(request.data)
        buf.open(QIODevice.ReadOnly)

        # A workaround for Qt5 bug. See https://github.com/Tribler/tribler/issues/7018
        self.setNetworkAccessible(QNetworkAccessManager.Accessible)

        request.reply = self.sendCustomRequest(qt_request, request.method.encode("utf8"), buf)
        buf.setParent(request.reply)

        connect(request.reply.finished, request._on_finished)  # pylint: disable=protected-access

    def remove(self, request: Request):
        self.active_requests.pop(request, None)

        if request.reply:
            request.reply.deleteLater()
            request.reply = None

    def update(self, request: Request, status: int):
        self.logger.debug(f'Update {request}: {status}')

        self.performed_requests[request] = status

    def show_error(self, request: Request, data: Dict) -> str:
        text = self.get_message_from_error(data)
        if self.window.core_manager.shutting_down:
            return ''

        text = f'An error occurred during the request "{request}":\n\n{text}'
        error_dialog = ConfirmationDialog(self.window, "Request error", text, [('CLOSE', BUTTON_TYPE_NORMAL)])

        def on_close(_):
            error_dialog.close_dialog()

        connect(error_dialog.button_clicked, on_close)
        error_dialog.show()
        return text

    def _get_base_url(self) -> str:
        return f'{self.protocol}://{self.host}:{self.port}/'

    @staticmethod
    def get_message_from_error(d: Dict) -> str:
        error = d.get('error', {})
        if isinstance(error, str):
            return error

        if message := error.get('message'):
            return message

        return json.dumps(d)

    def clear(self, skip_shutdown_request=True):
        for req in list(self.active_requests.values()):
            if skip_shutdown_request and isinstance(req, ShutdownRequest):
                continue
            req.cancel_request()

    def _drop_timed_out_requests(self):
        for req in list(self.active_requests.values()):
            is_time_to_cancel = time() - req.time > self.timeout_interval
            if is_time_to_cancel:
                req.cancel()

    def _urlencode(self, data):
        # Convert all keys and values in the data to utf-8 unicode strings
        utf8_items = []
        for key, value in data.items():
            if isinstance(value, list):
                utf8_items.extend([self._urlencode_single(key, list_item) for list_item in value if value])
            else:
                utf8_items.append(self._urlencode_single(key, value))

        data = "&".join(utf8_items)
        return data

    @staticmethod
    def _urlencode_single(key, value):
        utf8_key = quote_plus(str(key).encode('utf-8'))
        # Convert bool values to ints
        if isinstance(value, bool):
            value = int(value)
        utf8_value = quote_plus(str(value).encode('utf-8'))
        return f"{utf8_key}={utf8_value}"


# Request manager singleton.
request_manager = RequestManager()
