import json
from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest


class SearchRequestManager(QNetworkAccessManager):

    received_search_results = pyqtSignal(str)

    def on_error(self, error):
        print "GOT ERROR"

    def on_finished(self):
        print "SEARCH FINISHED"

    def on_read_data(self):
        data = self.reply.readAll()
        self.received_search_results.emit(str(data))

    def search_channels(self, query):
        url = QUrl("http://localhost:8085/channel/search?q=" + query)
        req = QNetworkRequest(url)
        self.reply = self.get(req)

        self.reply.readyRead.connect(self.on_read_data)
        self.reply.finished.connect(self.on_finished)
        self.reply.error.connect(self.on_error)