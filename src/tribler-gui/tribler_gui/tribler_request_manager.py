import json
import logging
from collections import deque
from time import time
from urllib.parse import quote_plus

from PyQt5.QtCore import QBuffer, QIODevice, QObject, QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

from tribler_gui.defs import BUTTON_TYPE_NORMAL, DEFAULT_API_HOST, DEFAULT_API_PORT, DEFAULT_API_PROTOCOL
from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.utilities import connect


def tribler_urlencode(data):
    # Convert all keys and values in the data to utf-8 unicode strings
    utf8_items = []
    for key, value in data.items():
        if isinstance(value, list):
            utf8_items.extend([tribler_urlencode_single(key, list_item) for list_item in value if value])
        else:
            utf8_items.append(tribler_urlencode_single(key, value))

    data = "&".join(utf8_items)
    return data


def tribler_urlencode_single(key, value):
    utf8_key = quote_plus(str(key).encode('utf-8'))
    # Convert bool values to ints
    if isinstance(value, bool):
        value = int(value)
    utf8_value = quote_plus(str(value).encode('utf-8'))
    return f"{utf8_key}={utf8_value}"


performed_requests = deque(maxlen=200)


class TriblerRequestManager(QNetworkAccessManager):
    """
    This class is responsible for all the requests made to the Tribler REST API.
    All requests are asynchronous so the caller object should keep track of response (QNetworkReply) object. A finished
    pyqt signal is fired when the response data is ready.
    """

    window = None

    max_in_flight = 50
    request_timeout_interval = 15  # seconds

    def __init__(self):
        QNetworkAccessManager.__init__(self)
        self.requests_in_flight = {}
        self.protocol = DEFAULT_API_PROTOCOL
        self.host = DEFAULT_API_HOST
        self.port = DEFAULT_API_PORT
        self.key = b""

    def get_base_url(self):
        return "%s://%s:%d/" % (self.protocol, self.host, self.port)

    @staticmethod
    def get_message_from_error(error):
        return_error = None
        if isinstance(error['error'], str):
            return_error = error['error']
        elif 'message' in error['error']:
            return_error = error['error']['message']

        if not return_error:
            return json.dumps(error)  # Just print the json object
        return return_error

    def show_error(self, error_text):
        main_text = f"An error occurred during the request:\n\n{error_text}"
        error_dialog = ConfirmationDialog(
            TriblerRequestManager.window, "Request error", main_text, [('CLOSE', BUTTON_TYPE_NORMAL)]
        )

        def on_close(checked):
            error_dialog.close_dialog()

        connect(error_dialog.button_clicked, on_close)
        error_dialog.show()

    def clear(self):
        for req in list(self.requests_in_flight.values()):
            req.cancel_request()

    def evict_timed_out_requests(self):
        t = time()
        for req in list(self.requests_in_flight.values()):
            if t - req.time > self.request_timeout_interval:
                req.cancel_request()

    def add_request(self, request):
        if len(self.requests_in_flight) > self.max_in_flight:
            self.evict_timed_out_requests()

        self.requests_in_flight[id(request)] = request
        log = [request, 0]
        performed_requests.append(log)

        # qt_request is managed by QNetworkAccessManager, so we don't have to
        qt_request = QNetworkRequest(QUrl(request.url))
        qt_request.setPriority(request.priority)
        qt_request.setHeader(QNetworkRequest.ContentTypeHeader, request.content_type_header)
        qt_request.setRawHeader(b'X-Api-Key', self.key)

        buf = QBuffer()
        if request.raw_data:
            buf.setData(request.raw_data)
        buf.open(QIODevice.ReadOnly)

        request.reply = self.sendCustomRequest(qt_request, request.method.encode("utf8"), buf)
        buf.setParent(request.reply)

        connect(request.reply.finished, lambda: request.on_finished(request))


# Request manager singleton.
request_manager = TriblerRequestManager()


