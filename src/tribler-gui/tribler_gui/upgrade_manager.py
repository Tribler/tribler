import logging
import sys
from typing import List

from PyQt5.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal
from PyQt5.QtWidgets import QMessageBox

from tribler_common.osutils import get_root_state_directory
from tribler_common.version_manager import TriblerVersion, VersionHistory

from tribler_gui.utilities import connect, format_size, tr


class UpgradeManager(QObject):
    """
    UpgradeManager is responsible for running the Tribler Upgrade process
    """

    upgrader_tick = pyqtSignal(str)
    upgrader_finished = pyqtSignal()

    def __init__(self):
        QObject.__init__(self, None)

        root_state_dir = get_root_state_directory()
        self.version_history = VersionHistory(root_state_dir)
        self._logger = logging.getLogger(self.__class__.__name__)

        self.upgrade_process = None

    def on_upgrade_read_ready(self):
        raw_output = bytes(self.upgrade_process.readAll())
        decoded_output = raw_output.decode(errors="replace")
        text = decoded_output.strip()
        self.upgrader_tick.emit(text)
        print(decoded_output.strip())  # noqa: T001

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

    def should_cleanup_old_versions(self) -> List[TriblerVersion]:
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

    def start(self):
        versions_to_delete = self.should_cleanup_old_versions()
        if versions_to_delete:
            for version in versions_to_delete:
                version.delete_state()

        # Determine if we have to notify the user to wait for the directory fork to finish
        if self.version_history.code_version.should_be_copied:
            self.upgrader_tick.emit(tr('Backing up state directory, please wait'))

        upg_env = QProcessEnvironment.systemEnvironment()
        upg_args = sys.argv + ['--upgrade']

        self.upgrade_process = QProcess()
        self.upgrade_process.setProcessEnvironment(upg_env)
        self.upgrade_process.setReadChannel(QProcess.StandardOutput)
        self.upgrade_process.setProcessChannelMode(QProcess.MergedChannels)
        connect(self.upgrade_process.readyRead, self.on_upgrade_read_ready)
        connect(self.upgrade_process.finished, lambda *_: self.upgrader_finished.emit())
        self.upgrade_process.start(sys.executable, upg_args)

    def stop_upgrade(self):
        self.upgrade_process.terminate()
