import json
from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest


class TriblerRequestManager(QNetworkAccessManager):

    received_search_results = pyqtSignal(str)
    received_torrents_in_channel = pyqtSignal(str)

    def perform_get(self, url, read_callback):
        self.reply = self.get(QNetworkRequest(QUrl(url)))

        self.reply.readyRead.connect(read_callback)
        self.reply.finished.connect(self.on_finished)
        self.reply.error.connect(self.on_error)

    def on_error(self, error):
        print "GOT ERROR"

    def on_finished(self):
        print "REQUEST FINISHED"

    def on_read_data_search_channels(self):
        data = self.reply.readAll()
        self.received_search_results.emit(str(data))

    def on_read_data_torrents_channel(self):
        data = self.reply.readAll()
        self.received_torrents_in_channel.emit(str(data))

    def search_channels(self, query):
        self.perform_get("http://localhost:8085/channel/search?q=" + query, self.on_read_data_search_channels)

    def get_torrents_in_channel(self, channel_id):
        self.perform_get("http://localhost:8085/channel/" + channel_id + "/torrents",
                         self.on_read_data_torrents_channel)