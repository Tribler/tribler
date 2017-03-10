from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QListWidget
from TriblerGUI.utilities import is_video_file


class LeftMenuPlaylist(QListWidget):
    """
    This class represents the menu with video files that is visible in the left menu.
    Only shows when a video is playing.
    """

    playing_item_change = pyqtSignal(int, str)  # file index, name of file
    item_should_play = pyqtSignal()  # no info required, a double click always follow a click event

    def __init__(self, parent):
        QListWidget.__init__(self, parent)

        self.files_data = []
        self.loaded_list = False
        self.active_index = -1
        self.itemClicked.connect(self.on_item_clicked)
        self.itemDoubleClicked.connect(self.on_item_double_clicked)

    def set_loading(self):
        self.clear()
        self.addItem("Loading...")
        self.loaded_list = False

    def set_files(self, files):
        self.clear()
        self.files_data = []

        for file_info in files:
            if is_video_file(file_info['name']):
                self.addItem(file_info['name'])
                self.files_data.append((file_info['index'], file_info['name']))
        self.loaded_list = True

    def set_active_index(self, file_index):
        cur_ind = 0
        for index, _ in self.files_data:
            if index == file_index:
                self.item(cur_ind).setSelected(True)
                self.setFocus()
                break
            cur_ind += 1

    def on_item_clicked(self, item):
        item_ind = self.row(item)
        if self.loaded_list:
            self.playing_item_change.emit(*self.files_data[item_ind])

    def on_item_double_clicked(self, item):
        self.item_should_play.emit()
