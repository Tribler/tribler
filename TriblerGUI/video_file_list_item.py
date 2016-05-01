from PyQt5 import uic
from PyQt5.QtWidgets import QWidget


class VideoFileListItem(QWidget):
    """
    This class defines a list item in the video files list.
    """

    def __init__(self, parent, file_info, is_selected=False):
        super(QWidget, self).__init__(parent)

        uic.loadUi('qt_resources/video_file_list_item.ui', self)

        self.file_name.setText(file_info["name"])

        if is_selected:
            self.setSelected()

    def setSelected(self):
        self.file_name.setStyleSheet("color: #e67300;"
                               "background-color: transparent;"
                               "font-size: 16px;"
                               "font-weight: bold;")

    def setDeselected(self):
        self.file_name.setStyleSheet("color: #eee;"
                               "background-color: transparent;"
                               "font-size: 16px;"
                               "font-weight: normal;")
