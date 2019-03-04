from __future__ import absolute_import

import logging
from collections import deque, namedtuple
from threading import RLock
from time import time
from urllib import quote_plus

from PyQt5.QtCore import QBuffer, QIODevice, QObject, QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

from six import string_types, text_type
from six.moves import xrange

import Tribler.Core.Utilities.json_util as json

from TriblerGUI.defs import BUTTON_TYPE_NORMAL, DEFAULT_API_HOST, DEFAULT_API_PORT, DEFAULT_API_PROTOCOL
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog


def tribler_urlencode(data):
    # Convert all values that are an array to uri-encoded values
    for key in data.keys():
        value = data[key]
        if isinstance(value, list):
            if value:
                data[key + "[]"] = "&".join(value)
            else:
                del data[key]

    # Convert all keys and values in the data to utf-8 unicode strings
    utf8_items = []
    for key, value in data.items():
        utf8_key = quote_plus(text_type(key).encode('utf-8'))
        # Convert bool values to ints
        if isinstance(value, bool):
            value = int(value)
        utf8_value = quote_plus(text_type(value).encode('utf-8'))
        utf8_items.append("%s=%s" % (utf8_key, utf8_value))

    data = "&".join(utf8_items)
    return data


class QueuePriorityEnum(object):
    """
    Enum for HTTP request priority.
    """

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


QueueItem = namedtuple('QueueItem', 'request_manager, callback, priority, insertion_time, performed')


class RequestQueue(object):
    """
    Queue and rate limit HTTP requests as to not overload the socket count.
    """

    def __init__(self, max_outstanding=50, timeout=15):
        """
        Create a RequestQueue object for rate-limiting HTTP requests.

        :param max_outstanding: the maximum number of requests which can be unanswered at any given time.
        :param timeout: the time after which a request is assumed to never receive a response.
        """
        self.max_outstanding = max_outstanding
        self.timeout = timeout

        self.critical_queue = []
        self.high_queue = []
        self.medium_queue = []
        self.low_queue = []

        self.lock = RLock()  # Don't allow asynchronous access to the queue

    def parse_queue(self):
        """
        Parse the queues and dispatch the request.
        """
        self.lock.acquire()

        current_time = time()
        self.critical_queue = [(request_manager, endpoint, read_callback, data, method, capture_errors, insertion_time)
                               for (request_manager, endpoint, read_callback, data, method, capture_errors,
                                    insertion_time) in self.critical_queue
                               if current_time - insertion_time < self.timeout or request_manager.cancel_request()]
        self.high_queue = [(request_manager, endpoint, read_callback, data, method, capture_errors, insertion_time)
                           for (request_manager, endpoint, read_callback, data, method, capture_errors,
                                insertion_time) in self.high_queue
                           if current_time - insertion_time < self.timeout or request_manager.cancel_request()]
        self.medium_queue = [(request_manager, endpoint, read_callback, data, method, capture_errors, insertion_time)
                             for (request_manager, endpoint, read_callback, data, method, capture_errors,
                                  insertion_time) in self.medium_queue
                             if current_time - insertion_time < self.timeout or request_manager.cancel_request()]
        self.low_queue = [(request_manager, endpoint, read_callback, data, method, capture_errors, insertion_time)
                          for (request_manager, endpoint, read_callback, data, method, capture_errors,
                               insertion_time) in self.low_queue
                          if current_time - insertion_time < self.timeout or request_manager.cancel_request()]

        queue_item = None
        if self.critical_queue:
            queue_item = self.critical_queue.pop(0)
        elif self.high_queue:
            queue_item = self.high_queue.pop(0)
        elif self.medium_queue:
            queue_item = self.medium_queue.pop(0)
        elif self.low_queue:
            queue_item = self.low_queue.pop(0)

        if queue_item:
            dispatcher.perform_request(*queue_item[:-2])

        self.lock.release()

    def enqueue(self, request_manager, method, endpoint, data, read_callback, capture_errors,
                priority=QueuePriorityEnum.HIGH):
        """
        Add a new request to the queue based on priority

        Priority order
         - CRITICAL
         - HIGH
         - MEDIUM
         - LOW

        :param request_manager: the TriblerRequestManager wishing to perform a request.
        :param method: request method.
        :param endpoint: request endpoint.
        :param data: request data.
        :param read_callback: callback to call if the request is processed.
        :param capture_errors: whether to display the errors or not.
        :param priority: the priority for this request.
        """
        self.lock.acquire()
        queue_item = (request_manager, endpoint, read_callback, data, method, capture_errors, time())
        if priority == QueuePriorityEnum.CRITICAL:
            self.critical_queue.append(queue_item)

        if priority == QueuePriorityEnum.HIGH:
            if len(self.high_queue) < self.max_outstanding:
                self.high_queue.append(queue_item)
            else:
                # Get the last item of the queue
                last_item = self.high_queue.pop(self.max_outstanding - 1)
                # Add the original queue_item to the front of the queue
                self.high_queue.insert(0, queue_item)
                # reduce the priority of last_item and try to put in medium queue
                priority = QueuePriorityEnum.MEDIUM
                queue_item = last_item
        if priority == QueuePriorityEnum.MEDIUM:
            if len(self.medium_queue) < self.max_outstanding:
                self.medium_queue.append(queue_item)
            else:
                # Get the last item of the queue
                last_item = self.medium_queue.pop(self.max_outstanding - 1)
                # Add the original queue_item to the front of the queue
                self.medium_queue.insert(0, queue_item)
                # reduce the priority of last_item and try to put in low queue
                priority = QueuePriorityEnum.LOW
                queue_item = last_item
        if priority == QueuePriorityEnum.LOW:
            if len(self.low_queue) < self.max_outstanding:
                self.low_queue.append(queue_item)
            else:
                # Remove the last item of the queue which will be dropped
                self.low_queue.pop(self.max_outstanding - 1)
                # Add the original queue_item to the front of the queue
                self.low_queue.insert(0, queue_item)

        self.lock.release()
        self.parse_queue()

    def clear(self):
        """
        Clear the queue.
        """
        self.lock.acquire()

        for request_manager, _, _, _, _, _, _ in self.critical_queue:
            request_manager.cancel_request()
        for request_manager, _, _, _, _, _, _ in self.high_queue:
            request_manager.cancel_request()
        for request_manager, _, _, _, _, _, _ in self.medium_queue:
            request_manager.cancel_request()
        for request_manager, _, _, _, _, _, _ in self.low_queue:
            request_manager.cancel_request()

        self.critical_queue = []
        self.high_queue = []
        self.medium_queue = []
        self.low_queue = []

        self.lock.release()


