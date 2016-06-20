import json
from PyQt5.QtCore import QUrl, pyqtSignal, QTimer
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


class EventRequestManager(QNetworkAccessManager):
    """
    The EventRequestManager class handles the events connection over which important events in Tribler are pushed.
    """

    received_search_result_channel = pyqtSignal(object)
    received_search_result_torrent = pyqtSignal(object)
    tribler_started = pyqtSignal()

    def __init__(self):
        QNetworkAccessManager.__init__(self)
        url = QUrl("http://localhost:8085/events")
        self.request = QNetworkRequest(url)
        self.failed_attempts = 0
        self.connect_timer = 0
        self.current_event_string = ""

    def on_error(self, error):
        if error == QNetworkReply.ConnectionRefusedError:
            if self.failed_attempts == 20:
                raise RuntimeError("Could not connect with the Tribler Core within 10 seconds")

            self.failed_attempts += 1

            # Reschedule an attempt
            self.connect_timer = QTimer()
            self.connect_timer.timeout.connect(self.connect)
            self.connect_timer.start(500)

    def on_read_data(self):
        self.connect_timer.stop()
        data = self.reply.readAll()
        self.current_event_string += data
        if self.current_event_string[-1] == '\n':
            for event in self.current_event_string.split('\n'):
                print event
                if len(event) == 0:
                    continue
                json_dict = json.loads(str(event))
                if json_dict["type"] == "search_result_channel":
                    self.received_search_result_channel.emit(json_dict["event"]["result"])
                elif json_dict["type"] == "search_result_torrent":
                    self.received_search_result_torrent.emit(json_dict["event"]["result"])
                elif json_dict["type"] == "tribler_started":
                    self.tribler_started.emit()
            self.current_event_string = ""

    def connect(self):
        self.reply = self.get(self.request)

        self.reply.readyRead.connect(self.on_read_data)
        self.reply.error.connect(self.on_error)
