from __future__ import annotations

import logging
import webbrowser
from typing import List, Optional, TYPE_CHECKING

from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMessageBox

from tribler.core.components.key.key_component import KeyComponent
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.upgrade.upgrade import TriblerUpgrader
from tribler.core.upgrade.version_manager import TriblerVersion, VersionHistory
from tribler.gui.defs import BUTTON_TYPE_NORMAL
from tribler.gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler.gui.exceptions import UpgradeError
from tribler.gui.utilities import connect, format_size, tr

if TYPE_CHECKING:
    from tribler.gui.tribler_window import TriblerWindow


class StateDirUpgradeWorker(QObject):
    finished = pyqtSignal(object)
    status_update = pyqtSignal(str)
    stop_upgrade = pyqtSignal()

    def __init__(self, version_history: VersionHistory):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.version_history = version_history
        self._upgrade_interrupted = False
        connect(self.stop_upgrade, self._stop_upgrade)

    def upgrade_interrupted(self):
        return self._upgrade_interrupted

    def _stop_upgrade(self):
        self._upgrade_interrupted = True

    def _update_status_callback(self, text):
        self.status_update.emit(text)

    def run(self):
        try:
            self.logger.info('Run')
            self.upgrade_state_dir(
                self.version_history,
                update_status_callback=self._update_status_callback,
                interrupt_upgrade_event=self.upgrade_interrupted,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.exception(exc)
            self.finished.emit(exc)
        else:
            self.logger.info('Finished')
            self.finished.emit(None)

    def upgrade_state_dir(self, version_history: VersionHistory, update_status_callback=None,
                          interrupt_upgrade_event=None):
        self.logger.info(f'Upgrade state dir for {version_history}')
        # Before any upgrade, prepare a separate state directory for the update version so it does not
        # affect the older version state directory. This allows for safe rollback.
        version_history.fork_state_directory_if_necessary()
        version_history.save_if_necessary()
        state_dir = version_history.code_version.directory
        if not state_dir.exists():
            logging.info('State dir does not exist. Exit upgrade procedure.')
            return

        config = TriblerConfig.load(state_dir=state_dir, reset_config_on_error=True)
        channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)

        primary_private_key_path = config.state_dir / KeyComponent.get_private_key_filename(config)
        primary_public_key_path = config.state_dir / config.trustchain.ec_keypair_pubfilename
        primary_key = KeyComponent.load_or_create(primary_private_key_path, primary_public_key_path)
        secondary_key = KeyComponent.load_or_create(config.state_dir / config.trustchain.secondary_key_filename)

        upgrader = TriblerUpgrader(state_dir, channels_dir, primary_key, secondary_key,
                                   update_status_callback=update_status_callback,
                                   interrupt_upgrade_event=interrupt_upgrade_event)
        upgrader.run()


class UpgradeManager(QObject):
    """
    UpgradeManager is responsible for running the Tribler Upgrade process
    """

    upgrader_tick = pyqtSignal(str)
    upgrader_finished = pyqtSignal()

    def __init__(self, version_history: VersionHistory, last_supported_version: str = '7.5'):
        QObject.__init__(self, None)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.last_supported_version = last_supported_version
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

    @staticmethod
    def _show_message_box(title, body, icon, standard_buttons, default_button, additional_text=''):
        message_box = QMessageBox()
        message_box.setIcon(icon)
        message_box.setWindowTitle(title)
        message_box.setText(body)
        message_box.setInformativeText(additional_text)
        message_box.setStandardButtons(standard_buttons)
        message_box.setDefaultButton(default_button)
        return message_box.exec_()

    def should_cleanup_old_versions(self) -> List[TriblerVersion]:
        self._logger.info('Should cleanup old versions')

        disposable_versions = self.version_history.get_disposable_versions(skip_versions=2)
        if not disposable_versions:
            self._logger.info('No disposable versions. Exit cleanup procedure.')
            return []

        storage_info = ""
        claimable_storage = 0
        for version in disposable_versions:
            state_size = version.calc_state_size()
            claimable_storage += state_size
            storage_info += f"{version.version_str} \t {format_size(state_size)}\n"
        self._logger.info(f'Storage info: {storage_info}')
        # Show a question to the user asking if the user wants to remove the old data.
        title = tr("Delete state directories for old versions?")
        message_body = tr(
            "Press 'Yes' to remove state directories for older versions of Tribler "
            "and reclaim %s of storage space. "
            "Tribler used those directories during upgrades from previous versions. "
            "Now those directories can be safely deleted. \n\n"
            "If unsure, press 'No'. "
            "You will be able to remove those directories from the Settings->Data page later."
        ) % format_size(claimable_storage)

        user_choice = self._show_message_box(
            title,
            message_body,
            additional_text=storage_info,
            icon=QMessageBox.Question,
            standard_buttons=QMessageBox.No | QMessageBox.Yes,
            default_button=QMessageBox.Yes
        )
        if user_choice == QMessageBox.Yes:
            self._logger.info('User decided to delete old versions. Start cleanup procedure.')
            return disposable_versions
        return []

    def start(self):
        if self.version_history.last_run_version == self.version_history.code_version:
            self._logger.info('Last run version is the same as the current version. Skip upgrade.')
            self.upgrader_finished.emit()
            return

        self._logger.info('Start upgrade process')
        last_version = self.version_history.last_run_version
        if last_version and last_version.is_ancient(self.last_supported_version):
            self._logger.info('Ancient version detected. Quitting Tribler.')
            self._show_message_box(
                tr("Ancient version detected"),
                body=tr("You are running an old version of Tribler. "
                        "It is not possible to upgrade from this version to the most recent one."
                        "Please do upgrade incrementally (download Tribler 7.10, upgrade, "
                        "then download the most recent one, upgrade)."),
                icon=QMessageBox.Warning,
                standard_buttons=QMessageBox.Yes,
                default_button=QMessageBox.Yes
            )
            QApplication.quit()
            return

        versions_to_delete = self.should_cleanup_old_versions()
        if versions_to_delete:
            for version in versions_to_delete:
                version.delete_state()
        # Determine if we have to notify the user to wait for the directory fork to finish
        if self.version_history.code_version.should_be_copied:
            self.upgrader_tick.emit(tr('Backing up state directory, please wait'))

        self._upgrade_worker = StateDirUpgradeWorker(self.version_history)
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