# The RequestQueue singleton for queueing requests
request_queue = RequestQueue()
# The request history and their status codes (stores the last 200 requests)
performed_requests = deque(maxlen=200)


class TriblerRequestDispatcher(object):

    def __init__(self, pool_size=5):
        self.pool_size = pool_size
        self.request_workers = []
        self.num_requests = 0

        self.default_protocol = None
        self.default_host = None
        self.default_port = None

    def update_worker_settings(self, protocol=None, host=None, port=None):
        self.default_protocol = protocol
        self.default_host = host
        self.default_port = port

    def perform_request(self, request_manager, endpoint, reply_callback, data, method):
        self.num_requests += 1
        worker_index = self.num_requests % self.pool_size

        num_worker = len(self.request_workers)
        if num_worker < self.pool_size:
            for _ in xrange(self.pool_size - num_worker):
                worker = TriblerRequestWorker()
                self.request_workers.append(worker)
                if self.default_protocol:
                    worker.update_protocol(self.default_protocol)
                if self.default_host:
                    worker.update_host(self.default_host)
                if self.default_port:
                    worker.update_port(self.default_port)

        network_reply = self.request_workers[worker_index].perform_request(endpoint, reply_callback, data, method)
        request_manager.set_reply_handle(network_reply)

    def download_file(self, request_manager, endpoint, reply_callback):
        self.perform_request(request_manager, endpoint, reply_callback, "", method="GET")


