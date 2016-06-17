from PyQt5 import uic
from PyQt5.QtWidgets import QWidget
from TriblerGUI.utilities import get_ui_file_path


class PlaylistListItem(QWidget):
    """
    This class is responsible for managing the playlist item widget.
    """

    def __init__(self, parent, playlist, show_controls=False, on_remove_clicked=None, on_edit_clicked=None):
        super(QWidget, self).__init__(parent)

        self.playlist_info = playlist

        uic.loadUi(get_ui_file_path('playlist_list_item.ui'), self)

        self.playlist_name.setText(playlist["name"])
        self.playlist_num_items.setText("%d items" % len(playlist["torrents"]))

        self.thumbnail_widget.initialize(playlist["name"], 24)

        if not show_controls:
            self.controls_container.setHidden(True)

        if on_remove_clicked is not None:
            self.remove_playlist_button.clicked.connect(lambda: on_remove_clicked(self))

        if on_edit_clicked is not None:
            self.edit_playlist_button.clicked.connect(lambda: on_edit_clicked(self))
