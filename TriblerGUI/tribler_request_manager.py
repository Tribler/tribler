import json
import logging
import mimetypes
from PyQt5.QtCore import QUrl, pyqtSignal, QFile, QIODevice, QByteArray, QFileInfo
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest


class TriblerRequestManager(QNetworkAccessManager):
    """
    This class is responsible for all the requests made to the Tribler REST API.
    """

    base_url = "http://localhost:8085/"

    received_json = pyqtSignal(object, int)
    received_file = pyqtSignal(str, object)

    def send_file(self, endpoint, read_callback, file):
        """
        From http://stackoverflow.com/questions/7922015/qnetworkaccessmanager-posting-files-via-http
        """
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

        contentLength = bytes.length()
        self.request.setRawHeader("Content-Length", "%s" % contentLength)

        self.reply = self.put(self.request, bytes)
        self.received_json.connect(read_callback)
        self.finished.connect(self.on_finished)

    def perform_request(self, endpoint, read_callback, data="", method='GET'):
        url = self.base_url + endpoint

        if method == 'GET':
            self.reply = self.get(QNetworkRequest(QUrl(url)))
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

    def on_error(self, error):
        # TODO Martijn: do something useful here
        print "GOT ERROR"

    def on_finished(self, reply):
        data = reply.readAll()
        try:
            json_result = json.loads(str(data))
            self.received_json.emit(json_result, reply.error())
        except ValueError as ex:
            self.received_json.emit(None, reply.error())
            logging.exception(ex)
            pass

    def download_file(self, endpoint, read_callback):
        url = self.base_url + endpoint
        self.reply = self.get(QNetworkRequest(QUrl(url)))
        self.received_file.connect(read_callback)
        self.finished.connect(self.on_file_download_finished)

    def on_file_download_finished(self, reply):
        content_header = str(reply.rawHeader("Content-Disposition"))
        data = reply.readAll()
        self.received_file.emit(content_header.split("=")[1], data)