# The TriblerRequestDispatcher singleton for dipatching requests to appropriate request worker
dispatcher = TriblerRequestDispatcher(pool_size=10)


class TriblerRequestManager(QObject):
    """
    This class is responsible for all the requests made to the Tribler REST API.
    """
    window = None
    received_json = pyqtSignal(object, int)
    received_file = pyqtSignal(object)

    def __init__(self):
        QObject.__init__(self)
        self.reply = None
        self.status_code = -1
        self.on_cancel = lambda: None

    def set_reply_handle(self, reply):
        self.reply = reply

    def perform_request(self, endpoint, read_callback, url_params=None, data=None, raw_data="", method='GET',
                        capture_errors=True, priority=QueuePriorityEnum.CRITICAL, on_cancel=lambda: None):
        """
        Perform a HTTP request.
        :param endpoint: the endpoint to call (i.e. "statistics")
        :param read_callback: the callback to be called with result info when we have the data
        :param url_params: an optional dictionary with parameters that should be included in the URL
        :param data: optional POST data to be sent with the request
        :param raw_data: optional raw data to include in the request, will get priority over data if defined
        :param method: the HTTP verb (GET/POST/PUT/PATCH)
        :param capture_errors: whether errors should be handled by this class (defaults to True)
        :param priority: the priority of this request
        :param on_cancel: optional callback to invoke when the request has been cancelled
        """
        self.on_cancel = on_cancel

        if read_callback:
            self.received_json.connect(read_callback)

        url = endpoint + (("?" + tribler_urlencode(url_params)) if url_params else "")

        if data and not raw_data:
            data = tribler_urlencode(data)
        elif raw_data:
            data = raw_data.encode('utf-8')

        def reply_callback(reply, log):
            log[-1] = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            self.on_finished(reply, capture_errors)

        request_queue.enqueue(self, method, url, data, reply_callback, priority)

    @staticmethod
    def get_message_from_error(error):
        return_error = None
        if isinstance(error['error'], string_types):
            return_error = error['error']
        elif 'message' in error['error']:
            return_error = error['error']['message']

        if not return_error:
            return json.dumps(error)  # Just print the json object
        return return_error

    def show_error(self, error_text):
        main_text = "An error occurred during the request:\n\n%s" % error_text
        error_dialog = ConfirmationDialog(TriblerRequestManager.window, "Request error",
                                          main_text, [('CLOSE', BUTTON_TYPE_NORMAL)])

        def on_close():
            error_dialog.close_dialog()

        error_dialog.button_clicked.connect(on_close)
        error_dialog.show()

    def on_finished(self, reply, capture_errors):
        self.status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        request_queue.parse_queue()

        if not reply.isOpen() or not self.status_code:
            self.received_json.emit(None, reply.error())
            return

        data = reply.readAll()
        try:
            json_result = json.loads(str(data), encoding='latin_1')

            if 'error' in json_result and capture_errors \
                    and not TriblerRequestManager.window.core_manager.shutting_down:
                self.show_error(TriblerRequestManager.get_message_from_error(json_result))
            else:
                self.received_json.emit(json_result, reply.error())
        except ValueError:
            self.received_json.emit(None, reply.error())
            logging.error("No json object could be decoded from data: %s" % data)

        # We disconnect the slot since we want the finished only to be emitted once. This allows us to reuse the
        # request manager.
        try:
            reply.finished.disconnect()
            self.received_json.disconnect()
        except TypeError:
            pass  # We probably didn't have any connected slots.

        try:
            reply.deleteLater()
        except RuntimeError:
            pass

        self.reply = None

    def download_file(self, endpoint, read_callback):
        def download_callback(reply, _):
            self.on_file_download_finished(reply)

        if read_callback:
            self.received_file.connect(read_callback)

        self.received_file.connect(read_callback)
        dispatcher.download_file(self, endpoint, download_callback)

    def on_file_download_finished(self, reply):
        data = reply.readAll()
        self.received_file.emit(data)
        self.received_file.disconnect()

    def cancel_request(self):
        """
        Cancel the request by aborting the reply handle and calling on_cancel if available.
        """
        if self.reply:
            self.reply.abort()
        self.on_cancel()


