import os

from PyQt5 import uic
from PyQt5.QtCore import QDir, pyqtSignal
from PyQt5.QtWidgets import QAction, QFileDialog, QSizePolicy, QTreeWidgetItem

from tribler_gui.defs import BUTTON_TYPE_NORMAL
from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.dialogs.dialogcontainer import DialogContainer
from tribler_gui.tribler_action_menu import TriblerActionMenu
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import connect, get_ui_file_path, is_dir_writable, tr


class DownloadFileTreeWidgetItem(QTreeWidgetItem):
    def __init__(self, parent):
        QTreeWidgetItem.__init__(self, parent)


class CreateTorrentDialog(DialogContainer):

    create_torrent_notification = pyqtSignal(dict)
    add_to_channel_selected = pyqtSignal(str)

    def __init__(self, parent):
        DialogContainer.__init__(self, parent)

        uic.loadUi(get_ui_file_path('createtorrentdialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        connect(self.dialog_widget.btn_cancel.clicked, self.close_dialog)
        connect(self.dialog_widget.create_torrent_choose_files_button.clicked, self.on_choose_files_clicked)
        connect(self.dialog_widget.create_torrent_choose_dir_button.clicked, self.on_choose_dir_clicked)
        connect(self.dialog_widget.btn_create.clicked, self.on_create_clicked)
        connect(self.dialog_widget.create_torrent_files_list.customContextMenuRequested, self.on_right_click_file_item)
        self.dialog_widget.create_torrent_files_list.clear()
        connect(self.dialog_widget.save_directory_chooser.clicked, self.on_select_save_directory)
        self.dialog_widget.edit_channel_create_torrent_progress_label.setText("")
        self.dialog_widget.file_export_dir.setText(os.path.expanduser("~"))
        self.dialog_widget.adjustSize()

        self.on_main_window_resize()

        self.name = None
        self.rest_request1 = None
        self.rest_request2 = None

    def close_dialog(self, checked=False):
        if self.rest_request1:
            self.rest_request1.cancel_request()
        if self.rest_request2:
            self.rest_request2.cancel_request()

        super().close_dialog()

    def on_choose_files_clicked(self, checked):
        filenames, _ = QFileDialog.getOpenFileNames(self.window(), tr("Please select the files"), QDir.homePath())

        for filename in filenames:
            self.dialog_widget.create_torrent_files_list.addItem(filename)

    def on_choose_dir_clicked(self, checked):
        chosen_dir = QFileDialog.getExistingDirectory(
            self.window(), tr("Please select the directory containing the files"), "", QFileDialog.ShowDirsOnly
        )

        if not chosen_dir:
            return

        files = []
        for path, _, dir_files in os.walk(chosen_dir):
            for filename in dir_files:
                files.append(os.path.join(path, filename))

        self.dialog_widget.create_torrent_files_list.clear()
        for filename in files:
            self.dialog_widget.create_torrent_files_list.addItem(filename)

    def on_create_clicked(self, checked):
        if self.dialog_widget.create_torrent_files_list.count() == 0:
            dialog = ConfirmationDialog(
                self.dialog_widget,
                tr("Warning!"),
                tr("You should add at least one file to your torrent."),
                [(tr("CLOSE"), BUTTON_TYPE_NORMAL)],
            )

            connect(dialog.button_clicked, dialog.close_dialog)
            dialog.show()
            return

        self.dialog_widget.btn_create.setEnabled(False)

        files_list = []
        for ind in range(self.dialog_widget.create_torrent_files_list.count()):
            file_str = self.dialog_widget.create_torrent_files_list.item(ind).text()
            files_list.append(file_str)

        export_dir = self.dialog_widget.file_export_dir.text()
        if not os.path.exists(export_dir):
            ConfirmationDialog.show_error(
                self.dialog_widget, tr("Cannot save torrent file to %s") % export_dir, tr("Path does not exist")
            )
            return

        is_writable, error = is_dir_writable(export_dir)
        if not is_writable:
            ConfirmationDialog.show_error(
                self.dialog_widget, tr("Cannot save torrent file to %s") % export_dir, tr("Error: %s ") % str(error)
            )
            return

        self.name = self.dialog_widget.create_torrent_name_field.text()
        description = self.dialog_widget.create_torrent_description_field.toPlainText()
        post_data = {"name": self.name, "description": description, "files": files_list, "export_dir": export_dir}
        url = (
            "createtorrent?download=1" if self.dialog_widget.seed_after_adding_checkbox.isChecked() else "createtorrent"
        )
        self.rest_request1 = TriblerNetworkRequest(url, self.on_torrent_created, data=post_data, method='POST')
        self.dialog_widget.edit_channel_create_torrent_progress_label.setText(tr("Creating torrent. Please wait..."))

    def on_torrent_created(self, result):
        if not result:
            return
        self.dialog_widget.btn_create.setEnabled(True)
        self.dialog_widget.edit_channel_create_torrent_progress_label.setText(tr("Created torrent"))
        if 'torrent' in result:
            self.create_torrent_notification.emit({"msg": tr("Torrent successfully created")})
            self.close_dialog()
            if self.dialog_widget.add_to_channel_checkbox.isChecked():
                self.add_to_channel_selected.emit(result['torrent'])

    def on_select_save_directory(self, checked):
        chosen_dir = QFileDialog.getExistingDirectory(
            self.window(), tr("Please select the directory containing the files"), "", QFileDialog.ShowDirsOnly
        )

        if not chosen_dir:
            return
        self.dialog_widget.file_export_dir.setText(chosen_dir)

    def on_remove_entry(self, index):
        self.dialog_widget.create_torrent_files_list.takeItem(index)

    def on_right_click_file_item(self, pos):
        item_clicked = self.dialog_widget.create_torrent_files_list.itemAt(pos)
        if not item_clicked:
            return

        selected_item_index = self.dialog_widget.create_torrent_files_list.row(item_clicked)

        remove_action = QAction(tr("Remove file"), self)
        connect(remove_action.triggered, lambda index=selected_item_index: self.on_remove_entry(index))

        menu = TriblerActionMenu(self)
        menu.addAction(remove_action)
        menu.exec_(self.dialog_widget.create_torrent_files_list.mapToGlobal(pos))
