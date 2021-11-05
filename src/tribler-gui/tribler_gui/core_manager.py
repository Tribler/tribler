import logging
import os
import sys
import time
from typing import List

from PyQt5.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWidgets import QApplication, QMessageBox

from tribler_common.osutils import get_root_state_directory
from tribler_common.utilities import is_frozen
from tribler_common.version_manager import TriblerVersion, VersionHistory

from tribler_gui.event_request_manager import EventRequestManager
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import connect, format_size, get_base_path, tr

START_FAKE_API = False
SKIP_VERSION_CLEANUP = os.environ.get("SKIP_VERSION_CLEANUP", "FALSE").lower() == "true"


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

        root_state_dir = get_root_state_directory()
        self.version_history = VersionHistory(root_state_dir)

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

    def start(self, core_args=None, core_env=None):
        """
        First test whether we already have a Tribler process listening on port <CORE_API_PORT>.
        If so, use that one and don't start a new, fresh session.
        """

        def on_request_error(_):
            self.use_existing_core = False
            self.start_tribler_core(core_args=core_args, core_env=core_env)

        versions_to_delete = self.should_cleanup_old_versions()
        if versions_to_delete:
            for version in versions_to_delete:
                version.delete_state()

        # Connect to the events manager only after the cleanup is done
        self.events_manager.connect()
        connect(self.events_manager.reply.error, on_request_error)

        # Determine if we have notify the user to wait for the directory fork to finish
        if self.version_history.code_version.should_be_copied:
            # There is going to be a directory fork, so we extend the core connection timeout and notify the user
            self.events_manager.remaining_connection_attempts = 1200
            self.events_manager.change_loading_text.emit("Copying data from previous Tribler version, please wait")

    def should_cleanup_old_versions(self) -> List[TriblerVersion]:
        # Skip old version check popup when running fake core, eg. during GUI tests
        # or during deployment tests since it blocks the tests with a popup dialog
        if START_FAKE_API or SKIP_VERSION_CLEANUP:
            return []

        if self.version_history.last_run_version == self.version_history.code_version:
            return []

        disposable_versions = self.version_history.get_disposable_versions(skip_versions=2)
        if not disposable_versions:
            return []

        storage_info = ""
        claimable_storage = 0
        for version in disposable_versions:
            state_size = version.calc_state_size()
            claimable_storage += state_size
            storage_info += f"{version.version_str} \t {format_size(state_size)}\n"

        # Show a question to the user asking if the user wants to remove the old data.
        title = "Delete state directories for old versions?"
        message_body = tr(
            "Press 'Yes' to remove state directories for older versions of Tribler "
            "and reclaim %s of storage space. "
            "Tribler used those directories during upgrades from previous versions. "
            "Now those directories can be safely deleted. \n\n"
            "If unsure, press 'No'. "
            "You will be able to remove those directories from the Settings->Data page later."
        ) % format_size(claimable_storage)

        user_choice = self._show_question_box(title, message_body, storage_info, default_button=QMessageBox.Yes)
        if user_choice == QMessageBox.Yes:
            return disposable_versions
        return []

    def _show_question_box(self, title, body, additional_text, default_button=None):
        message_box = QMessageBox()
        message_box.setIcon(QMessageBox.Question)
        message_box.setWindowTitle(title)
        message_box.setText(body)
        message_box.setInformativeText(additional_text)
        message_box.setStandardButtons(QMessageBox.No | QMessageBox.Yes)
        if default_button:
            message_box.setDefaultButton(default_button)
        return message_box.exec_()

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
