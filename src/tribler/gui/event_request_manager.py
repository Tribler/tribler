import json
import logging
import time
from typing import Optional

from PyQt5.QtCore import QTimer, QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from tribler.core import notifications
from tribler.core.components.reporter.reported_error import ReportedError
from tribler.core.utilities.notifier import Notifier
from tribler.gui import gui_sentry_reporter
from tribler.gui.exceptions import CoreConnectTimeoutError, CoreConnectionError
from tribler.gui.utilities import connect, make_network_errors_dict

received_events = []

CORE_CONNECTION_TIMEOUT = 120
RECONNECT_INTERVAL_MS = 100


class EventRequestManager(QNetworkAccessManager):
    """
    The EventRequestManager class handles the events connection over which important events in Tribler are pushed.
    """

    node_info_updated = pyqtSignal(object)
    received_remote_query_results = pyqtSignal(object)
    core_connected = pyqtSignal(object)
    new_version_available = pyqtSignal(str)
    discovered_channel = pyqtSignal(object)
    torrent_finished = pyqtSignal(object)
    low_storage_signal = pyqtSignal(object)
    tribler_shutdown_signal = pyqtSignal(str)
    change_loading_text = pyqtSignal(str)
    config_error_signal = pyqtSignal(str)

    def __init__(self, api_port: Optional[int], api_key, error_handler):
        QNetworkAccessManager.__init__(self)
        self.api_port = api_port
        self.api_key = api_key
        self.request: Optional[QNetworkRequest] = None
        self.start_time = time.time()
        self.connect_timer = QTimer()
        self.current_event_string = ""
        self.reply: Optional[QNetworkReply] = None
        self.receiving_data = False
        self.shutting_down = False
        self.error_handler = error_handler
        self._logger = logging.getLogger(self.__class__.__name__)
        self.network_errors = make_network_errors_dict()

        self.connect_timer.setSingleShot(True)
        connect(self.connect_timer.timeout, self.reconnect)

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

    def create_request(self) -> QNetworkRequest:
        if not self.api_port:
            raise RuntimeError("Can't create a request: api_port is not set")

        url = QUrl(f"http://localhost:{self.api_port}/events")
        request = QNetworkRequest(url)
        request.setRawHeader(b'X-Api-Key', self.api_key.encode('ascii'))
        return request

    def set_api_port(self, api_port: int):
        self.api_port = api_port
        self.request = self.create_request()

    def on_events_start(self, public_key: str, version: str):
        # if public key format is changed, don't forget to change it at the core side as well
        if public_key:
            gui_sentry_reporter.set_user(public_key.encode('utf-8'))
        self.core_connected.emit(version)

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

    def on_tribler_shutdown_state(self, state: str):
        self.tribler_shutdown_signal.emit(state)

    def on_report_config_error(self, error):
        self.config_error_signal.emit(error)

    def on_error(self, error: int, reschedule_on_err: bool):
        # If the REST API server is not started yet and the port is not opened, the error will be received.
        # The specific error can be different on different systems:
        #   - QNetworkReply.ConnectionRefusedError (code 1);
        #   - QNetworkReply.HostNotFoundError (code 3);
        #   - QNetworkReply.TimeoutError (code 4);
        #   - QNetworkReply.UnknownNetworkError (code 99).
        # Tribler GUI should retry on any of these errors.

        # Depending on the system, while the server is not started, the error can be returned with some delay
        # (like, five seconds). But don't try to specify a timeout using request.setTransferTimeout(REQUEST_TIMEOUT_MS).
        # First, it is unnecessary, as the reply is sent almost immediately after the REST API is started,
        # so the GUI will not wait five seconds for that. Also, with TransferTimeout specified, AIOHTTP starts
        # raising ConnectionResetError "Cannot write to closing transport".

        if self.shutting_down:
            return

        if self.receiving_data:
            # We are performing reconnect on the initial connection error only.
            # In the future, if we consider it useful, we can immediately call here
            # `self.reconnect(reschedule_on_err=False)`
            # and raise an exception if it fails to reconnect
            raise CoreConnectionError('The connection to the Tribler Core was lost')

        should_retry = reschedule_on_err and time.time() < self.start_time + CORE_CONNECTION_TIMEOUT
        error_name = self.network_errors.get(error, error)
        self._logger.info(f"Error {error_name} while trying to connect to Tribler Core"
                          + (', will retry' if should_retry else ', will not retry'))

        if reschedule_on_err:
            if should_retry:
                self.connect_timer.start(RECONNECT_INTERVAL_MS)  # Reschedule an attempt
            else:
                raise CoreConnectTimeoutError(
                    f"Could not connect with the Tribler Core within {CORE_CONNECTION_TIMEOUT} seconds: "
                    f"{error_name} (code {error})"
                )

    def on_read_data(self):
        if not self.receiving_data:
            self.receiving_data = True
            self._logger.info('Starts receiving data from Core')

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
        self.start_time = time.time()
        self.connect_timer.start(RECONNECT_INTERVAL_MS)

    def connect_to_core(self, reschedule_on_err=True):
        if not self.api_port:
            raise RuntimeError("Can't connect to core: api_port is not set")

        if reschedule_on_err:
            self._logger.info(f"Set event request manager timeout to {CORE_CONNECTION_TIMEOUT} seconds")
            self.start_time = time.time()
        self._connect_to_core(reschedule_on_err)

    def reconnect(self, reschedule_on_err=True):
        self._connect_to_core(reschedule_on_err)

    def _connect_to_core(self, reschedule_on_err):
        self._logger.info(f"Connecting to events endpoint ({'with' if reschedule_on_err else 'without'} retrying)")
        if self.reply is not None:
            self.reply.deleteLater()

        # A workaround for Qt5 bug. See https://github.com/Tribler/tribler/issues/7018
        self.setNetworkAccessible(QNetworkAccessManager.Accessible)

        if not self.request:
            self.request = self.create_request()

        self.reply = self.get(self.request)

        connect(self.reply.readyRead, self.on_read_data)
        connect(self.reply.error, lambda error: self.on_error(error, reschedule_on_err=reschedule_on_err))
