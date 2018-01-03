from collections import deque, namedtuple
import logging
from threading import RLock
from time import time

from PyQt5.QtCore import QUrl, pyqtSignal, QIODevice, QBuffer
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

import Tribler.Core.Utilities.json_util as json
from TriblerGUI.defs import BUTTON_TYPE_NORMAL, API_PORT
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog


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

    def __init__(self, max_outstanding=200, timeout=15):
        """
        Create a RequestQueue object for rate-limiting HTTP requests.

        :param max_outstanding: the maximum number of requests which can be unanswered at any given time.
        :param timeout: the time after which a request is assumed to never receive a response.
        """
        self.queue = [] # [(TriblerRequestManager, callable, QueuePriorityEnum, time, [performed])]
        self.max_outstanding = max_outstanding
        self.timeout = timeout
        self.old_medium_index = 0.0 # The previous queue quotient where QueuePriorityEnum.MEDIUM items started
        self.old_low_index = 0.0 # The previous queue quotient where QueuePriorityEnum.LOW items started
        self.lock = RLock() # Don't allow asynchronous access to the queue

    def parse_queue(self):
        """
        Update the current queue and check if requests are completed and/or need to be sent.
        """
        self.lock.acquire()
        # 1. Filter out completed and timed-out requests
        current_time = time()
        self.queue = [(request_manager, callback, priority, insertion_time, performed)
                      for request_manager, callback, priority, insertion_time, performed in self.queue
                      if request_manager.status_code == -1 and
                      (current_time - insertion_time < self.timeout or request_manager.cancel_request())] # or is lazy
        # 2. Perform new requests, which aren't already pending
        outstanding = 0
        for _, callback, priority, _, performed in self.queue:
            called = performed[0]
            if not called:
                callback()
                performed[0] = True
            outstanding += 1
            if outstanding >= self.max_outstanding:
                break
        self.lock.release()

    def enqueue(self, request_manager, callback, priority=QueuePriorityEnum.CRITICAL):
        """
        Add a new request to the queue.

        If priority equals:
         - CRITICAL: Send request immediately
         - HIGH: Send request as soon as possible, respecting the 'max_outstanding' setting
         - MEDIUM: Send request as soon as no more HIGH priority items exist, drop in case of very high load
         - LOW: Send request if not MEDIUM or HIGH priority items exist, drop in case of average load

        :param request_manager: the TriblerRequestManager wishing to perform a request.
        :param callback: the callback to call if when this request is allowed to be sent.
        :param priority: the priority for this request.
        """
        # Send CRITICAL requests immediately
        if priority == QueuePriorityEnum.CRITICAL:
            callback()
            return
        self.lock.acquire()
        queue_length = len(self.queue)
        insert_point = -1
        insert_guess = 0
        insert_step = 1
        insert_find = QueuePriorityEnum.CRITICAL
        # Create an educated guess to find where in the queue to insert a request
        # If the queue is too full, drop/cancel the request
        if priority == QueuePriorityEnum.HIGH and queue_length > 0:
            insert_guess = max(min(int(queue_length * self.old_medium_index), queue_length), 0)
            insert_step = 1 if self.queue[insert_guess] == QueuePriorityEnum.HIGH else -1
            insert_find = QueuePriorityEnum.MEDIUM if insert_step == 1 else QueuePriorityEnum.HIGH
        elif priority == QueuePriorityEnum.MEDIUM and queue_length > 0:
            if queue_length > 200:
                logging.error("Too many requests to handle new request with priority %s.", priority)
                request_manager.cancel_request()
                return
            insert_guess = max(min(int(queue_length * self.old_low_index), queue_length), 0)
            insert_step = 1 if self.queue[insert_guess] == QueuePriorityEnum.MEDIUM else -1
            insert_find = QueuePriorityEnum.LOW if insert_step == 1 else QueuePriorityEnum.MEDIUM
        else:
            if queue_length > 80:
                logging.error("Too many requests to handle new request with priority %s.", priority)
                request_manager.cancel_request()
                return
            insert_point = queue_length
        # Find the point to insert the request in the queue
        if insert_point == -1:
            for i in xrange(insert_guess, queue_length if insert_step == 1 else 0, insert_step):
                if self.queue[i] == insert_find:
                    insert_point = i + (0 if insert_step == 1 else 1)
                    break
        # Update pointers
        if priority == QueuePriorityEnum.HIGH:
            self.old_medium_index = (insert_point + 0.0)/(queue_length + 1.0)
        elif priority == QueuePriorityEnum.MEDIUM:
            self.old_low_index = (insert_point + 0.0) / (queue_length + 1.0)
        self.queue.insert(insert_point, QueueItem(request_manager, callback, priority, time(), [False, ]))
        self.parse_queue()
        self.lock.release()

    def clear(self):
        """
        Clear the queue.
        """
        self.lock.acquire()
        for request_manager, _, _, _, _ in self.queue:
            request_manager.cancel_request()
        self.queue = []
        self.lock.release()


request_queue = RequestQueue()
performed_requests = deque(maxlen=200)


