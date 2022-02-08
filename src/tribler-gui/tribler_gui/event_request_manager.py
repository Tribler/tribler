import json
import logging
import time

from PyQt5.QtCore import QTimer, QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from tribler_core import notifications
from tribler_core.components.reporter.reported_error import ReportedError
from tribler_core.utilities.notifier import Notifier

from tribler_gui import gui_sentry_reporter
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

        self.connect_timer.setSingleShot(True)
        connect(self.connect_timer.timeout, self.connect)

        self.notifier = notifier = Notifier()
        notifier.add_observer(notifications.events_start, self.on_events_start)
        notifier.add_observer(notifications.tribler_exception, self.on_tribler_exception)
        notifier.add_observer(notifications.channel_entity_updated, self.on_channel_entity_updated)
        notifier.add_observer(notifications.tribler_new_version, self.on_tribler_new_version)
        notifier.add_observer(notifications.channel_discovered, self.on_channel_discovered)
        notifier.add_observer(notifications.torrent_finished, self.on_torrent_finished)
        notifier.add_observer(notifications.low_space, self.on_low_space)
        notifier.add_observer(notifications.remote_query_results, self.on_remote_query_results)
        notifier.add_observer(notifications.tribler_shutdown_state, self.on_tribler_shutdown_state)
        notifier.add_observer(notifications.report_config_error, self.on_report_config_error)

    def on_events_start(self, public_key: str, version: str):
        if version:
            self.tribler_started_flag = True
            self.tribler_started.emit(version)
            # if public key format will be changed, don't forget to change it
            # at the core side as well
            if public_key:
                gui_sentry_reporter.set_user(public_key.encode('utf-8'))

    def on_tribler_exception(self, error: dict):
        self.error_handler.core_error(ReportedError(**error))

    def on_channel_entity_updated(self, channel_update_dict: dict):
        self.node_info_updated.emit(channel_update_dict)

    def on_tribler_new_version(self, version: str):
        self.new_version_available.emit(version)

    def on_channel_discovered(self, data: dict):
        self.discovered_channel.emit(data)

    def on_torrent_finished(self, infohash: str, name: str, hidden: bool):
        self.torrent_finished.emit(dict(infohash=infohash, name=name, hidden=hidden))

    def on_low_space(self, disk_usage_data: dict):
        self.low_storage_signal.emit(disk_usage_data)

    def on_remote_query_results(self, data: dict):
        self.received_remote_query_results.emit(data)

    def on_tribler_shutdown_state(self,state: str):
        self.tribler_shutdown_signal.emit(state)

    def on_report_config_error(self, error):
        self.config_error_signal.emit(error)

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

                topic_name = json_dict.get("topic", "noname")
                args = json_dict.get("args", [])
                kwargs = json_dict.get("kwargs", {})
                self.notifier.notify_by_topic_name(topic_name, *args, **kwargs)

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
