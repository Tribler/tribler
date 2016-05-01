import json
from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest


class EventRequestManager(QNetworkAccessManager):
    """
    The EventRequestManager class handles the events connection over which important events in Tribler are pushed.
    """

    received_free_space = pyqtSignal(str)
    received_download_status = pyqtSignal(object)

    def on_error(self, error):
        # TODO Martijn: do something useful here
        print "GOT EVENT ERROR"

    def on_finished(self):
        # TODO Martijn: do something useful here
        print self.reply.error()

    def on_read_data(self):
        data = self.reply.readAll()
        json_dict = json.loads(str(data))
        if json_dict["type"] == "free_space":
            self.received_free_space.emit(json_dict["free_space"])
        elif json_dict["type"] == "downloads":
            self.received_download_status.emit(json_dict["downloads"])

    def __init__(self):
        QNetworkAccessManager.__init__(self)
        url = QUrl("http://localhost:8085/events")
        req = QNetworkRequest(url)
        self.reply = self.get(req)

        self.reply.readyRead.connect(self.on_read_data)
        self.reply.finished.connect(self.on_finished)
        self.reply.error.connect(self.on_error)
