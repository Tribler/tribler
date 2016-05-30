from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QListWidget
from TriblerGUI.utilities import is_video_file


class LeftMenuPlaylist(QListWidget):

    playing_item_change = pyqtSignal(int, str) # file index, name of file

    def __init__(self, parent):
        super(QListWidget, self).__init__(parent)

        self.files_data = []
        self.loaded_list = False
        self.active_index = -1
        self.itemClicked.connect(self.on_item_clicked)

    def set_loading(self):
        self.clear()
        self.addItem("Loading...")
        self.loaded_list = False

    def set_files(self, files):
        self.clear()
        self.files_data = []

        for file in files:
            if is_video_file(file['name']):
                self.addItem(file['name'])
                self.files_data.append((file['index'], file['name']))
        self.loaded_list = True

    def set_active_index(self, file_index):
        cur_ind = 0
        for index, name in self.files_data:
            if index == file_index:
                self.item(cur_ind).setSelected(True)
                self.setFocus()
                break
            cur_ind += 1

    def on_item_clicked(self, item):
        item_ind = self.row(item)
        self.playing_item_change.emit(*self.files_data[item_ind])
