import logging
import time

from PyQt5.QtCore import QTimer, QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

from tribler_common.simpledefs import NTFY

import tribler_core.utilities.json_util as json

received_events = []


class CoreConnectTimeoutError(RuntimeError):
    pass


class EventRequestManager(QNetworkAccessManager):
    """
    The EventRequestManager class handles the events connection over which important events in Tribler are pushed.
    """

    node_info_updated = pyqtSignal(object)
    received_remote_query_results = pyqtSignal(object)
    tribler_started = pyqtSignal(object)
    upgrader_tick = pyqtSignal(str)
    upgrader_finished = pyqtSignal()
    new_version_available = pyqtSignal(str)
    discovered_channel = pyqtSignal(object)
    torrent_finished = pyqtSignal(object)
    low_storage_signal = pyqtSignal(object)
    tribler_shutdown_signal = pyqtSignal(str)

    def __init__(self, api_port, api_key):
        QNetworkAccessManager.__init__(self)
        url = QUrl("http://localhost:%d/events" % api_port)
        self.request = QNetworkRequest(url)
        self.request.setRawHeader(b'X-Api-Key', api_key)
        self.failed_attempts = 0
        self.connect_timer = QTimer()
        self.current_event_string = ""
        self.reply = None
        self.shutting_down = False
        self._logger = logging.getLogger('TriblerGUI')
        self.reactions_dict = {
            NTFY.CHANNEL_ENTITY_UPDATED.value: self.node_info_updated.emit,
            NTFY.TRIBLER_NEW_VERSION.value: lambda data: self.new_version_available.emit(data["version"]),
            NTFY.UPGRADER_DONE.value: self.upgrader_finished.emit,
            NTFY.UPGRADER_TICK.value: lambda data: self.upgrader_tick.emit(data["text"]),
            NTFY.CHANNEL_DISCOVERED.value: self.discovered_channel.emit,
            NTFY.TORRENT_FINISHED.value: self.torrent_finished.emit,
            NTFY.LOW_SPACE.value: self.low_storage_signal.emit,
            NTFY.REMOTE_QUERY_RESULTS.value: self.received_remote_query_results.emit,
            NTFY.TRIBLER_SHUTDOWN_STATE.value: self.tribler_shutdown_signal.emit,
            NTFY.EVENTS_START.value: self.events_start_received,
            NTFY.TRIBLER_STARTED.value: lambda data: self.tribler_started.emit(data["version"]),
        }

    def events_start_received(self, event_dict):
        if event_dict["tribler_started"]:
            self.tribler_started.emit(event_dict["version"])

    def on_error(self, error, reschedule_on_err):
        self._logger.info("Got Tribler core error: %s" % error)
        if self.failed_attempts == 120:
            raise CoreConnectTimeoutError("Could not connect with the Tribler Core within 60 seconds")

        self.failed_attempts += 1

        if reschedule_on_err:
            # Reschedule an attempt
            self.connect_timer = QTimer()
            self.connect_timer.setSingleShot(True)
            self.connect_timer.timeout.connect(self.connect)
            self.connect_timer.start(500)

    def on_read_data(self):
        if self.receivers(self.finished) == 0:
            self.finished.connect(lambda reply: self.on_finished())
        self.connect_timer.stop()
        data = self.reply.readAll()
        self.current_event_string += bytes(data).decode('utf8')
        if len(self.current_event_string) > 0 and self.current_event_string[-2:] == '\n\n':
            for event in self.current_event_string.split('\n\n'):
                if len(event) == 0:
                    continue
                event = event[5:] if event.startswith('data:') else event
                json_dict = json.loads(event)

                received_events.insert(0, (json_dict, time.time()))
                if len(received_events) > 100:  # Only buffer the last 100 events
                    received_events.pop()

                event_type, event = json_dict.get("type"), json_dict.get("event")
                reaction = self.reactions_dict.get(event_type)
                if reaction:
                    if event:
                        reaction(event)
                    else:
                        reaction()
                elif event_type == NTFY.TRIBLER_EXCEPTION.value:
                    raise RuntimeError(json_dict["event"]["text"])
            self.current_event_string = ""

    def on_finished(self):
        """
        Somehow, the events connection dropped. Try to reconnect.
        """
        if self.shutting_down:
            return
        self._logger.warning("Events connection dropped, attempting to reconnect")
        self.failed_attempts = 0

        self.connect_timer = QTimer()
        self.connect_timer.setSingleShot(True)
        self.connect_timer.timeout.connect(self.connect)
        self.connect_timer.start(500)

    def connect(self, reschedule_on_err=True):
        self._logger.info("Will connect to events endpoint")
        self.reply = self.get(self.request)

        self.reply.readyRead.connect(self.on_read_data)
        self.reply.error.connect(lambda error: self.on_error(error, reschedule_on_err=reschedule_on_err))
