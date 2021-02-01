import logging
import os
import sys
import time

from PyQt5.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWidgets import QApplication

from tribler_common.utilities import is_frozen

from tribler_core.upgrade.version_manager import should_fork_state_directory
from tribler_core.utilities.osutils import get_root_state_directory
from tribler_core.version import version_id

from tribler_gui.event_request_manager import EventRequestManager
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import connect, get_base_path

START_FAKE_API = False


class CoreManager(QObject):
    """
    The CoreManager is responsible for managing the Tribler core (starting/stopping). When we are running the GUI tests,
    a fake API will be started.
    """

    tribler_stopped = pyqtSignal()
    core_state_update = pyqtSignal(str)

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

        self.check_state_timer = QTimer()
        self.check_state_timer.setSingleShot(True)
        connect(self.check_state_timer.timeout, self.check_core_ready)

    def on_core_read_ready(self):
        raw_output = bytes(self.core_process.readAll())
        decoded_output = raw_output.decode(errors="replace")
        if b'Traceback' in raw_output:
            self.core_traceback = decoded_output
            self.core_traceback_timestamp = int(round(time.time() * 1000))
        print(decoded_output.strip())

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

    def start(self, core_args=None, core_env=None):
        """
        First test whether we already have a Tribler process listening on port 8085. If so, use that one and don't
        start a new, fresh session.
        """

        def on_request_error(_):
            self.use_existing_core = False
            self.start_tribler_core(core_args=core_args, core_env=core_env)

        self.events_manager.connect()
        connect(self.events_manager.reply.error, on_request_error)
        # This is a hack to determine if we have notify the user to wait for the directory fork to finish
        _, _, src_dir, tgt_dir = should_fork_state_directory(get_root_state_directory(), version_id)
        if src_dir is not None:
            # There is going to be a directory fork, so we extend the core connection timeout and notify the user
            self.events_manager.remaining_connection_attempts = 1200
            self.events_manager.change_loading_text.emit("Copying data from previous Tribler version, please wait")

    def start_tribler_core(self, core_args=None, core_env=None):
        if not START_FAKE_API:
            if not core_env:
                core_env = QProcessEnvironment.systemEnvironment()
                core_env.insert("CORE_PROCESS", "1")
                core_env.insert("CORE_BASE_PATH", self.base_path)
                core_env.insert("CORE_API_PORT", f"{self.api_port}")
                core_env.insert("CORE_API_KEY", self.api_key.decode('utf-8'))
            if not core_args:
                core_args = sys.argv

            self.core_process = QProcess()
            self.core_process.setProcessEnvironment(core_env)
            self.core_process.setReadChannel(QProcess.StandardOutput)
            self.core_process.setProcessChannelMode(QProcess.MergedChannels)
            connect(self.core_process.readyRead, self.on_core_read_ready)
            connect(self.core_process.finished, self.on_core_finished)
            self.core_process.start(sys.executable, core_args)

        self.check_core_ready()

    def check_core_ready(self):
        TriblerNetworkRequest(
            "state", self.on_received_state, capture_core_errors=False, priority=QNetworkRequest.HighPriority
        )

    def on_received_state(self, state):
        if not state or 'state' not in state or state['state'] not in ['STARTED', 'EXCEPTION']:
            self.check_state_timer.start(50)
            return

        self.core_state_update.emit(state['readable_state'])

        if state['state'] == 'STARTED':
            self.events_manager.connect(reschedule_on_err=False)
            self.is_core_running = True
        elif state['state'] == 'EXCEPTION':
            raise RuntimeError(state['last_exception'])

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
