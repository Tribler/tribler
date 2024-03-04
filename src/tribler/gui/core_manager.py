from __future__ import annotations

import logging
import os
import re
import sys
import time
from collections import deque
from pathlib import Path
from typing import Optional, List

from PyQt5.QtCore import QObject, QProcess, QProcessEnvironment, QTimer
from PyQt5.QtNetwork import QNetworkRequest

from tribler.core.utilities.exit_codes import get_error_name
from tribler.core.utilities.exit_codes.tribler_exit_codes import EXITCODE_DATABASE_IS_CORRUPTED, \
    EXITCODE_ANOTHER_CORE_PROCESS_IS_RUNNING
from tribler.core.utilities.process_manager import ProcessManager, ProcessKind, TriblerProcess
from tribler.gui import gui_sentry_reporter
from tribler.gui.app_manager import AppManager
from tribler.gui.core_restart_logs import CoreRestartLog
from tribler.gui.event_request_manager import EventRequestManager
from tribler.gui.exceptions import CoreConnectTimeoutError, CoreCrashedError
from tribler.gui.network.request_manager import SHUTDOWN_ENDPOINT, request_manager
from tribler.gui.utilities import connect, show_message_corrupted_database_was_fixed

API_PORT_CHECK_INTERVAL = 100  # 0.1 seconds between attempts to retrieve Core API port
API_PORT_CHECK_TIMEOUT = 120  # Stop trying to determine API port after this number of seconds

CORE_OUTPUT_DEQUE_LENGTH = 10
CORE_RESTART_TRACK_COUNT = 3