class TriblerRequestManager(QNetworkAccessManager):
    """
    This class is responsible for all the requests made to the Tribler REST API.
    """
    window = None

    received_json = pyqtSignal(object, int)
    received_file = pyqtSignal(object)

    def __init__(self):
        QNetworkAccessManager.__init__(self)
        self.base_url = "http://localhost:%d/" % API_PORT
        self.reply = None
        self.status_code = -1
        self.dispatch_map = {
            'GET': self.perform_get,
            'PATCH': self.perform_patch,
            'PUT': self.perform_put,
            'DELETE': self.perform_delete,
            'POST': self.perform_post
        }

    def get_status_code(self):
        """
        Get the status code of this request.
        """
        return self.status_code

    def perform_request(self, endpoint, read_callback, data="", method='GET', capture_errors=True,
                        priority=QueuePriorityEnum.CRITICAL):
        """
        Perform a HTTP request.
        :param endpoint: the endpoint to call (i.e. "statistics")
        :param read_callback: the callback to be called with result info when we have the data
        :param data: optional POST data to be sent with the request
        :param method: the HTTP verb (GET/POST/PUT/PATCH)
        :param capture_errors: whether errors should be handled by this class (defaults to True)
        """
        url = self.base_url + endpoint

        self.status_code = -1
        request_queue.enqueue(self,
                              lambda: self.dispatch_map.get(method, lambda x, y, z: None)(endpoint, data, url),
                              priority)

        if read_callback:
            self.received_json.connect(read_callback)

        self.finished.connect(lambda reply: self.on_finished(reply, capture_errors))

    def perform_get(self, endpoint, data, url):
        """
        Perform an HTTP GET request.

        :param endpoint: the name of the Tribler endpoint.
        :param data: the data/body to send with the request.
        :param url: the url to send the request to.
        """
        performed_requests.append([endpoint, "GET", data, time(), self.get_status_code])
        buf = QBuffer()
        buf.setData(data)
        buf.open(QIODevice.ReadOnly)
        get_request = QNetworkRequest(QUrl(url))
        self.reply = self.sendCustomRequest(get_request, "GET", buf)
        buf.setParent(self.reply)

    def perform_patch(self, endpoint, data, url):
        """
        Perform an HTTP PATCH request.

        :param endpoint: the name of the Tribler endpoint.
        :param data: the data/body to send with the request.
        :param url: the url to send the request to.
        """
        performed_requests.append([endpoint, "PATCH", data, time(), self.get_status_code])
        buf = QBuffer()
        buf.setData(data)
        buf.open(QIODevice.ReadOnly)
        patch_request = QNetworkRequest(QUrl(url))
        self.reply = self.sendCustomRequest(patch_request, "PATCH", buf)
        buf.setParent(self.reply)

    def perform_put(self, endpoint, data, url):
        """
        Perform an HTTP PUT request.

        :param endpoint: the name of the Tribler endpoint.
        :param data: the data/body to send with the request.
        :param url: the url to send the request to.
        """
        performed_requests.append([endpoint, "PUT", data, time(), self.get_status_code])
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/x-www-form-urlencoded")
        self.reply = self.put(request, data)

    def perform_delete(self, endpoint, data, url):
        """
        Perform an HTTP DELETE request.

        :param endpoint: the name of the Tribler endpoint.
        :param data: the data/body to send with the request.
        :param url: the url to send the request to.
        """
        performed_requests.append([endpoint, "DELETE", data, time(), self.get_status_code])
        buf = QBuffer()
        buf.setData(data)
        buf.open(QIODevice.ReadOnly)
        delete_request = QNetworkRequest(QUrl(url))
        self.reply = self.sendCustomRequest(delete_request, "DELETE", buf)
        buf.setParent(self.reply)

    def perform_post(self, endpoint, data, url):
        """
        Perform an HTTP POST request.

        :param endpoint: the name of the Tribler endpoint.
        :param data: the data/body to send with the request.
        :param url: the url to send the request to.
        """
        performed_requests.append([endpoint, "POST", data, time(), self.get_status_code])
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/x-www-form-urlencoded")
        self.reply = self.post(request, data)

    @staticmethod
    def get_message_from_error(error):
        return_error = None
        if isinstance(error['error'], (str, unicode)):
            return_error = error['error']
        elif 'message' in error['error']:
            return_error = error['error']['message']

        if not return_error:
            return json.dumps(error)  # Just print the json object
        return return_error

    def on_finished(self, reply, capture_errors):
        self.status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        request_queue.parse_queue()

        if not reply.isOpen() or not self.status_code:
            self.received_json.emit(None, reply.error())
            return

        data = reply.readAll()
        try:
            json_result = json.loads(str(data), encoding='latin_1')

            if 'error' in json_result and capture_errors:
                self.show_error(TriblerRequestManager.get_message_from_error(json_result))
            else:
                self.received_json.emit(json_result, reply.error())
        except ValueError:
            self.received_json.emit(None, reply.error())
            logging.error("No json object could be decoded from data: %s" % data)

        # We disconnect the slot since we want the finished only to be emitted once. This allows us to reuse the
        # request manager.
        try:
            self.finished.disconnect()
            self.received_json.disconnect()
        except TypeError:
            pass  # We probably didn't have any connected slots.

    def download_file(self, endpoint, read_callback):
        url = self.base_url + endpoint
        self.reply = self.get(QNetworkRequest(QUrl(url)))
        self.received_file.connect(read_callback)
        self.finished.connect(self.on_file_download_finished)

    def on_file_download_finished(self, reply):
        data = reply.readAll()
        self.received_file.emit(data)

    def show_error(self, error_text):
        main_text = "An error occurred during the request:\n\n%s" % error_text
        error_dialog = ConfirmationDialog(TriblerRequestManager.window, "Request error",
                                          main_text, [('CLOSE', BUTTON_TYPE_NORMAL)])

        def on_close():
            error_dialog.setParent(None)

        error_dialog.button_clicked.connect(on_close)
        error_dialog.show()

    def cancel_request(self):
        if self.reply:
            self.reply.abort()
