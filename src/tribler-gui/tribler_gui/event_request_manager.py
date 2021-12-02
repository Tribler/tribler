import json
import logging
import time

from PyQt5.QtCore import QTimer, QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from tribler_common.reported_error import ReportedError
from tribler_common.sentry_reporter.sentry_reporter import SentryReporter
from tribler_common.simpledefs import NTFY

from tribler_gui.exceptions import CoreConnectTimeoutError, CoreConnectionError
from tribler_gui.utilities import connect

received_events = []

CORE_CONNECTION_ATTEMPTS_LIMIT = 120
RECONNECT_INTERVAL_MS = 500


class EventRequestManager(QNetworkAccessManager):
    """
    The EventRequestManager class handles the events connection over which important events in Tribler are pushed.
    """

    node_info_updated = pyqtSignal(object)
    received_remote_query_results = pyqtSignal(object)
    tribler_started = pyqtSignal(object)
    new_version_available = pyqtSignal(str)
    discovered_channel = pyqtSignal(object)
    torrent_finished = pyqtSignal(object)
    low_storage_signal = pyqtSignal(object)
    tribler_shutdown_signal = pyqtSignal(str)
    change_loading_text = pyqtSignal(str)
    config_error_signal = pyqtSignal(str)

    def __init__(self, api_port, api_key, error_handler):
        QNetworkAccessManager.__init__(self)
        url = QUrl("http://localhost:%d/events" % api_port)
        self.request = QNetworkRequest(url)
        self.request.setRawHeader(b'X-Api-Key', api_key.encode('ascii'))
        self.remaining_connection_attempts = CORE_CONNECTION_ATTEMPTS_LIMIT
        self.connect_timer = QTimer()
        self.current_event_string = ""
        self.reply = None
        self.shutting_down = False
        self.error_handler = error_handler
        self._logger = logging.getLogger(self.__class__.__name__)
        # This flag is used to prevent race condition when starting GUI tests
        self.tribler_started_flag = False
        self.reactions_dict = {
            NTFY.CHANNEL_ENTITY_UPDATED.value: self.node_info_updated.emit,
            NTFY.TRIBLER_NEW_VERSION.value: lambda data: self.new_version_available.emit(data["version"]),
            NTFY.CHANNEL_DISCOVERED.value: self.discovered_channel.emit,
            NTFY.TORRENT_FINISHED.value: self.torrent_finished.emit,
            NTFY.LOW_SPACE.value: self.low_storage_signal.emit,
            NTFY.REMOTE_QUERY_RESULTS.value: self.received_remote_query_results.emit,
            NTFY.TRIBLER_SHUTDOWN_STATE.value: self.tribler_shutdown_signal.emit,
            NTFY.EVENTS_START.value: self.events_start_received,
            NTFY.REPORT_CONFIG_ERROR.value: self.config_error_signal.emit,
            NTFY.TRIBLER_EXCEPTION.value: lambda data: self.error_handler.core_error(ReportedError(**data)),
        }

        self.connect_timer.setSingleShot(True)
        connect(self.connect_timer.timeout, self.connect)

    def events_start_received(self, event_dict):
        if event_dict["version"]:
            self.tribler_started_flag = True
            self.tribler_started.emit(event_dict["version"])
            # if public key format will be changed, don't forget to change it
            # at the core side as well
            public_key = event_dict["public_key"]
            if public_key:
                SentryReporter.set_user(public_key.encode('utf-8'))

    def on_error(self, error, reschedule_on_err):
        if error == QNetworkReply.ConnectionRefusedError:
            self._logger.debug("Tribler Core refused connection, retrying...")
        else:
            raise CoreConnectionError(f"Error {error} while trying to connect to Tribler Core")

        if self.remaining_connection_attempts <= 0:
            raise CoreConnectTimeoutError(
                f"Could not connect with the Tribler Core \
                within {RECONNECT_INTERVAL_MS*CORE_CONNECTION_ATTEMPTS_LIMIT} seconds"
            )

        self.remaining_connection_attempts -= 1

        if reschedule_on_err:
            # Reschedule an attempt
            self.connect_timer.start(RECONNECT_INTERVAL_MS)

    def on_read_data(self):
        if self.receivers(self.finished) == 0:
            connect(self.finished, lambda reply: self.on_finished())
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
            self.current_event_string = ""

    def on_finished(self):
        """
        Somehow, the events connection dropped. Try to reconnect.
        """
        if self.shutting_down:
            return
        self._logger.warning("Events connection dropped, attempting to reconnect")
        self.remaining_connection_attempts = CORE_CONNECTION_ATTEMPTS_LIMIT
        self.connect_timer.start(RECONNECT_INTERVAL_MS)

    def connect(self, reschedule_on_err=True):
        self._logger.debug("Will connect to events endpoint")
        if self.reply is not None:
            self.reply.deleteLater()
        self.reply = self.get(self.request)

        connect(self.reply.readyRead, self.on_read_data)
        connect(self.reply.error, lambda error: self.on_error(error, reschedule_on_err=reschedule_on_err))
