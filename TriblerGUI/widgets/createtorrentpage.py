import os
from PyQt5.QtWidgets import QWidget, QFileDialog
from TriblerGUI.defs import PAGE_EDIT_CHANNEL_TORRENTS


class CreateTorrentPage(QWidget):

    def initialize(self):
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
        # TODO
        pass
