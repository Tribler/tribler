import json

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QListWidget, QListWidgetItem

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.video_file_list_item import VideoFileListItem


class VideoPlayerFilesMenu(QWidget):
    """
    This class manages the menu to the right of the video player that can be used to choose a different file for
    playback.
    """

    should_change_playing_file = pyqtSignal(int)

    def initialize_file_menu(self):
        self.window().video_player_files.itemClicked.connect(self.on_file_item_click)

    def load_download_files(self, infohash):
        self.request_manager.get_download_details(infohash)

    def received_download_details(self, json_result):
        self.file_list.clear()
        results = json.loads(json_result)

        for result in results['download']['files']:
            item = QListWidgetItem(self.file_list)
            item.setData(Qt.UserRole, result)
            is_selected = self.parent().ACTIVE_INDEX == result['index']
            widget_item = VideoFileListItem(self.file_list, result, is_selected)
            item.setSizeHint(widget_item.sizeHint())
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, widget_item)

    def on_file_item_click(self, file_list_item):
        file_info = file_list_item.data(Qt.UserRole)
        self.should_change_playing_file.emit(file_info['index'])

        for i in xrange(0, self.file_list.count()):
            item = self.file_list.item(i)
            self.file_list.itemWidget(item).setDeselected()

        self.file_list.itemWidget(file_list_item).setSelected()
