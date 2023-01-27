from __future__ import annotations

import json
import logging
from time import time
from typing import Callable, Dict, Optional, TYPE_CHECKING, Union

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtNetwork import QNetworkReply, QNetworkRequest

from tribler.gui.utilities import connect

if TYPE_CHECKING:
    from tribler.gui.network.request_manager import RequestManager


class Request(QObject):
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    PATCH = 'PATCH'
    DELETE = 'DELETE'

    # This signal is called if we receive some real reply from the request
    # and if the user defined a callback to call on the received data.
    # We implement the callback as a signal call and not as a direct callback
    # because we want the request object be deleted independent of what happens
    # during the callback call.
    on_finished_signal = pyqtSignal(object)
    on_cancel_signal = pyqtSignal()

    def __init__(
            self,
            endpoint: str,
            on_finish: Callable = lambda _: None,
            on_cancel: Callable = lambda: None,
            url_params: Optional[Dict] = None,
            data: Optional[Union[bytes, str, Dict]] = None,
            method: str = GET,
            capture_errors: bool = True,
            priority=QNetworkRequest.NormalPriority,
            raw_response: bool = False,
    ):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        self.endpoint = endpoint
        self.url_params = url_params

        self.priority = priority
        self.method = method
        self.capture_errors = capture_errors
        self.raw_response = raw_response
        self.data: Optional[bytes] = data
        self.raw_data = data
        if isinstance(self.data, Dict):
            self.data = json.dumps(data)
        if isinstance(self.data, str):
            self.data = self.data.encode('utf8')

        connect(self.on_finished_signal, on_finish)
        connect(self.on_cancel_signal, on_cancel)

        self.reply: Optional[QNetworkReply] = None  # to hold the associated QNetworkReply object
        self.manager: Optional[RequestManager] = None
        self.url: str = ''

        # Pass the newly created object to the manager singleton, so the object can be dispatched immediately
        self.time = time()
        self.status_code = 0

    def update_status(self, status_code: int):
        self.logger.debug(f'Update {self}: {status_code}')
        self.status_code = status_code

    def _on_finished(self):
        if not self.reply or not self.manager:
            return

        self.logger.info(f'Finished: {self}')
        try:
            if status_code := self.reply.attribute(QNetworkRequest.HttpStatusCodeAttribute):
                self.update_status(status_code)

            data = bytes(self.reply.readAll())
            if self.raw_response:
                self.logger.debug('Create a raw response')
                header = self.reply.header(QNetworkRequest.ContentTypeHeader)
                self.on_finished_signal.emit((data, header))
                return

            self.logger.debug('Create a json response')
            result = json.loads(data)
            is_error = 'error' in result
            if is_error and self.capture_errors:
                text = self.manager.show_error(self, result)
                raise Warning(text)

            self.on_finished_signal.emit(result)
        except Exception as e:  # pylint: disable=broad-except
            self.logger.exception(e)
            self.cancel()
        finally:
            self._delete()

    def cancel(self):
        """
        Cancel the request by aborting the reply handle and calling on_cancel if available.
        """
        try:
            self.logger.warning(f'Request was canceled: {self}')
            if self.reply:
                self.reply.abort()

            self.on_cancel_signal.emit()
        finally:
            self._delete()

    def _delete(self):
        """
        Call Qt deletion procedure for the object and its member objects
        and remove the object from the request_manager's list of requests in flight
        """
        self.logger.debug(f'Delete for {self}')

        if self.manager:
            self.manager.remove(self)
            self.manager = None

    def __str__(self):
        return f'{self.method} {self.url}'
