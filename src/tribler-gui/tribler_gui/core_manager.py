import logging
import sys

from PyQt5.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWidgets import QApplication

from tribler_gui.event_request_manager import EventRequestManager
from tribler_gui.exceptions import CoreCrashedError
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import connect


class CoreManager(QObject):
    """
    The CoreManager is responsible for managing the Tribler core (starting/stopping). When we are running the GUI tests,
    a fake API will be started.
    """

    def __init__(self, root_state_dir, api_port, api_key, error_handler):
        QObject.__init__(self, None)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.root_state_dir = root_state_dir
        self.core_process = None
        self.api_port = api_port
        self.api_key = api_key
        self.events_manager = EventRequestManager(self.api_port, self.api_key, error_handler)

        self.upgrade_manager = None
        self.core_args = None
        self.core_env = None

        self.core_started = False
        self.core_running = False
        self.core_connected = False
        self.shutting_down = False
        self.core_finished = False
        self.quitting_app = False

        self.should_quit_app_on_core_finished = False

        self.use_existing_core = True
        self.last_core_stdout_output: str = ''
        self.last_core_stderr_output: str = ''

        connect(self.events_manager.tribler_started, self.on_core_connected)

    def on_core_connected(self, _):
        if not self.core_finished:
            self.core_connected = True

    def start(self, core_args=None, core_env=None, upgrade_manager=None, run_core=True):
        """
        First test whether we already have a Tribler process listening on port <CORE_API_PORT>.
        If so, use that one and don't start a new, fresh Core.
        """
        # Connect to the events manager
        self.events_manager.connect()

        if run_core:
            self.core_args = core_args
            self.core_env = core_env
            self.upgrade_manager = upgrade_manager
            connect(self.events_manager.reply.error, self.on_event_manager_initial_error)

    def on_event_manager_initial_error(self, _):
        if self.upgrade_manager:
            # Start Tribler Upgrader. When it finishes, start Tribler Core
            connect(self.upgrade_manager.upgrader_finished, self.start_tribler_core)
            self.upgrade_manager.start()
        else:
            self.start_tribler_core()

    def start_tribler_core(self):
        self.use_existing_core = False

        core_env = self.core_env
        if not core_env:
            core_env = QProcessEnvironment.systemEnvironment()
            core_env.insert("CORE_API_PORT", f"{self.api_port}")
            core_env.insert("CORE_API_KEY", self.api_key)
            core_env.insert("TSTATEDIR", str(self.root_state_dir))

        core_args = self.core_args
        if not core_args:
            core_args = sys.argv + ['--core']

        self.core_process = QProcess()
        self.core_process.setProcessEnvironment(core_env)
        self.core_process.setProcessChannelMode(QProcess.SeparateChannels)
        connect(self.core_process.started, self.on_core_started)
        connect(self.core_process.readyReadStandardOutput, self.on_core_stdout_read_ready)
        connect(self.core_process.readyReadStandardError, self.on_core_stderr_read_ready)
        connect(self.core_process.finished, self.on_core_finished)
        self.core_process.start(sys.executable, core_args)

    def on_core_started(self):
        self.core_started = True
        self.core_running = True

    def on_core_stdout_read_ready(self):
        raw_output = bytes(self.core_process.readAllStandardOutput())
        self.last_core_stdout_output = raw_output.decode("utf-8").strip()
        try:
            print(self.last_core_stdout_output)  # print core output # noqa: T001
        except OSError:
            # Possible reason - cannot write to stdout as it was already closed during the application shutdown
            if not self.quitting_app:
                raise

    def on_core_stderr_read_ready(self):
        raw_output = bytes(self.core_process.readAllStandardError())
        self.last_core_stderr_output = raw_output.decode("utf-8").strip()
        try:
            print(self.last_core_stderr_output, file=sys.stderr)  # print core output # noqa: T001
        except OSError:
            # Possible reason - cannot write to stdout as it was already closed during the application shutdown
            if not self.quitting_app:
                raise

    def stop(self, quit_app_on_core_finished=True):
        if quit_app_on_core_finished:
            self.should_quit_app_on_core_finished = True

        if self.shutting_down:
            return

        self.shutting_down = True
        self._logger.info("Stopping Core manager")
        if self.core_process or self.core_connected:
            self._logger.info("Sending shutdown request to Tribler Core")
            self.events_manager.shutting_down = True
            TriblerNetworkRequest("shutdown", lambda _: None, method="PUT", priority=QNetworkRequest.HighPriority)

    def on_core_finished(self, exit_code, exit_status):
        self.core_running = False
        self.core_finished = True
        if self.shutting_down:
            if self.should_quit_app_on_core_finished:
                self.quit_application()
        else:
            error_message = (
                f"The Tribler core has unexpectedly finished with exit code {exit_code} and status: {exit_status}!\n"
                f"Last core output: \n {self.last_core_stderr_output or self.last_core_stdout_output}"
            )
            self._logger.warning(error_message)

            # Stop the event manager loop if it is running
            if self.events_manager.connect_timer and self.events_manager.connect_timer.isActive():
                self.events_manager.connect_timer.stop()

            raise CoreCrashedError(error_message)

    def quit_application(self):
        if not self.quitting_app:
            self.quitting_app = True
            QApplication.quit()
