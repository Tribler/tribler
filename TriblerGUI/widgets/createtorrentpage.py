import os
from PyQt5.QtGui import QIcon

from PyQt5.QtWidgets import QWidget, QFileDialog, QAction

from TriblerGUI.TriblerActionMenu import TriblerActionMenu
from TriblerGUI.defs import PAGE_EDIT_CHANNEL_TORRENTS, BUTTON_TYPE_NORMAL
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path


class CreateTorrentPage(QWidget):

    def initialize(self, identifier):
        self.channel_identifier = identifier
        self.window().manage_channel_create_torrent_back.setIcon(QIcon(get_image_path('page_back.png')))

        self.window().create_torrent_name_field.setText('')
        self.window().create_torrent_description_field.setText('')
        self.window().create_torrent_files_list.clear()
        self.window().create_torrent_files_list.customContextMenuRequested.connect(self.on_right_click_file_item)

        self.window().manage_channel_create_torrent_back.clicked.connect(self.on_create_torrent_manage_back_clicked)
        self.window().create_torrent_choose_files_button.clicked.connect(self.on_choose_files_clicked)
        self.window().create_torrent_choose_dir_button.clicked.connect(self.on_choose_dir_clicked)
        self.window().edit_channel_create_torrent_button.clicked.connect(self.on_create_clicked)

    def on_create_torrent_manage_back_clicked(self):
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_TORRENTS)

    def on_choose_files_clicked(self):
        filenames = QFileDialog.getOpenFileNames(self, "Please select the files", "")

        for file in filenames[0]:
            self.window().create_torrent_files_list.addItem(file)

    def on_choose_dir_clicked(self):
        dir = QFileDialog.getExistingDirectory(self, "Please select the directory containing the files", "",
                                               QFileDialog.ShowDirsOnly)

        if len(dir) == 0:
            return

        files = []
        for path, subdir, dir_files in os.walk(dir):
            for file in dir_files:
                files.append(os.path.join(path, file))

        self.window().create_torrent_files_list.clear()
        for file in files:
            self.window().create_torrent_files_list.addItem(file)

    def on_create_clicked(self):
        if self.window().create_torrent_files_list.count() == 0:
            self.dialog = ConfirmationDialog(self, "Notice", "You should add at least one file to your torrent.", [('CLOSE', BUTTON_TYPE_NORMAL)])
            self.dialog.button_clicked.connect(self.on_dialog_ok_clicked)
            self.dialog.show()
            return

        files_str = u""
        for ind in xrange(self.window().create_torrent_files_list.count()):
            files_str += u"files[]=%s&" % self.window().create_torrent_files_list.item(ind).text()

        description = self.window().create_torrent_description_field.toPlainText()
        post_data = (u"%s&description=%s" % (files_str[:-1], description)).encode('utf-8')
        self.torrent_request_mgr = TriblerRequestManager()
        self.torrent_request_mgr.perform_request("createtorrent", self.on_torrent_created,
                                                 data=post_data, method='POST')

    def on_dialog_ok_clicked(self, _):
        self.dialog.setParent(None)
        self.dialog = None

    def on_torrent_created(self, result):
        if 'torrent' in result:
            self.add_torrent_to_channel(result['torrent'])

    def add_torrent_to_channel(self, torrent):
        post_data = str("torrent=%s" % torrent)
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("channels/discovered/%s/torrents" % self.channel_identifier, self.on_torrent_to_channel_added, data=post_data, method='PUT')

    def on_torrent_to_channel_added(self, result):
        if 'added' in result:
            self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_TORRENTS)
            self.window().edit_channel_page.load_channel_torrents()

    def on_remove_entry(self):
        self.window().create_torrent_files_list.takeItem(self.selected_item_index)

    def on_right_click_file_item(self, pos):
        selected_item = self.window().create_torrent_files_list.selectedItems()[0]
        self.selected_item_index = self.window().create_torrent_files_list.row(selected_item)

        menu = TriblerActionMenu(self)

        remove_action = QAction('Remove file', self)
        remove_action.triggered.connect(self.on_remove_entry)
        menu.addAction(remove_action)
        menu.exec_(self.window().create_torrent_files_list.mapToGlobal(pos))
