import logging
import os
import sys
import time

from PyQt5.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWidgets import QApplication

from tribler_common.utilities import is_frozen

from tribler_gui.event_request_manager import EventRequestManager
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import connect, get_base_path


class CoreManager(QObject):
    """
    The CoreManager is responsible for managing the Tribler core (starting/stopping). When we are running the GUI tests,
    a fake API will be started.
    """

    tribler_stopped = pyqtSignal()

    def __init__(self, api_port, api_key, error_handler):
        QObject.__init__(self, None)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.base_path = get_base_path()
        if not is_frozen():
            self.base_path = os.path.join(get_base_path(), "..")

        self.core_process = None
        self.api_port = api_port
        self.api_key = api_key
        self.events_manager = EventRequestManager(self.api_port, self.api_key, error_handler)

        self.shutting_down = False
        self.should_stop_on_shutdown = False
        self.use_existing_core = True
        self.is_core_running = False
        self.core_traceback = None
        self.core_traceback_timestamp = 0

        connect(self.events_manager.tribler_started, self._set_core_running)

    def _set_core_running(self, _):
        self.is_core_running = True

    def on_core_read_ready(self):
        raw_output = bytes(self.core_process.readAll())
        decoded_output = raw_output.decode(errors="replace")
        if b'Traceback' in raw_output:
            self.core_traceback = decoded_output
            self.core_traceback_timestamp = int(round(time.time() * 1000))
        print(decoded_output.strip())  # noqa: T001

    def on_core_finished(self, exit_code, exit_status):
        if self.shutting_down and self.should_stop_on_shutdown:
            self.on_finished()
        elif not self.shutting_down and exit_code != 0:
            # Stop the event manager loop if it is running
            if self.events_manager.connect_timer and self.events_manager.connect_timer.isActive():
                self.events_manager.connect_timer.stop()

            exception_msg = (
                f"The Tribler core has unexpectedly finished " f"with exit code {exit_code} and status: {exit_status}!"
            )
            if self.core_traceback:
                exception_msg += "\n\n%s\n(Timestamp: %d, traceback timestamp: %d)" % (
                    self.core_traceback,
                    int(round(time.time() * 1000)),
                    self.core_traceback_timestamp,
                )

            raise RuntimeError(exception_msg)

    def start(self, core_args=None, core_env=None, upgrade_manager=None, run_core=True):
        """
        First test whether we already have a Tribler process listening on port <CORE_API_PORT>.
        If so, use that one and don't start a new, fresh Core.
        """
        # Connect to the events manager
        self.events_manager.connect()

        if run_core:

            def on_request_error(_):
                if upgrade_manager:
                    # Start Tribler Upgrader. When it finishes, start Tribler Core
                    connect(
                        upgrade_manager.upgrader_finished,
                        lambda: self.start_tribler_core(core_args=core_args, core_env=core_env),
                    )
                    upgrade_manager.start()
                else:
                    self.start_tribler_core(core_args=core_args, core_env=core_env)

            connect(self.events_manager.reply.error, on_request_error)

    def start_tribler_core(self, core_args=None, core_env=None):
        self.use_existing_core = False
        if not core_env:
            core_env = QProcessEnvironment.systemEnvironment()
            core_env.insert("CORE_API_PORT", f"{self.api_port}")
            core_env.insert("CORE_API_KEY", self.api_key.decode('utf-8'))
        if not core_args:
            core_args = sys.argv + ['--core']

        self.core_process = QProcess()
        self.core_process.setProcessEnvironment(core_env)
        self.core_process.setReadChannel(QProcess.StandardOutput)
        self.core_process.setProcessChannelMode(QProcess.MergedChannels)
        connect(self.core_process.readyRead, self.on_core_read_ready)
        connect(self.core_process.finished, self.on_core_finished)
        self.core_process.start(sys.executable, core_args)

    def stop(self, stop_app_on_shutdown=True):
        if self.core_process or self.is_core_running:
            self.events_manager.shutting_down = True
            TriblerNetworkRequest("shutdown", lambda _: None, method="PUT", priority=QNetworkRequest.HighPriority)

            if stop_app_on_shutdown:
                self.should_stop_on_shutdown = True

    def on_finished(self):
        self.tribler_stopped.emit()
        if self.shutting_down:
            QApplication.quit()
