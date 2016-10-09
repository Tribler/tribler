from PyQt5 import uic
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

from TriblerGUI.tribler_window import fc_playlist_list_item
from TriblerGUI.utilities import get_ui_file_path, get_image_path


class PlaylistListItem(QWidget, fc_playlist_list_item):
    """
    This class is responsible for managing the playlist item widget.
    """

    def __init__(self, parent, playlist, show_controls=False, on_remove_clicked=None, on_edit_clicked=None):
        super(QWidget, self).__init__(parent)

        self.setupUi(self)

        self.playlist_info = playlist

        self.edit_playlist_button.setIcon(QIcon(get_image_path("edit_white.png")))
        self.remove_playlist_button.setIcon(QIcon(get_image_path("delete.png")))

        self.playlist_name.setText(playlist["name"])
        self.playlist_num_items.setText("%d items" % len(playlist["torrents"]))

        self.thumbnail_widget.initialize(playlist["name"], 24)

        self.controls_container.setHidden(True)
        self.show_controls = show_controls

        if on_remove_clicked is not None:
            self.remove_playlist_button.clicked.connect(lambda: on_remove_clicked(self))

        if on_edit_clicked is not None:
            self.edit_playlist_button.clicked.connect(lambda: on_edit_clicked(self))

    def enterEvent(self, event):
        if self.show_controls:
            self.controls_container.setHidden(False)
            self.edit_playlist_button.setIcon(QIcon(get_image_path('edit_white.png')))
            self.remove_playlist_button.setIcon(QIcon(get_image_path('delete.png')))

    def leaveEvent(self, event):
        self.controls_container.setHidden(True)
