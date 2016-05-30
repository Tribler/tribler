import json
import logging
from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest


class TriblerRequestManager(QNetworkAccessManager):
    """
    This class is responsible for all the requests made to the Tribler REST API.
    """

    base_url = "http://localhost:8085/"

    received_json = pyqtSignal(object, int)

    def perform_request(self, endpoint, read_callback, data="", method='GET'):
        url = self.base_url + endpoint

        if method == 'GET':
            self.reply = self.get(QNetworkRequest(QUrl(url)))
        elif method == 'PUT':
            self.reply = self.put(QNetworkRequest(QUrl(url)), data)
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
