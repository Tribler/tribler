import json
import logging
from PyQt5.QtCore import QUrl, pyqtSignal, QTimer
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
import time


received_events = []


class EventRequestManager(QNetworkAccessManager):
    """
    The EventRequestManager class handles the events connection over which important events in Tribler are pushed.
    """

    received_search_result_channel = pyqtSignal(object)
    received_search_result_torrent = pyqtSignal(object)
    tribler_started = pyqtSignal()
    upgrader_tick = pyqtSignal(str)
    upgrader_started = pyqtSignal()
    upgrader_finished = pyqtSignal()
    new_version_available = pyqtSignal(str)
    discovered_channel = pyqtSignal(object)
    discovered_torrent = pyqtSignal(object)
    torrent_finished = pyqtSignal(object)

    def __init__(self, api_port):
        QNetworkAccessManager.__init__(self)
        url = QUrl("http://localhost:%d/events" % api_port)
        self.request = QNetworkRequest(url)
        self.failed_attempts = 0
        self.connect_timer = QTimer()
        self.current_event_string = ""
        self.tribler_version = "Unknown"
        self.reply = None
        self._logger = logging.getLogger('TriblerGUI')

    def on_error(self, error, reschedule_on_err):
        self._logger.info("Got Tribler core error: %s" % error)
        if error == QNetworkReply.ConnectionRefusedError:
            if self.failed_attempts == 40:
                raise RuntimeError("Could not connect with the Tribler Core within 20 seconds")

            self.failed_attempts += 1

            if reschedule_on_err:
                # Reschedule an attempt
                self.connect_timer = QTimer()
                self.connect_timer.timeout.connect(self.connect)
                self.connect_timer.start(500)

    def on_read_data(self):
        self.connect_timer.stop()
        data = self.reply.readAll()
        self.current_event_string += data
        if len(self.current_event_string) > 0 and self.current_event_string[-1] == '\n':
            for event in self.current_event_string.split('\n'):
                if len(event) == 0:
                    continue
                json_dict = json.loads(str(event))

                received_events.insert(0, (json_dict, time.time()))
                if len(received_events) > 100:  # Only buffer the last 100 events
                    received_events.pop()

                if json_dict["type"] == "search_result_channel":
                    self.received_search_result_channel.emit(json_dict["event"]["result"])
                elif json_dict["type"] == "search_result_torrent":
                    self.received_search_result_torrent.emit(json_dict["event"]["result"])
                elif json_dict["type"] == "tribler_started":
                    self.tribler_started.emit()
                elif json_dict["type"] == "new_version_available":
                    self.new_version_available.emit(json_dict["event"]["version"])
                elif json_dict["type"] == "upgrader_started":
                    self.upgrader_started.emit()
                elif json_dict["type"] == "upgrader_finished":
                    self.upgrader_finished.emit()
                elif json_dict["type"] == "upgrader_tick":
                    self.upgrader_tick.emit(json_dict["event"]["text"])
                elif json_dict["type"] == "channel_discovered":
                    self.discovered_channel.emit(json_dict["event"])
                elif json_dict["type"] == "torrent_discovered":
                    self.discovered_torrent.emit(json_dict["event"])
                elif json_dict["type"] == "events_start":
                    self.tribler_version = json_dict["event"]["version"]
                    if json_dict["event"]["tribler_started"]:
                        self.tribler_started.emit()
                elif json_dict["type"] == "torrent_finished":
                    self.torrent_finished.emit(json_dict["event"])
                elif json_dict["type"] == "tribler_exception":
                    raise RuntimeError(json_dict["event"]["text"])
            self.current_event_string = ""

    def on_finished(self):
        """
        Somehow, the events connection dropped. Try to reconnect.
        """
        self._logger.warning("Events connection dropped, attempting to reconnect")
        self.failed_attempts = 0
        self.connect()

    def connect(self, reschedule_on_err=True):
        self._logger.info("Will connect to events endpoint")
        self.reply = self.get(self.request)

        self.reply.readyRead.connect(self.on_read_data)
        self.reply.error.connect(lambda error: self.on_error(error, reschedule_on_err=reschedule_on_err))
