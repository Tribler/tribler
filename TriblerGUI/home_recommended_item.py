from PyQt5 import uic
from PyQt5.QtWidgets import QWidget
from TriblerGUI.utilities import pretty_date, get_ui_file_path

HOME_ITEM_FONT_SIZE = 44


class HomeRecommendedChannelItem(QWidget):

    def __init__(self, parent, channel):
        super(QWidget, self).__init__(parent)

        self.channel_info = channel

        uic.loadUi(get_ui_file_path('home_recommended_item.ui'), self)
        self.thumbnail_widget.initialize(channel["name"], HOME_ITEM_FONT_SIZE)

        self.main_label.setText(channel["name"])
        self.detail_label.setText("Updated " + pretty_date(channel["modified"]))


class HomeRecommendedTorrentItem(QWidget):

    def __init__(self, parent, torrent):
        super(QWidget, self).__init__(parent)

        uic.loadUi(get_ui_file_path('home_recommended_item.ui'), self)
        self.thumbnail_widget.initialize(torrent["name"], HOME_ITEM_FONT_SIZE)

        self.main_label.setText(torrent["name"])
        self.detail_label.setText("Added " + pretty_date(torrent["added"]))
