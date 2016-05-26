from PyQt5.QtWidgets import QLabel
from TriblerGUI.utilities import get_random_color


class ThumbnailWidget(QLabel):

    def initialize(self, torrent_name, font_size):

        parts = torrent_name.split(" ")
        if len(parts) == 1:
            self.setText(parts[0][:1])
        else:
            self.setText(parts[0][:1] + parts[1][:1])

        self.setStyleSheet("font-size: " + str(font_size) + "px; color: rgba(255, 255, 255, 0.7); background-color: %s" % get_random_color())