class TriblerNetworkRequest(QObject):
    # This signal is called if we receive some real reply from the request
    # and if the user defined a callback to call on the received data.
    # We implement the callback as a signal call and not as a direct callback
    # because we want the request object be deleted independent of what happens
    # during the callback call.
    received_json = pyqtSignal(object)
    request_finished = pyqtSignal(object, int)
    received_error = pyqtSignal(int)

    def __init__(
        self,
        endpoint,
        reply_callback,
        url_params=None,
        data=None,
        raw_data=None,
        method='GET',
        capture_core_errors=True,
        priority=QNetworkRequest.NormalPriority,
        on_cancel=lambda: None,
        decode_json_response=True,
        on_error_callback=None,
        include_header_in_response=None,
        content_type_header="application/x-www-form-urlencoded",
    ):
        QObject.__init__(self)

        # data and raw_data should never come together
        if data and raw_data:
            raise Exception

        if endpoint.startswith("http:") or endpoint.startswith("https:"):
            url = endpoint
        else:
            url = request_manager.get_base_url() + endpoint
        url += ("?" + tribler_urlencode(url_params)) if url_params else ""

        self.decode_json_response = decode_json_response
        self.time = time()
        self.url = url
        self.priority = priority
        self.on_cancel = on_cancel
        self.method = method
        self.capture_core_errors = capture_core_errors
        self.include_header_in_response = include_header_in_response
        self.content_type_header = content_type_header
        if data:
            raw_data = json.dumps(data)
        self.raw_data = raw_data if (issubclass(type(raw_data), bytes) or raw_data is None) else raw_data.encode('utf8')
        self.reply_callback = reply_callback
        if self.reply_callback:
            connect(self.received_json, self.reply_callback)

        self.on_error_callback = on_error_callback
        if on_error_callback is not None:
            connect(self.received_error, on_error_callback)
        self.reply = None  # to hold the associated QNetworkReply object

        # Pass the newly created object to the manager singleton, so the object can be dispatched immediately
        request_manager.add_request(self)

    def on_finished(self, request):
        status_code = self.reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)

        # Set the status code in the performed requests log
        for item in performed_requests:
            if item[0] == request:
                item[1] = status_code
                break

        try:
            if not self.reply.isOpen() or not status_code:
                self.received_error.emit(self.reply.error())
                return

            data = self.reply.readAll()
            if not self.decode_json_response:
                if self.include_header_in_response is not None:
                    header = self.reply.header(self.include_header_in_response)
                    self.received_json.emit((bytes(data), header))
                else:
                    self.received_json.emit(data)
                return
            json_result = json.loads(bytes(data))
            if (
                'error' in json_result
                and self.capture_core_errors
                and not TriblerRequestManager.window.core_manager.shutting_down
            ):
                # TODO: Report REST API errors to Sentry
                request_manager.show_error(TriblerRequestManager.get_message_from_error(json_result))
            else:
                self.received_json.emit(json_result)
        except ValueError:
            self.received_error.emit(self.reply.error())
            logging.error(f"No json object could be decoded from data: {data}")
        finally:
            self.destruct()  # the request object should be properly destroyed no matter what

    def destruct(self):
        """
        Call Qt deletion procedure for the object and its member objects
        and remove the object from the request_manager's list of requests in flight
        """
        if self.reply is not None:
            self.reply.deleteLater()
            self.reply = None
        try:
            request_manager.requests_in_flight.pop(id(self))
        except KeyError:
            pass

    def cancel_request(self):
        """
        Cancel the request by aborting the reply handle and calling on_cancel if available.
        """
        if self.reply:
            self.reply.abort()
        self.on_cancel()
        self.destruct()


class TriblerFileDownloadRequest(TriblerNetworkRequest):
    def __init__(self, endpoint, read_callback):
        TriblerNetworkRequest.__init__(
            self,
            endpoint,
            read_callback,
            method="GET",
            priority=QNetworkRequest.LowPriority,
            decode_json_response=False,
        )