class CoreManager(QObject):
    """
    The CoreManager is responsible for managing the Tribler core (starting/stopping). When we are running the GUI tests,
    a fake API will be started.
    """

    def __init__(self, root_state_dir: Path, api_port: Optional[int], api_key: str,
                 app_manager: AppManager, process_manager: ProcessManager, events_manager: EventRequestManager):
        QObject.__init__(self, None)

        self._logger = logging.getLogger(self.__class__.__name__)
        self.app_manager = app_manager
        self.root_state_dir = root_state_dir
        self.core_process: Optional[QProcess] = None
        self.api_port = api_port
        self.api_key = api_key

        self.process_manager = process_manager
        self.check_core_api_port_timer = QTimer()
        self.check_core_api_port_timer.setSingleShot(True)
        connect(self.check_core_api_port_timer.timeout, self.check_core_api_port)

        self.events_manager = events_manager

        self.upgrade_manager = None
        self.core_args = None
        self.core_env = None

        self.core_started = False
        self.core_running = False
        self.core_connected = False
        self.shutting_down = False
        self.core_finished = False

        self.is_restarting = False
        self.core_process_started_at: Optional[int] = None
        self.wait_for_finished_to_restart_core = False
        self.should_quit_app_on_core_finished = False

        self.use_existing_core = False
        self.last_core_stdout_output: deque = deque(maxlen=CORE_OUTPUT_DEQUE_LENGTH)
        self.last_core_stderr_output: deque = deque(maxlen=CORE_OUTPUT_DEQUE_LENGTH)

        connect(self.events_manager.core_connected, self.on_core_connected)

        # Core restart log that tracks when core process was restarted.
        self.core_restart_logs: List[CoreRestartLog] = []

    def on_core_connected(self, _):
        if self.core_finished:
            self._logger.warning('Core connected after the core process is already finished')
            return

        if self.shutting_down:
            self._logger.warning('Core connected after the shutting down is already started')
            return

        self.core_connected = True

    def start(self, core_args=None, core_env=None, upgrade_manager=None, run_core=True):
        """
        First test whether we already have a Tribler process listening on port <CORE_API_PORT>.
        If so, use that one and don't start a new, fresh Core.
        """
        if run_core:
            self.core_args = core_args
            self.core_env = core_env
            self.upgrade_manager = upgrade_manager

        # Connect to the events manager
        if self.events_manager.api_port:
            self.events_manager.connect_to_core(
                reschedule_on_err=False  # do not retry if tribler Core is not running yet
            )
            connect(self.events_manager.reply.error, self.do_upgrade_and_start_core)
        else:
            self.do_upgrade_and_start_core()

    def do_upgrade_and_start_core(self, _=None):
        if self.upgrade_manager:
            # Start Tribler Upgrader. When it finishes, start Tribler Core
            connect(self.upgrade_manager.upgrader_finished, self.start_tribler_core)
            self.upgrade_manager.start()
        else:
            self.start_tribler_core()

    def start_tribler_core(self):
        # reset the status flags
        self.use_existing_core = False
        self.is_restarting = False
        self.core_started = False
        self.core_running = False
        self.core_connected = False
        self.core_finished = False

        core_env = self.core_env
        if not core_env:
            core_env = QProcessEnvironment.systemEnvironment()
            core_env.insert("CORE_API_KEY", self.api_key)
            core_env.insert("TSTATEDIR", str(self.root_state_dir))
            core_env.insert("TRIBLER_GUI_PID", str(os.getpid()))

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
        self.core_process.start(sys.executable, core_args)

    def on_core_started(self):
        self._logger.info("Core process started")
        self.core_started = True
        self.core_process_started_at = time.time()
        self.core_running = True

        self.log_core_started()
        self.check_core_api_port()

    def log_core_started(self):
        core_restart_log = CoreRestartLog.current(self.core_process.pid())
        self.core_restart_logs.append(core_restart_log)

    def log_core_finished(self, exit_code: int, exit_status: str):
        if self.core_restart_logs:
            self.core_restart_logs[-1].log_finished(exit_code, exit_status)

    def log_core_restart_triggered(self):
        if self.core_restart_logs:
            self.core_restart_logs[-1].log_restart_triggered()

    def core_restarted_frequently(self):
        return len([log for log in self.core_restart_logs if log.is_recent_log()]) > CORE_RESTART_TRACK_COUNT

    def check_core_api_port(self, *args):
        """
        Determines the actual REST API port of the Core process.

        This function is first executed from the `on_core_started` after the physical Core process starts and then
        repeatedly executed after API_PORT_CHECK_INTERVAL milliseconds until it retrieves the REST API port value from
        the Core process. Shortly after the Core process starts, it adds itself to a process database. At that moment,
        the api_port value in the database is not specified yet for the Core process. Then the Core REST manager finds
        a suitable port and sets the api_port value in the process database. After that, the `check_core_api_port`
        method retrieves the api_port value from the database and asks EventRequestManager to connect to that port.
        """
        if not self.use_existing_core and (not self.core_running or self.core_connected or self.shutting_down):
            return

        core_process = self.get_core_process()
        if core_process is not None and core_process.api_port:
            api_port = core_process.api_port
            self._logger.info(f"Got REST API port value from the Core process: {api_port}")
            if api_port != self.api_port:
                self.api_port = api_port
                request_manager.set_api_port(api_port)
                self.events_manager.set_api_port(api_port)

            # Previously it was necessary to reschedule on error because `events_manager.connect_to_core()` was executed
            # before the REST API was available, so it retried until the REST API was ready. Now the API is ready
            # to use when we can read the api_port value from the database, so now we can call connect_to_core
            # with reschedule_on_err=False. I kept reschedule_on_err=True just for reinsurance.
            self.events_manager.connect_to_core(reschedule_on_err=True)

        elif time.time() - self.core_process_started_at > API_PORT_CHECK_TIMEOUT:
            raise CoreConnectTimeoutError(f"Can't get Core API port value within {API_PORT_CHECK_TIMEOUT} seconds")
        else:
            self.check_core_api_port_timer.start(API_PORT_CHECK_INTERVAL)

    def get_core_process(self) -> Optional[TriblerProcess]:
        if self.use_existing_core:
            return self.process_manager.get_primary_process(ProcessKind.Core)
        return self.process_manager.current_process.get_core_process()

    def on_core_stdout_read_ready(self):
        if self.app_manager.quitting_app:
            # Reading at this stage can lead to the error "wrapped C/C++ object of type QProcess has been deleted"
            return

        raw_output = bytes(self.core_process.readAllStandardOutput())
        output = self.decode_raw_core_output(raw_output).strip()
        self.last_core_stdout_output.append(output)
        gui_sentry_reporter.add_breadcrumb(
            message=output,
            category='CORE_STDOUT',
            level='info'
        )

        try:
            print(output)  # print core output # noqa: T001
        except OSError:
            # Possible reason - cannot write to stdout as it was already closed during the application shutdown
            pass

    def on_core_stderr_read_ready(self):
        if self.app_manager.quitting_app:
            # Reading at this stage can lead to the error "wrapped C/C++ object of type QProcess has been deleted"
            return

        raw_output = bytes(self.core_process.readAllStandardError())
        output = self.decode_raw_core_output(raw_output).strip()
        self.last_core_stderr_output.append(output)
        gui_sentry_reporter.add_breadcrumb(
            message=output,
            category='CORE_STDERR',
            level='error'
        )

        try:
            print(output, file=sys.stderr)  # print core output # noqa: T001
        except OSError:
            # Possible reason - cannot write to stdout as it was already closed during the application shutdown
            pass

    def shutdown_request_processed(self, response):
        self._logger.info(f"{SHUTDOWN_ENDPOINT} request was processed by Core. Response: {response}")

    def send_shutdown_request(self):
        self._logger.info(f"Sending {SHUTDOWN_ENDPOINT} request to Tribler Core")

        request = request_manager.put(
            endpoint=SHUTDOWN_ENDPOINT,
            on_success=self.shutdown_request_processed,
            priority=QNetworkRequest.HighPriority
        )
        if request:
            request.cancellable = False

    def stop(self, quit_app_on_core_finished=True):
        if quit_app_on_core_finished:
            self.should_quit_app_on_core_finished = True

        if self.shutting_down:
            return

        self.shutting_down = True
        self._logger.info("Stopping Core manager")

        if self.core_process and not self.core_finished:
            if not self.core_connected:
                # If Core is not connected via events_manager it also most probably cannot process API requests.
                self._logger.warning('Core is not connected during the CoreManager shutdown, killing it...')
                self.kill_core_process()
                return

            self.events_manager.shutting_down = True
            self.send_shutdown_request()

        elif self.should_quit_app_on_core_finished:
            self._logger.info('Core is not running, quitting GUI application')
            self.app_manager.quit_application()

    def restart_core(self):
        """
        The job of this method is to ensure that core process is terminated either by calling shutdown endpoint
        if the core is connected, otherwise, kill the core process.

        In case the core process has already finished (is terminated) as indicated by flag self.core_finished, in that
        case, a new core process can be directed started.

        Otherwise, core process is tried to be terminated and self.is_restarting flag is set. This flag makes sure to
        restart the core again on processing on_finished signal of previous dead core process.

        It is done like this to avoid blocking wait of core process finishing (by waiting on
        self.core_process.waitForFinished()) and restarting a new core process.
        """
        if self.is_restarting:
            return

        self._logger.info("Restarting Core Process ...")
        self.is_restarting = True

        self.log_core_restart_triggered()

        if self.core_finished:
            self.start_tribler_core()

        elif self.core_process:
            self.wait_for_finished_to_restart_core = True
            if self.core_connected:
                self.events_manager.shutting_down = False
                self.send_shutdown_request()
            else:
                # If Core is not connected via events_manager it also most probably cannot process API requests.
                self._logger.warning('Core is not connected during the CoreManager shutdown, killing it...')
                self.kill_core_process()

    def kill_core_process(self):
        if not self.core_process or self.use_existing_core:
            self._logger.warning("Cannot kill the Core process as it is not initialized")

        self.core_process.kill()
        finished = self.core_process.waitForFinished()
        if not finished:
            self._logger.error('Cannot kill the core process')

    def get_last_core_output(self, quoted=True):
        output = ''.join(self.last_core_stderr_output) or ''.join(self.last_core_stdout_output)
        if quoted:
            output = re.sub(r'^', '> ', output, flags=re.MULTILINE)
        return output

    @staticmethod
    def error_code_to_hex(error_code: int) -> str:
        """Convert a signed integer error code to a hexadecimal string."""
        v = error_code & (2 ** 32 - 1)
        return hex(v)

    @staticmethod
    def format_error_message(exit_code: int, exit_status: int) -> str:
        hex_error_code = CoreManager.error_code_to_hex(exit_code)
        message = f"The Tribler core has unexpectedly finished with exit code {exit_code} ({hex_error_code}) " \
                  f"and status: {exit_status}."
        if exit_code == 1:
            string_error = "Application error"
        else:
            try:
                string_error = get_error_name(exit_code)
            except ValueError:
                # On platforms where strerror() returns NULL when given an unknown error number, ValueError is raised.
                string_error = 'unknown error number'
        message += f'\n\nError message: {string_error}'
        return message

    def on_core_finished(self, exit_code, exit_status):
        self._logger.info(f"Core process finished with exit-code: {exit_code} and status: {exit_status}")
        self.log_core_finished(exit_code, exit_status)

        self.core_running = False
        self.core_connected = False
        if exit_code == EXITCODE_DATABASE_IS_CORRUPTED:
            self._logger.error(f"Core process crashed with code {exit_code}: the database is corrupted. "
                               "Restarting Core...")
            self.start_tribler_core()
            show_message_corrupted_database_was_fixed()
            return

        if exit_code == EXITCODE_ANOTHER_CORE_PROCESS_IS_RUNNING:
            self._logger.error(f"Core process crashed with code {exit_code}: Another Core process is running.")
            self.use_existing_core = True
            self.check_core_api_port()
            return

        self.core_finished = True
        if self.shutting_down:
            if self.should_quit_app_on_core_finished:
                self.app_manager.quit_application()

        elif self.wait_for_finished_to_restart_core:
            self.start_tribler_core()
            self.wait_for_finished_to_restart_core = False

        else:
            error_message = self.format_error_message(exit_code, exit_status)
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
