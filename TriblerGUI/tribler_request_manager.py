import json
import logging
import mimetypes
import random
import string
from time import time

from PyQt5.QtCore import QUrl, pyqtSignal, QFile, QIODevice, QByteArray, QFileInfo, QBuffer
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest


API_PORT = 8085
performed_requests = {}


class TriblerRequestManager(QNetworkAccessManager):
    """
    This class is responsible for all the requests made to the Tribler REST API.
    """
    received_json = pyqtSignal(object, int)
    received_file = pyqtSignal(str, object)

    def __init__(self):
        QNetworkAccessManager.__init__(self)
        self.request_id = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
        self.base_url = "http://localhost:%d/" % API_PORT

    def send_file(self, endpoint, read_callback, file):
        """
        From http://stackoverflow.com/questions/7922015/qnetworkaccessmanager-posting-files-via-http
        """
        performed_requests[self.request_id] = [endpoint, 'POST', '<torrent file>', time(), -1]

        url = QUrl(self.base_url + endpoint)
        self.request = QNetworkRequest(url)

        self.request.setRawHeader("Host", str(url.host()))
        self.request.setRawHeader("Content-type", "multipart/form-data; boundary=AaB03x")

        fp = QFile(file)
        fp.open(QIODevice.ReadOnly)
        bytes = QByteArray()

        bytes.append("--AaB03x\r\n")
        bytes.append("Content-Disposition: ")
        bytes.append("form-data; name=\"file\"; filename=\"" + QByteArray(str(QFileInfo(file).fileName())) + "\"\r\n")
        bytes.append("Content-Type: %s\r\n" % mimetypes.guess_type(str(file))[0])
        bytes.append("\r\n")
        bytes.append(fp.readAll())

        fp.close()

        bytes.append("\r\n--AaB03x\r\n")
        bytes.append("Content-Disposition: form-data; name=\"source\"\r\nfile")
        bytes.append("\r\n")
        bytes.append("--AaB03x--")

        content_length = bytes.length()
        self.request.setRawHeader("Content-Length", "%s" % content_length)

        self.reply = self.put(self.request, bytes)
        self.received_json.connect(read_callback)
        self.finished.connect(self.on_finished)

    def perform_request(self, endpoint, read_callback, data="", method='GET'):
        performed_requests[self.request_id] = [endpoint, method, data, time(), -1]
        url = self.base_url + endpoint

        if method == 'GET':
            buf = QBuffer()
            buf.setData(data)
            buf.open(QIODevice.ReadOnly)
            get_request = QNetworkRequest(QUrl(url))
            self.reply = self.sendCustomRequest(get_request, "GET", buf)
            buf.setParent(self.reply)
        elif method == 'PUT':
            request = QNetworkRequest(QUrl(url))
            request.setHeader(QNetworkRequest.ContentTypeHeader, "application/x-www-form-urlencoded")
            self.reply = self.put(request, data)
        elif method == 'DELETE':
            self.reply = self.deleteResource(QNetworkRequest(QUrl(url)))
        elif method == 'POST':
            request = QNetworkRequest(QUrl(url))
            request.setHeader(QNetworkRequest.ContentTypeHeader, "application/x-www-form-urlencoded")
            self.reply = self.post(request, data)

        if read_callback:
            self.received_json.connect(read_callback)

        self.finished.connect(self.on_finished)

    def on_finished(self, reply):
        performed_requests[self.request_id][4] = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)

        data = reply.readAll()
        try:
            json_result = json.loads(str(data))
            self.received_json.emit(json_result, reply.error())
        except ValueError as ex:
            self.received_json.emit(None, reply.error())
            logging.exception(ex)

    def download_file(self, endpoint, read_callback):
        url = self.base_url + endpoint
        self.reply = self.get(QNetworkRequest(QUrl(url)))
        self.received_file.connect(read_callback)
        self.finished.connect(self.on_file_download_finished)

    def on_file_download_finished(self, reply):
        content_header = str(reply.rawHeader("Content-Disposition"))
        data = reply.readAll()
        self.received_file.emit(content_header.split("=")[1], data)
