import json
from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest


class TriblerRequestManager(QNetworkAccessManager):

    received_search_results = pyqtSignal(str)
    received_channels = pyqtSignal(str)
    received_subscribed_channels = pyqtSignal(str)
    received_torrents_in_channel = pyqtSignal(str)
    received_download_details = pyqtSignal(str)
    received_settings = pyqtSignal(str)

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

    def on_read_data_download_details(self):
        data = self.reply.readAll()
        self.received_download_details.emit(str(data))

    def on_read_data_settings(self):
        data = self.reply.readAll()
        self.received_settings.emit(str(data))

    def on_read_data_channels(self):
        data = self.reply.readAll()
        self.received_channels.emit(str(data))

    def on_read_data_subscribed_channels(self):
        data = self.reply.readAll()
        self.received_subscribed_channels.emit(str(data))

    def search_channels(self, query, callback):
        self.received_search_results.connect(callback)
        self.perform_get("http://localhost:8085/channel/search?q=" + query, self.on_read_data_search_channels)

    def get_torrents_in_channel(self, channel_id, callback):
        self.received_torrents_in_channel.connect(callback)
        self.perform_get("http://localhost:8085/channel/" + channel_id + "/torrents",
                         self.on_read_data_torrents_channel)

    def get_download_details(self, infohash, callback):
        self.received_download_details.connect(callback)
        self.perform_get("http://localhost:8085/download/" + infohash, self.on_read_data_download_details)

    def get_settings(self, callback):
        self.received_settings.connect(callback)
        self.perform_get("http://localhost:8085/settings", self.on_read_data_settings)

    def get_channels(self, callback):
        self.received_channels.connect(callback)
        self.perform_get("http://localhost:8085/channels/all", self.on_read_data_channels)

    def get_subscribed_channels(self, callback):
        self.received_subscribed_channels.connect(callback)
        self.perform_get("http://localhost:8085/channels/subscribed", self.on_read_data_subscribed_channels)
