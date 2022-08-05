import logging
import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal
from PyQt5.QtNetwork import QNetworkRequest

from tribler.gui.app_manager import AppManager
from tribler.gui.event_request_manager import EventRequestManager
from tribler.gui.exceptions import CoreCrashedError
from tribler.gui.tribler_request_manager import TriblerNetworkRequest
from tribler.gui.utilities import connect


class CoreManager(QObject):
    """
    The CoreManager is responsible for managing the Tribler core (starting/stopping). When we are running the GUI tests,
    a fake API will be started.
    """

    def __init__(self, root_state_dir: Path, api_port: int, api_key: str, app_manager: AppManager,
                 events_manager: EventRequestManager):
        QObject.__init__(self, None)

        self._logger = logging.getLogger(self.__class__.__name__)
        self.app_manager = app_manager
        self.root_state_dir = root_state_dir
        self.core_process: Optional[QProcess] = None
        self.api_port = api_port
        self.api_key = api_key
        self.events_manager = events_manager

        self.upgrade_manager = None
        self.core_args = None
        self.core_env = None

        self.core_started = False
        self.core_running = False
        self.core_connected = False
        self.shutting_down = False
        self.core_finished = False

        self.should_quit_app_on_core_finished = False

        self.use_existing_core = True
        self.last_core_stdout_output: str = ''
        self.last_core_stderr_output: str = ''

        connect(self.events_manager.core_connected, self.on_core_connected)

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
            if getattr(sys, 'frozen', False):
                # remove duplicate tribler.exe from core_args when running complied binary
                # https://pyinstaller.org/en/v3.3.1/runtime-information.html#using-sys-executable-and-sys-argv-0
                core_args = core_args[1:]

        self.core_process = QProcess()
        self.core_process.setProcessEnvironment(core_env)
        self.core_process.setProcessChannelMode(QProcess.SeparateChannels)
        connect(self.core_process.started, self.on_core_started)
        connect(self.core_process.readyReadStandardOutput, self.on_core_stdout_read_ready)
        connect(self.core_process.readyReadStandardError, self.on_core_stderr_read_ready)
        connect(self.core_process.finished, self.on_core_finished)
        self._logger.info(f'Start Tribler core process {sys.executable} with arguments: {core_args}')
        self.core_process.start(sys.executable, core_args)

    def on_core_started(self):
        self.core_started = True
        self.core_running = True

    def on_core_stdout_read_ready(self):
        if self.app_manager.quitting_app:
            # Reading at this stage can lead to the error "wrapped C/C++ object of type QProcess has been deleted"
            return

        raw_output = bytes(self.core_process.readAllStandardOutput())
        self.last_core_stdout_output = self.decode_raw_core_output(raw_output).strip()

        try:
            print(self.last_core_stdout_output)  # print core output # noqa: T001
        except OSError:
            # Possible reason - cannot write to stdout as it was already closed during the application shutdown
            pass

    def on_core_stderr_read_ready(self):
        if self.app_manager.quitting_app:
            # Reading at this stage can lead to the error "wrapped C/C++ object of type QProcess has been deleted"
            return

        raw_output = bytes(self.core_process.readAllStandardError())
        self.last_core_stderr_output = self.decode_raw_core_output(raw_output).strip()

        try:
            print(self.last_core_stderr_output, file=sys.stderr)  # print core output # noqa: T001
        except OSError:
            # Possible reason - cannot write to stdout as it was already closed during the application shutdown
            pass

    def stop(self, quit_app_on_core_finished=True):
        if quit_app_on_core_finished:
            self.should_quit_app_on_core_finished = True

        if self.shutting_down:
            return

        self.shutting_down = True
        self._logger.info("Stopping Core manager")

        need_to_shutdown_core = (self.core_process or self.core_connected) and not self.core_finished
        if need_to_shutdown_core:
            self.events_manager.shutting_down = True

            def shutdown_request_processed(response):
                self._logger.info(f"Shutdown request was processed by Core. Response: {response}")

            def send_shutdown_request(initial=False):
                if initial:
                    self._logger.info("Sending shutdown request to Tribler Core")
                else:
                    self._logger.warning("Re-sending shutdown request to Tribler Core")

                TriblerNetworkRequest("shutdown", shutdown_request_processed, method="PUT",
                                      priority=QNetworkRequest.HighPriority, on_cancel=send_shutdown_request)

            send_shutdown_request(initial=True)

        elif self.should_quit_app_on_core_finished:
            self._logger.info('Core finished, quitting GUI application')
            self.app_manager.quit_application()

    def on_core_finished(self, exit_code, exit_status):
        self.core_running = False
        self.core_finished = True
        if self.shutting_down:
            if self.should_quit_app_on_core_finished:
                self.app_manager.quit_application()
        else:
            error_message = (
                f"The Tribler core has unexpectedly finished with exit code {exit_code} and status: {exit_status}!\n"
                f"Last core output: \n {self.last_core_stderr_output or self.last_core_stdout_output}"
            )
            self._logger.warning(error_message)

            if not self.app_manager.quitting_app:
                # Stop the event manager loop if it is running
                if self.events_manager.connect_timer and self.events_manager.connect_timer.isActive():
                    self.events_manager.connect_timer.stop()

            raise CoreCrashedError(error_message)

    @staticmethod
    def decode_raw_core_output(output: bytes) -> str:
        try:
            # Let's optimistically try to decode from UTF8.
            # If it is not UTF8, we should get UnicodeDecodeError "invalid continuation byte".
            return output.decode('utf-8')
        except UnicodeDecodeError:
            # It may be hard to guess the real encoding on some systems,
            # but by using the "backslashreplace" error handler we can keep all the received data.
            return output.decode('ascii', errors='backslashreplace')
