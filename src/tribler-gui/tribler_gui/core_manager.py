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

    tribler_stopped = pyqtSignal()

    def __init__(self, root_state_dir, api_port, api_key, error_handler):
        QObject.__init__(self, None)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.root_state_dir = root_state_dir
        self.core_process = None
        self.api_port = api_port
        self.api_key = api_key
        self.events_manager = EventRequestManager(self.api_port, self.api_key, error_handler)

        self.shutting_down = False
        self.should_stop_on_shutdown = False
        self.use_existing_core = True
        self.is_core_running = False
        self.last_core_stdout_output: str = ''
        self.last_core_stderr_output: str = ''

        connect(self.events_manager.tribler_started, self._set_core_running)

    def _set_core_running(self, _):
        self.is_core_running = True

    def on_core_stdout_read_ready(self):
        raw_output = bytes(self.core_process.readAllStandardOutput())
        self.last_core_stdout_output = raw_output.decode("utf-8").strip()
        try:
            print(self.last_core_stdout_output)  # print core output # noqa: T001
        except OSError:
            # Possible reason - cannot write to stdout as it was already closed during the application shutdown
            if not self.shutting_down:
                raise

    def on_core_stderr_read_ready(self):
        raw_output = bytes(self.core_process.readAllStandardError())
        self.last_core_stderr_output = raw_output.decode("utf-8").strip()
        try:
            print(self.last_core_stderr_output, file=sys.stderr)  # print core output # noqa: T001
        except OSError:
            # Possible reason - cannot write to stdout as it was already closed during the application shutdown
            if not self.shutting_down:
                raise

    def on_core_finished(self, exit_code, exit_status):
        if self.shutting_down and self.should_stop_on_shutdown:
            self.on_finished()
        elif not self.shutting_down and exit_code != 0:
            # Stop the event manager loop if it is running
            if self.events_manager.connect_timer and self.events_manager.connect_timer.isActive():
                self.events_manager.connect_timer.stop()

            exception_message = (
                f"The Tribler core has unexpectedly finished with exit code {exit_code} and status: {exit_status}!\n"
                f"Last core output: \n {self.last_core_stderr_output or self.last_core_stdout_output}"
            )

            raise CoreCrashedError(exception_message)

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
            core_env.insert("CORE_API_KEY", self.api_key)
            core_env.insert("TSTATEDIR", str(self.root_state_dir))
        if not core_args:
            core_args = sys.argv + ['--core']

        self.core_process = QProcess()
        self.core_process.setProcessEnvironment(core_env)
        self.core_process.setProcessChannelMode(QProcess.SeparateChannels)
        connect(self.core_process.readyReadStandardOutput, self.on_core_stdout_read_ready)
        connect(self.core_process.readyReadStandardError, self.on_core_stderr_read_ready)
        connect(self.core_process.finished, self.on_core_finished)
        self.core_process.start(sys.executable, core_args)

    def stop(self, stop_app_on_shutdown=True):
        self._logger.info("Stopping Core manager")
        if self.core_process or self.is_core_running:
            self._logger.info("Sending shutdown request to Tribler Core")
            self.events_manager.shutting_down = True
            TriblerNetworkRequest("shutdown", lambda _: None, method="PUT", priority=QNetworkRequest.HighPriority)

            if stop_app_on_shutdown:
                self.should_stop_on_shutdown = True

    def on_finished(self):
        self.tribler_stopped.emit()
        if self.shutting_down:
            QApplication.quit()
