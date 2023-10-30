from __future__ import annotations

import json
import logging
from time import time
from typing import Callable, Dict, List, Optional, TYPE_CHECKING, Union
from urllib.parse import urlencode

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtNetwork import QNetworkReply, QNetworkRequest

from tribler.gui.utilities import connect

REQUEST_ID = '_request_id'

if TYPE_CHECKING:
    from tribler.gui.network.request_manager import RequestManager

DATA_TYPE = Optional[Union[bytes, str, Dict, List]]


def make_reply_errors_map() -> Dict[int, str]:
    errors_map = {}
    for attr_name in dir(QNetworkReply):
        if attr_name[0].isupper() and attr_name.endswith('Error'):  # SomeError, but not the `setError` method
            error_code = getattr(QNetworkReply, attr_name)
            if isinstance(error_code, int):  # an additional safety check, just for case
                errors_map[error_code] = attr_name
    return errors_map


reply_errors = make_reply_errors_map()


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

    def __init__(
            self,
            endpoint: str,
            on_success: Callable = lambda _: None,
            url_params: Optional[Dict] = None,
            data: DATA_TYPE = None,
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
        self.data = data
        if isinstance(data, (Dict, List)):
            raw_data = json.dumps(data).encode('utf8')
        elif isinstance(data, str):
            raw_data = data.encode('utf8')
        else:
            raw_data = data
        self.raw_data: Optional[bytes] = raw_data

        connect(self.on_finished_signal, on_success)

        self.reply: Optional[QNetworkReply] = None  # to hold the associated QNetworkReply object
        self.manager: Optional[RequestManager] = None
        self.url: str = ''

        self.time = time()
        self.status_code = 0
        self.status_text = "unknown"
        self.cancellable = True
        self.id = 0
        self.caller = ''

    def set_manager(self, manager: RequestManager):
        self.manager = manager
        self._set_url(manager.get_base_url())

    def _set_url(self, base_url: str):
        self.url = base_url + self.endpoint
        if self.url_params:
            # Encode True and False as "1" and "0" and not as "True" and "False"
            url_params = {key: int(value) if isinstance(value, bool) else value
                          for key, value in self.url_params.items()}
            self.url += '?' + urlencode(url_params, doseq=True)

    def on_finished(self):
        if not self.reply or not self.manager:
            return

        self.logger.info(f'Finished: {self}')
        try:
            # If HTTP status code is available on the reply, we process that first.
            # This is because self.reply.error() is not always QNetworkReply.NoError even if there is HTTP response.
            # One example case is for HTTP Status Code 413 (HTTPRequestEntityTooLarge) for which QNetworkReply
            # error code is QNetworkReply.UnknownContentError
            if status_code := self.reply.attribute(QNetworkRequest.HttpStatusCodeAttribute):
                self._handle_http_response(status_code)
                return

            # Process any other NetworkReply Error response.
            error_code = self.reply.error()
            self._handle_network_reply_errors(error_code)

        except Exception as e:  # pylint: disable=broad-except
            self.logger.exception(e)
            self.cancel()
        finally:
            self._delete()

    def _handle_network_reply_errors(self, error_code):
        error_name = reply_errors.get(error_code, '<unknown error>')
        self.status_code = -error_code  # QNetworkReply errors are set negative to distinguish from HTTP response codes.
        self.status_text = f'{self.status_code}: {error_code}'
        self.logger.warning(f'Request {self} finished with error: {self.status_code} ({error_name})')

    def _handle_http_response(self, status_code):
        self.logger.debug(f'Update {self}: {status_code}')
        self.status_code = status_code
        self.status_text = str(status_code)

        data = bytes(self.reply.readAll())
        if self.raw_response:
            self.logger.debug('Create a raw response')
            header = self.reply.header(QNetworkRequest.ContentTypeHeader)
            self.on_finished_signal.emit((data, header))
            return

        if not data:
            self.logger.error(f'No data received in the reply for {self}')
            return

        self.logger.debug('Create a json response')
        result = json.loads(data)
        if isinstance(result, dict):
            result[REQUEST_ID] = self.id
        is_error = 'error' in result
        if is_error and self.capture_errors:
            text = self.manager.show_error(self, result)
            raise Warning(text)

        self.on_finished_signal.emit(result)

    def cancel(self):
        """
        Cancel the request by aborting the reply handle
        """
        try:
            self.logger.warning(f'Request was canceled: {self}')
            if self.reply:
                self.reply.abort()
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

        if self.reply:
            self.reply.deleteLater()
            self.reply = None

    def __str__(self):
        result = f'{self.method} {self.url}'
        if self.caller:
            result += f'\nCaller: {self.caller}'
        return result
