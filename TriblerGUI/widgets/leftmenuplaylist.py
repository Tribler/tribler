from PyQt5.QtCore import QTimer
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QListWidget
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import is_video_file


class LeftMenuPlaylist(QListWidget):
    """
    This class represents the menu with video files that is visible in the left menu.
    Only shows when a video is playing.
    """

    playing_item_change = pyqtSignal(int)  # file index
    list_loaded = pyqtSignal()
    item_should_play = pyqtSignal()  # no info required, a double click always follow a click event

    def __init__(self, parent):
        QListWidget.__init__(self, parent)

        self.files_data = []
        self.loaded_list = False
        self.loading_list = False
        self.active_index = -1
        self.infohash = None
        self.itemClicked.connect(self.on_item_clicked)
        self.itemDoubleClicked.connect(self.on_item_double_clicked)

        self.files_request_mgr = None
        self.files_request_timer = None

    def set_loading(self):
        self.clear()
        self.addItem("Loading...")
        self.loaded_list = False
        self.loading_list = True

    def load_list(self, infohash):
        self.infohash = infohash
        self.set_loading()

        if self.files_request_timer:
            self.files_request_timer.invalidate()

        self.files_request_timer = QTimer()
        self.files_request_timer.timeout.connect(self.perform_get_files_request)
        self.files_request_timer.start(1000)

    def perform_get_files_request(self):
        self.files_request_mgr = TriblerRequestManager()
        self.files_request_mgr.perform_request("downloads/%s/files" % self.infohash, self.on_received_files)

    def on_received_files(self, files):
        if "files" not in files or not files["files"]:
            return

        self.files_request_timer.stop()
        self.files_request_timer = None

        self.set_files(files["files"])
        self.loaded_list = True
        self.loading_list = False
        self.list_loaded.emit()

    def get_largest_file(self):
        largest_file = None
        largest_index = None
        for index, file_info in enumerate(self.files_data):
            if is_video_file(file_info["name"]) and \
                    (largest_file is None or file_info["size"] > largest_file["size"]):
                largest_file = file_info
                largest_index = index
        return largest_index, largest_file

    def set_files(self, files):
        self.clear()
        self.files_data = []

        for file_info in files:
            if is_video_file(file_info['name']):
                self.addItem(file_info['name'])
                self.files_data.append(file_info)

    def set_active_index(self, file_index):
        cur_ind = 0
        for ind, file_info in enumerate(self.files_data):
            if ind == file_index:
                self.item(cur_ind).setSelected(True)
                self.setFocus()
                break
            cur_ind += 1

    def get_file_info(self, menu_index):
        """
        Get the file info, based on the menu index
        """
        return self.files_data[menu_index] if menu_index < len(self.files_data) else None

    def on_item_clicked(self, item):
        item_ind = self.row(item)
        if self.loaded_list:
            self.playing_item_change.emit(item_ind)

    def on_item_double_clicked(self, item):
        self.item_should_play.emit()
