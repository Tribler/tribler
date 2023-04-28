from __future__ import annotations

import json
import logging
from collections import deque
from time import time
from typing import Callable, Dict, Optional, Set

from PyQt5.QtCore import QBuffer, QIODevice, QUrl
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

from tribler.gui.defs import BUTTON_TYPE_NORMAL, DEFAULT_API_HOST, DEFAULT_API_PORT, DEFAULT_API_PROTOCOL
from tribler.gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler.gui.network.request import DATA_TYPE, Request
from tribler.gui.utilities import connect


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

        self.active_requests: Set[Request] = set()
        self.performed_requests: deque[Request] = deque(maxlen=200)

        self.protocol = DEFAULT_API_PROTOCOL
        self.host = DEFAULT_API_HOST
        self.port = DEFAULT_API_PORT
        self.key = ''
        self.limit = limit
        self.timeout_interval = timeout_interval
        self.last_request_id = 0

    def get(self,
            endpoint: str,
            on_success: Callable = lambda _: None,
            url_params: Optional[Dict] = None,
            data: DATA_TYPE = None,
            capture_errors: bool = True,
            priority: int = QNetworkRequest.NormalPriority,
            raw_response: bool = False) -> Request:

        request = Request(endpoint=endpoint, on_success=on_success, url_params=url_params, data=data,
                          capture_errors=capture_errors, priority=priority, raw_response=raw_response,
                          method=Request.GET)
        self.add(request)
        return request

    def post(self,
             endpoint: str,
             on_success: Callable = lambda _: None,
             url_params: Optional[Dict] = None,
             data: DATA_TYPE = None,
             capture_errors: bool = True,
             priority: int = QNetworkRequest.NormalPriority,
             raw_response: bool = False) -> Request:

        request = Request(endpoint=endpoint, on_success=on_success, url_params=url_params, data=data,
                          capture_errors=capture_errors, priority=priority, raw_response=raw_response,
                          method=Request.POST)
        self.add(request)
        return request

    def put(self,
            endpoint: str,
            on_success: Callable = lambda _: None,
            url_params: Optional[Dict] = None,
            data: DATA_TYPE = None,
            capture_errors: bool = True,
            priority: int = QNetworkRequest.NormalPriority,
            raw_response: bool = False) -> Request:

        request = Request(endpoint=endpoint, on_success=on_success, url_params=url_params, data=data,
                          capture_errors=capture_errors, priority=priority, raw_response=raw_response,
                          method=Request.PUT)
        self.add(request)
        return request

    def patch(self,
              endpoint: str,
              on_success: Callable = lambda _: None,
              url_params: Optional[Dict] = None,
              data: DATA_TYPE = None,
              capture_errors: bool = True,
              priority: int = QNetworkRequest.NormalPriority,
              raw_response: bool = False) -> Request:

        request = Request(endpoint=endpoint, on_success=on_success, url_params=url_params, data=data,
                          capture_errors=capture_errors, priority=priority, raw_response=raw_response,
                          method=Request.PATCH)
        self.add(request)
        return request

    def delete(self,
               endpoint: str,
               on_success: Callable = lambda _: None,
               url_params: Optional[Dict] = None,
               data: DATA_TYPE = None,
               capture_errors: bool = True,
               priority: int = QNetworkRequest.NormalPriority,
               raw_response: bool = False) -> Request:

        request = Request(endpoint=endpoint, on_success=on_success, url_params=url_params, data=data,
                          capture_errors=capture_errors, priority=priority, raw_response=raw_response,
                          method=Request.DELETE)
        self.add(request)
        return request

    def add(self, request: Request):
        # Set last request id
        self.last_request_id += 1
        request.id = self.last_request_id

        if len(self.active_requests) > self.limit:
            self._drop_timed_out_requests()

        self.active_requests.add(request)
        self.performed_requests.append(request)
        request.set_manager(self)
        self.logger.info(f'Request: {request}')

        qt_request = QNetworkRequest(QUrl(request.url))
        qt_request.setPriority(request.priority)
        qt_request.setHeader(QNetworkRequest.ContentTypeHeader, 'application/x-www-form-urlencoded')
        qt_request.setRawHeader(b'X-Api-Key', self.key.encode('ascii'))

        buf = QBuffer()
        if request.raw_data is not None:
            buf.setData(request.raw_data)
        buf.open(QIODevice.ReadOnly)

        # A workaround for Qt5 bug. See https://github.com/Tribler/tribler/issues/7018
        self.setNetworkAccessible(QNetworkAccessManager.Accessible)

        request.reply = self.sendCustomRequest(qt_request, request.method.encode("utf8"), buf)
        buf.setParent(request.reply)

        connect(request.reply.finished, request.on_finished)

    def remove(self, request: Request):
        self.active_requests.discard(request)

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

    def get_base_url(self) -> str:
        return f'{self.protocol}://{self.host}:{self.port}/'

    @staticmethod
    def get_message_from_error(d: Dict) -> str:
        error = d.get('error', {})
        if isinstance(error, str):
            return error

        if message := error.get('message'):
            return message

        return json.dumps(d)

    def clear(self):
        for request in list(self.active_requests):
            if request.cancellable:
                request.cancel()

    def _drop_timed_out_requests(self):
        for req in list(self.active_requests):
            is_time_to_cancel = time() - req.time > self.timeout_interval
            if is_time_to_cancel:
                req.cancel()


# Request manager singleton.
request_manager = RequestManager()
