import logging
from typing import List

from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox

from tribler_common.version_manager import TriblerVersion, VersionHistory

from tribler_gui.utilities import connect, format_size, tr


class StateDirUpgradeWorker(QObject):
    finished = pyqtSignal()
    status_update = pyqtSignal(str)
    stop_upgrade = pyqtSignal()

    def __init__(self, root_state_dir):
        super().__init__()
        self.root_state_dir = root_state_dir
        self._upgrade_interrupted = False
        connect(self.stop_upgrade, self._stop_upgrade)
        self._upgrade_state_dir = None

    def upgrade_interrupted(self):
        return self._upgrade_interrupted

    def _stop_upgrade(self):
        self._upgrade_interrupted = True

    def _update_status_callback(self, text):
        self.status_update.emit(text)

    def run(self):
        self._upgrade_state_dir(
            self.root_state_dir,
            update_status_callback=self._update_status_callback,
            interrupt_upgrade_event=self.upgrade_interrupted,
        )
        self.finished.emit()


class UpgradeManager(QObject):
    """
    UpgradeManager is responsible for running the Tribler Upgrade process
    """

    upgrader_tick = pyqtSignal(str)
    upgrader_finished = pyqtSignal()

    def __init__(self, version_history: VersionHistory):
        QObject.__init__(self, None)

        self.version_history = version_history
        self._logger = logging.getLogger(self.__class__.__name__)

        self._upgrade_worker = None
        self._upgrade_thread = None

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

        self._upgrade_worker = StateDirUpgradeWorker(self.version_history.root_state_dir)
        # We import it here because it is safer to do it in the main thread
        from run_tribler_upgrader import upgrade_state_dir  # pylint: disable=C0415

        self._upgrade_worker._upgrade_state_dir = upgrade_state_dir  # pylint: disable=W0212
        self._upgrade_thread = QThread()
        self._upgrade_worker.moveToThread(self._upgrade_thread)

        # ACHTUNG!!! _upgrade_thread.started signal MUST be connected using the original "connect" method!
        # Otherwise, if we use our own connect(x,y) wrapper, Tribler just freezes
        self._upgrade_thread.started.connect(self._upgrade_worker.run)

        # ACHTUNG!!! the following signals cannot be properly handled by our "connect" method.
        # These must be connected directly to prevent problems with disconnecting and thread handling.
        self._upgrade_worker.status_update.connect(self.upgrader_tick.emit)
        self._upgrade_thread.finished.connect(self._upgrade_thread.deleteLater)
        self._upgrade_worker.finished.connect(self._upgrade_thread.quit)
        self._upgrade_worker.finished.connect(self.upgrader_finished.emit)
        self._upgrade_worker.finished.connect(self._upgrade_worker.deleteLater)

        self._upgrade_thread.start()

    def stop_upgrade(self):
        self._upgrade_worker.stop_upgrade.emit()
