import os
import urllib

from PyQt5.QtCore import QDir
from PyQt5.QtGui import QIcon

from PyQt5.QtWidgets import QWidget, QFileDialog, QAction

from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.defs import PAGE_EDIT_CHANNEL_TORRENTS, BUTTON_TYPE_NORMAL
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path


class CreateTorrentPage(QWidget):
    """
    The CreateTorrentPage is the page where users can create torrent files so they can be added to their channel.
    """

    def __init__(self):
        QWidget.__init__(self)

        self.channel_identifier = None
        self.request_mgr = None
        self.dialog = None
        self.selected_item_index = -1
        self.initialized = False

    def initialize(self, identifier):
        self.channel_identifier = identifier
        self.window().create_torrent_name_field.setText('')
        self.window().create_torrent_description_field.setText('')
        self.window().create_torrent_files_list.clear()
        self.window().seed_after_adding_checkbox.setChecked(True)
        self.window().edit_channel_create_torrent_progress_label.hide()

        if not self.initialized:
            self.window().manage_channel_create_torrent_back.setIcon(QIcon(get_image_path('page_back.png')))

            self.window().create_torrent_files_list.customContextMenuRequested.connect(self.on_right_click_file_item)
            self.window().manage_channel_create_torrent_back.clicked.connect(self.on_create_torrent_manage_back_clicked)
            self.window().create_torrent_choose_files_button.clicked.connect(self.on_choose_files_clicked)
            self.window().create_torrent_choose_dir_button.clicked.connect(self.on_choose_dir_clicked)
            self.window().edit_channel_create_torrent_button.clicked.connect(self.on_create_clicked)

            self.initialized = True

    def on_create_torrent_manage_back_clicked(self):
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_TORRENTS)

    def on_choose_files_clicked(self):
        filenames, _ = QFileDialog.getOpenFileNames(self.window(), "Please select the files", QDir.homePath())

        for filename in filenames:
            self.window().create_torrent_files_list.addItem(filename)

    def on_choose_dir_clicked(self):
        chosen_dir = QFileDialog.getExistingDirectory(self.window(), "Please select the directory containing the files",
                                                      "", QFileDialog.ShowDirsOnly)

        if len(chosen_dir) == 0:
            return

        files = []
        for path, _, dir_files in os.walk(chosen_dir):
            for filename in dir_files:
                files.append(os.path.join(path, filename))

        self.window().create_torrent_files_list.clear()
        for filename in files:
            self.window().create_torrent_files_list.addItem(filename)

    def on_create_clicked(self):
        if self.window().create_torrent_files_list.count() == 0:
            self.dialog = ConfirmationDialog(self, "Notice", "You should add at least one file to your torrent.",
                                             [('CLOSE', BUTTON_TYPE_NORMAL)])
            self.dialog.button_clicked.connect(self.on_dialog_ok_clicked)
            self.dialog.show()
            return

        self.window().edit_channel_create_torrent_button.setEnabled(False)

        files_str = u""
        for ind in xrange(self.window().create_torrent_files_list.count()):
            files_str += u"files[]=%s&" % urllib.quote_plus(
                self.window().create_torrent_files_list.item(ind).text().encode('utf-8'))

        name = urllib.quote_plus(self.window().create_torrent_name_field.text().encode('utf-8'))
        description = urllib.quote_plus(self.window().create_torrent_description_field.toPlainText().encode('utf-8'))
        post_data = (u"%s&name=%s&description=%s" % (files_str[:-1], name, description)).encode('utf-8')
        url = "createtorrent?download=1" if self.window().seed_after_adding_checkbox.isChecked() else "createtorrent"
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request(url, self.on_torrent_created, data=post_data, method='POST')
        # Show creating torrent text
        self.window().edit_channel_create_torrent_progress_label.show()

    def on_dialog_ok_clicked(self, _):
        self.dialog.close_dialog()
        self.dialog = None

    def on_torrent_created(self, result):
        if not result:
            return
        self.window().edit_channel_create_torrent_button.setEnabled(True)
        if 'torrent' in result:
            self.add_torrent_to_channel(result['torrent'])

    def add_torrent_to_channel(self, torrent):
        post_data = str("torrent=%s" % urllib.quote_plus(torrent))
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("channels/discovered/%s/torrents" %
                                         self.channel_identifier, self.on_torrent_to_channel_added,
                                         data=post_data, method='PUT')

    def on_torrent_to_channel_added(self, result):
        if not result:
            return
        self.window().edit_channel_create_torrent_progress_label.hide()
        if 'added' in result:
            self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_TORRENTS)
            self.window().edit_channel_torrents_list.model.refresh()

    def on_remove_entry(self):
        self.window().create_torrent_files_list.takeItem(self.selected_item_index)

    def on_right_click_file_item(self, pos):
        item_clicked = self.window().create_torrent_files_list.itemAt(pos)
        if not item_clicked:
            return

        self.selected_item_index = self.window().create_torrent_files_list.row(item_clicked)

        menu = TriblerActionMenu(self)

        remove_action = QAction('Remove file', self)
        remove_action.triggered.connect(self.on_remove_entry)
        menu.addAction(remove_action)
        menu.exec_(self.window().create_torrent_files_list.mapToGlobal(pos))
