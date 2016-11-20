from PyQt5.QtWidgets import QLabel
from TriblerGUI.utilities import get_color


class ThumbnailWidget(QLabel):
    """
    This widget represents a thumbnail that is associated with a torrent. For now, it only acts as a placeholder.
    """

    #def __init__(self):
    #    QLabel.__init__(self)

    def initialize(self, torrent_name, font_size):
        stripped_torrent_name = ''.join([i for i in torrent_name if i.isalpha() or i == ' '])

        parts = stripped_torrent_name.split(" ")
        if len(parts) == 1:
            self.setText(parts[0][:1].upper())
        else:
            self.setText(parts[0][:1].upper() + parts[1][:1].upper())

        self.setStyleSheet("font-size: " + str(font_size) +
                           "px; color: rgba(255, 255, 255, 0.7); background-color: %s" % get_color(torrent_name))
