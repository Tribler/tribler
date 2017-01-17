import json
import logging
import random
import string
from time import time

from PyQt5.QtCore import QUrl, pyqtSignal, QIODevice, QBuffer
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from TriblerGUI.defs import BUTTON_TYPE_NORMAL
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog

API_PORT = 8085
performed_requests = {}


class TriblerRequestManager(QNetworkAccessManager):
    """
    This class is responsible for all the requests made to the Tribler REST API.
    """
    window = None

    received_json = pyqtSignal(object, int)
    received_file = pyqtSignal(str, object)

    def __init__(self):
        QNetworkAccessManager.__init__(self)
        self.request_id = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
        self.base_url = "http://localhost:%d/" % API_PORT
        self.reply = None
        self.error_dialog = None

    def perform_request(self, endpoint, read_callback, data="", method='GET', capture_errors=True):
        """
        Perform a HTTP request.
        :param endpoint: the endpoint to call (i.e. "statistics")
        :param read_callback: the callback to be called with result info when we have the data
        :param data: optional POST data to be sent with the request
        :param method: the HTTP verb (GET/POST/PUT/PATCH)
        :param capture_errors: whether errors should be handled by this class (defaults to True)
        """
        performed_requests[self.request_id] = [endpoint, method, data, time(), -1]
        url = self.base_url + endpoint

        if method == 'GET':
            buf = QBuffer()
            buf.setData(data)
            buf.open(QIODevice.ReadOnly)
            get_request = QNetworkRequest(QUrl(url))
            self.reply = self.sendCustomRequest(get_request, "GET", buf)
            buf.setParent(self.reply)
        elif method == 'PATCH':
            buf = QBuffer()
            buf.setData(data)
            buf.open(QIODevice.ReadOnly)
            patch_request = QNetworkRequest(QUrl(url))
            self.reply = self.sendCustomRequest(patch_request, "PATCH", buf)
            buf.setParent(self.reply)
        elif method == 'PUT':
            request = QNetworkRequest(QUrl(url))
            request.setHeader(QNetworkRequest.ContentTypeHeader, "application/x-www-form-urlencoded")
            self.reply = self.put(request, data)
        elif method == 'DELETE':
            buf = QBuffer()
            buf.setData(data)
            buf.open(QIODevice.ReadOnly)
            delete_request = QNetworkRequest(QUrl(url))
            self.reply = self.sendCustomRequest(delete_request, "DELETE", buf)
            buf.setParent(self.reply)
        elif method == 'POST':
            request = QNetworkRequest(QUrl(url))
            request.setHeader(QNetworkRequest.ContentTypeHeader, "application/x-www-form-urlencoded")
            self.reply = self.post(request, data)

        if read_callback:
            self.received_json.connect(read_callback)

        self.finished.connect(lambda reply: self.on_finished(reply, capture_errors))

    def on_finished(self, reply, capture_errors):
        performed_requests[self.request_id][4] = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)

        data = reply.readAll()
        try:
            json_result = json.loads(str(data))

            if 'error' in json_result and capture_errors:
                if isinstance(json_result['error'], (str, unicode)):
                    self.show_error(json_result['error'])
                elif 'message' in json_result['error']:
                    self.show_error(json_result['error']['message'])
            else:
                self.received_json.emit(json_result, reply.error())
        except ValueError:
            self.received_json.emit(None, reply.error())
            logging.error("No json object could be decoded from data: %s" % data)

    def download_file(self, endpoint, read_callback):
        url = self.base_url + endpoint
        self.reply = self.get(QNetworkRequest(QUrl(url)))
        self.received_file.connect(read_callback)
        self.finished.connect(self.on_file_download_finished)

    def on_file_download_finished(self, reply):
        content_header = str(reply.rawHeader("Content-Disposition"))
        data = reply.readAll()
        self.received_file.emit(content_header.split("=")[1], data)

    def show_error(self, error_text):
        main_text = "An error occurred during the request:\n\n%s" % error_text
        self.error_dialog = ConfirmationDialog(TriblerRequestManager.window, "Request error",
                                               main_text, [('close', BUTTON_TYPE_NORMAL)])
        self.error_dialog.button_clicked.connect(self.on_error_dialog_cancel_clicked)
        self.error_dialog.show()

    def on_error_dialog_cancel_clicked(self, _):
        self.error_dialog.setParent(None)
        self.error_dialog = None

    def cancel_request(self):
        if self.reply:
            self.reply.abort()
