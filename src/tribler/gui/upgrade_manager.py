from __future__ import annotations

import logging
import webbrowser
from typing import List, Optional, TYPE_CHECKING

from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox

from tribler.core.upgrade.version_manager import TriblerVersion, VersionHistory
from tribler.gui.defs import BUTTON_TYPE_NORMAL
from tribler.gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler.gui.exceptions import UpgradeError
from tribler.gui.utilities import connect, format_size, tr
from tribler.run_tribler_upgrader import upgrade_state_dir

if TYPE_CHECKING:
    from tribler.gui.tribler_window import TriblerWindow


class StateDirUpgradeWorker(QObject):
    finished = pyqtSignal(object)
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
        try:
            self._upgrade_state_dir(
                self.root_state_dir,
                update_status_callback=self._update_status_callback,
                interrupt_upgrade_event=self.upgrade_interrupted,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.finished.emit(exc)
        else:
            self.finished.emit(None)


class UpgradeManager(QObject):
    """
    UpgradeManager is responsible for running the Tribler Upgrade process
    """

    upgrader_tick = pyqtSignal(str)
    upgrader_finished = pyqtSignal()

    def __init__(self, version_history: VersionHistory):
        QObject.__init__(self, None)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.version_history = version_history
        self.new_version_dialog_postponed: bool = False
        self.dialog: Optional[ConfirmationDialog] = None

        self._upgrade_worker = None
        self._upgrade_thread = None

    def on_new_version_available(self, tribler_window: TriblerWindow, new_version: str):
        last_reported_version = str(tribler_window.gui_settings.value('last_reported_version'))
        if new_version == last_reported_version:
            return

        if self.new_version_dialog_postponed or self.dialog:
            return

        self.dialog = ConfirmationDialog(
            tribler_window,
            tr("New version available"),
            tr("Version %s of Tribler is available. Do you want to visit the website to download the newest version?")
            % new_version,
            [(tr("IGNORE"), BUTTON_TYPE_NORMAL), (tr("LATER"), BUTTON_TYPE_NORMAL), (tr("OK"), BUTTON_TYPE_NORMAL)],
        )

        def on_button_clicked(click_result: int):
            self.dialog.close_dialog()
            self.dialog = None

            if click_result == 0:  # ignore
                tribler_window.gui_settings.setValue("last_reported_version", new_version)
            elif click_result == 1:  # later
                self.new_version_dialog_postponed = True
            elif click_result == 2:  # ok
                webbrowser.open("https://tribler.org")

        connect(self.dialog.button_clicked, on_button_clicked)
        self.dialog.show()

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

        self._upgrade_worker._upgrade_state_dir = upgrade_state_dir  # pylint: disable=W0212
        self._upgrade_thread = QThread()
        self._upgrade_worker.moveToThread(self._upgrade_thread)

        # ACHTUNG!!! _upgrade_thread.started signal MUST be connected using the original "connect" method!
        # Otherwise, if we use our own connect(x,y) wrapper, Tribler just freezes
        self._upgrade_thread.started.connect(self._upgrade_worker.run)

        # ACHTUNG!!! the following signals cannot be properly handled by our "connect" method.
        # These must be connected directly to prevent problems with disconnecting and thread handling.
        self._upgrade_worker.status_update.connect(self.upgrader_tick.emit)
        self._upgrade_worker.finished.connect(self.on_worker_finished)

        self._upgrade_thread.start()

    def on_worker_finished(self, exc):
        self._upgrade_thread.deleteLater()
        self._upgrade_thread.quit()
        self._upgrade_worker.deleteLater()
        if exc is None:
            self.upgrader_finished.emit()
        else:
            raise UpgradeError(f'{exc.__class__.__name__}: {exc}') from exc

    def stop_upgrade(self):
        self._upgrade_worker.stop_upgrade.emit()
