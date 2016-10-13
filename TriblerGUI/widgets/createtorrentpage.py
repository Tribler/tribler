import os
from PyQt5.QtGui import QIcon

from PyQt5.QtWidgets import QWidget, QFileDialog
from TriblerGUI.defs import PAGE_EDIT_CHANNEL_TORRENTS
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path


class CreateTorrentPage(QWidget):

    def initialize(self, identifier):
        self.channel_identifier = identifier
        self.window().manage_channel_create_torrent_back.setIcon(QIcon(get_image_path('page_back.png')))

        self.window().create_torrent_name_field.setText('')
        self.window().create_torrent_description_field.setText('')
        self.window().create_torrent_files_list.clear()

        self.window().manage_channel_create_torrent_back.clicked.connect(self.on_create_torrent_manage_back_clicked)
        self.window().create_torrent_choose_files_button.clicked.connect(self.on_choose_files_clicked)
        self.window().create_torrent_choose_dir_button.clicked.connect(self.on_choose_dir_clicked)
        self.window().edit_channel_create_torrent_button.clicked.connect(self.on_create_clicked)

    def on_create_torrent_manage_back_clicked(self):
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_TORRENTS)

    def on_choose_files_clicked(self):
        filenames = QFileDialog.getOpenFileNames(self, "Please select the files", "")

        self.window().create_torrent_files_list.clear()
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
        paths = []
        for ind in xrange(self.window().create_torrent_files_list.count()):
            paths.append(str(self.window().create_torrent_files_list.item(ind).text()))

        post_data = "files=%s&description=test" % str(paths)
        self.torrent_request_mgr = TriblerRequestManager()
        self.torrent_request_mgr.perform_request("createtorrent", self.on_torrent_created, data=post_data, method='GET')

    def on_torrent_created(self, result):
        if 'torrent' in result:
            self.add_torrent_to_channel(result['torrent'])

    def add_torrent_to_channel(self, torrent):
        post_data = str("torrent=%s&description=test" % torrent)
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("channels/discovered/%s/torrents" % self.channel_identifier, self.on_torrent_to_channel_added, data=post_data, method='PUT')

    def on_torrent_to_channel_added(self, result):
        if 'added' in result:
            self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_TORRENTS)
            self.window().edit_channel_page.load_channel_torrents()
