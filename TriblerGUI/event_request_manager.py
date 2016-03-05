import json
from PyQt5.QtCore import QByteArray, QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest


class EventRequestManager(QNetworkAccessManager):

    received_free_space = pyqtSignal(str)

    def on_error(self, error):
        print "GOT ERROR"

    def on_finished(self):
        print self.reply.error()

    def on_read_data(self):
        data = self.reply.readAll()
        json_dict = json.loads(str(data))
        self.received_free_space.emit(json_dict["free_space"])

    def __init__(self):
        QNetworkAccessManager.__init__(self)
        url = QUrl("http://localhost:8085/events")
        req = QNetworkRequest(url)
        self.reply = self.get(req)

        self.reply.readyRead.connect(self.on_read_data)
        self.reply.finished.connect(self.on_finished)
        self.reply.error.connect(self.on_error)