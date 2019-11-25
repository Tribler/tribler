from __future__ import absolute_import

import os

from PyQt5 import uic
from PyQt5.QtCore import QDir, pyqtSignal
from PyQt5.QtWidgets import QAction, QFileDialog, QSizePolicy, QTreeWidgetItem

from six.moves import xrange

from Tribler.Core.Utilities.unicode import ensure_unicode

from TriblerGUI.defs import BUTTON_TYPE_NORMAL
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.dialogs.dialogcontainer import DialogContainer
from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_ui_file_path, is_dir_writable


class DownloadFileTreeWidgetItem(QTreeWidgetItem):

    def __init__(self, parent):
        QTreeWidgetItem.__init__(self, parent)


class CreateTorrentDialog(DialogContainer):

    create_torrent_notification = pyqtSignal(dict)

    def __init__(self, parent):
        DialogContainer.__init__(self, parent)

        uic.loadUi(get_ui_file_path('createtorrentdialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.dialog_widget.btn_cancel.clicked.connect(self.close_dialog)
        self.dialog_widget.create_torrent_choose_files_button.clicked.connect(self.on_choose_files_clicked)
        self.dialog_widget.create_torrent_choose_dir_button.clicked.connect(self.on_choose_dir_clicked)
        self.dialog_widget.btn_create.clicked.connect(self.on_create_clicked)
        self.dialog_widget.create_torrent_files_list.customContextMenuRequested.connect(self.on_right_click_file_item)
        self.dialog_widget.create_torrent_files_list.clear()
        self.dialog_widget.save_directory_chooser.clicked.connect(self.on_select_save_directory)
        self.dialog_widget.edit_channel_create_torrent_progress_label.setText("")
        self.dialog_widget.file_export_dir.setText(os.path.expanduser("~"))
        self.dialog_widget.adjustSize()

        self.on_main_window_resize()

        self.request_mgr = None
        self.name = None

    def close_dialog(self):
        if self.request_mgr:
            self.request_mgr.cancel_request()
            self.request_mgr = None

        super(CreateTorrentDialog, self).close_dialog()

    def on_choose_files_clicked(self):
        filenames, _ = QFileDialog.getOpenFileNames(self.window(), "Please select the files", QDir.homePath())

        for filename in filenames:
            self.dialog_widget.create_torrent_files_list.addItem(filename)

    def on_choose_dir_clicked(self):
        chosen_dir = QFileDialog.getExistingDirectory(self.window(),
                                                      "Please select the directory containing the files",
                                                      "", QFileDialog.ShowDirsOnly)

        if not chosen_dir:
            return

        files = []
        for path, _, dir_files in os.walk(chosen_dir):
            for filename in dir_files:
                files.append(os.path.join(path, filename))

        self.dialog_widget.create_torrent_files_list.clear()
        for filename in files:
            self.dialog_widget.create_torrent_files_list.addItem(filename)

    def on_create_clicked(self):
        if self.dialog_widget.create_torrent_files_list.count() == 0:
            dialog = ConfirmationDialog(self.dialog_widget, "Warning!",
                                        "You should add at least one file to your torrent.",
                                        [('CLOSE', BUTTON_TYPE_NORMAL)])

            dialog.button_clicked.connect(dialog.close_dialog)
            dialog.show()
            return

        self.dialog_widget.btn_create.setEnabled(False)

        files_list = []
        for ind in xrange(self.dialog_widget.create_torrent_files_list.count()):
            file_str = self.dialog_widget.create_torrent_files_list.item(ind).text()
            files_list.append(file_str)

        export_dir = self.dialog_widget.file_export_dir.text()
        if not os.path.exists(export_dir):
            ConfirmationDialog.show_error(self.dialog_widget, "Cannot save torrent file to %s" % export_dir,
                                          "Path does not exist")
            return

        is_writable, error = is_dir_writable(export_dir)
        if not is_writable:
            ConfirmationDialog.show_error(self.dialog_widget, "Cannot save torrent file to %s" % export_dir,
                                          "Error: %s" % error)
            return

        self.name = self.dialog_widget.create_torrent_name_field.text()
        description = self.dialog_widget.create_torrent_description_field.toPlainText()
        post_data = {
            "name": self.name,
            "description": description,
            "files": files_list,
            "export_dir": export_dir
        }
        url = "createtorrent?download=1" if self.dialog_widget.seed_after_adding_checkbox.isChecked() \
            else "createtorrent"
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request(url, self.on_torrent_created, data=post_data, method='POST')
        self.dialog_widget.edit_channel_create_torrent_progress_label.setText("Creating torrent. Please wait...")

    def on_torrent_created(self, result):
        if not result:
            return
        self.dialog_widget.btn_create.setEnabled(True)
        self.dialog_widget.edit_channel_create_torrent_progress_label.setText("Created torrent")
        if 'torrent' in result:
            self.create_torrent_notification.emit({"msg": "Torrent successfully created"})
            if self.dialog_widget.add_to_channel_checkbox.isChecked():
                self.add_torrent_to_channel(result['torrent'])
            else:
                self.close_dialog()

    def add_torrent_to_channel(self, torrent):
        self.request_mgr = TriblerRequestManager()
        data = {"torrent": torrent}
        if self.name:
            data.update({"title": ensure_unicode(self.name, 'utf8')})
        self.request_mgr.perform_request("mychannel/torrents", self.on_torrent_to_channel_added,
                                         data=data, method='PUT')

    def on_torrent_to_channel_added(self, result):
        if not result:
            return
        if 'added' in result:
            self.create_torrent_notification.emit({"msg": "Torrent successfully added to the channel"})
            self.dialog_widget.edit_channel_create_torrent_progress_label.setText("Created torrent")
        self.close_dialog()

    def on_select_save_directory(self):
        chosen_dir = QFileDialog.getExistingDirectory(self.window(), "Please select the directory containing the files",
                                                      "", QFileDialog.ShowDirsOnly)

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

        remove_action = QAction('Remove file', self)
        remove_action.triggered.connect(lambda index=selected_item_index: self.on_remove_entry(index))

        menu = TriblerActionMenu(self)
        menu.addAction(remove_action)
        menu.exec_(self.dialog_widget.create_torrent_files_list.mapToGlobal(pos))