class TriblerRequestWorker(QNetworkAccessManager):
    """
    This is a worker class responsible for handling the HTTP requests. It spawns a separate thread so better to reuse.
    All requests are asynchronous so the caller object should keep track of response (QNetworkReply) object. A finished
    pyqt signal is fired when the response data is ready.
    """

    def __init__(self):
        QNetworkAccessManager.__init__(self)
        self.dispatch_map = {
            'GET': self.perform_get,
            'PATCH': self.perform_patch,
            'PUT': self.perform_put,
            'DELETE': self.perform_delete,
            'POST': self.perform_post
        }
        self.protocol = DEFAULT_API_PROTOCOL
        self.host = DEFAULT_API_HOST
        self.port = DEFAULT_API_PORT

    def update_host(self, host):
        self.host = host

    def update_port(self, port):
        self.port = port

    def update_protocol(self, protocol):
        self.protocol = protocol

    def get_base_url(self):
        return "%s://%s:%d/" % (self.protocol, self.host, self.port)

    def perform_request(self, endpoint, reply_callback, data, method):
        """
        Perform a HTTP request.
        :param endpoint: the endpoint to call (i.e. "statistics"), could also be a full URL
        :param reply_callback: the callback to be called with result info when we have the data
        :param data: optional POST data to be sent with the request
        :param method: the HTTP verb (GET/POST/PUT/PATCH)
        """
        if endpoint.startswith("http:") or endpoint.startswith("https:"):
            url = endpoint
        else:
            url = self.get_base_url() + endpoint

        log = [endpoint, method, data, time(), 0]
        performed_requests.append(log)
        network_reply = self.dispatch_map.get(method, lambda x, y, z: None)(endpoint, data, url)
        network_reply.finished.connect(lambda cb=reply_callback, nr=network_reply: cb(nr, log))

        return network_reply

    def perform_get(self, endpoint, data, url):
        """
        Perform an HTTP GET request.

        :param endpoint: the name of the Tribler endpoint.
        :param data: the data/body to send with the request.
        :param url: the url to send the request to.
        """
        buf = QBuffer()
        buf.setData(data)
        buf.open(QIODevice.ReadOnly)
        get_request = QNetworkRequest(QUrl(url))
        reply = self.sendCustomRequest(get_request, "GET", buf)
        buf.setParent(reply)
        return reply

    def perform_patch(self, endpoint, data, url):
        """
        Perform an HTTP PATCH request.

        :param endpoint: the name of the Tribler endpoint.
        :param data: the data/body to send with the request.
        :param url: the url to send the request to.
        """
        buf = QBuffer()
        buf.setData(data)
        buf.open(QIODevice.ReadOnly)
        patch_request = QNetworkRequest(QUrl(url))
        reply = self.sendCustomRequest(patch_request, "PATCH", buf)
        buf.setParent(reply)
        return reply

    def perform_put(self, endpoint, data, url):
        """
        Perform an HTTP PUT request.

        :param endpoint: the name of the Tribler endpoint.
        :param data: the data/body to send with the request.
        :param url: the url to send the request to.
        """
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/x-www-form-urlencoded")
        reply = self.put(request, data)
        return reply

    def perform_delete(self, endpoint, data, url):
        """
        Perform an HTTP DELETE request.

        :param endpoint: the name of the Tribler endpoint.
        :param data: the data/body to send with the request.
        :param url: the url to send the request to.
        """
        buf = QBuffer()
        buf.setData(data)
        buf.open(QIODevice.ReadOnly)
        delete_request = QNetworkRequest(QUrl(url))
        reply = self.sendCustomRequest(delete_request, "DELETE", buf)
        buf.setParent(reply)
        return reply

    def perform_post(self, endpoint, data, url):
        """
        Perform an HTTP POST request.

        :param endpoint: the name of the Tribler endpoint.
        :param data: the data/body to send with the request.
        :param url: the url to send the request to.
        """

        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/x-www-form-urlencoded")
        reply = self.post(request, data)
        return reply
