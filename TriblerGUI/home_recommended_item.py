from PyQt5.QtCore import QPoint, QSize, Qt
from PyQt5.QtGui import QIcon, QCursor
from PyQt5.QtWidgets import QWidget, QLabel, QSizePolicy, QToolButton

from TriblerGUI.tribler_window import fc_home_recommended_item
from TriblerGUI.utilities import pretty_date, get_image_path

HOME_ITEM_FONT_SIZE = 44


class HomeRecommendedItem(QWidget, fc_home_recommended_item):

    def __init__(self, parent):
        super(QWidget, self).__init__(parent)

        self.setupUi(self)

        self.show_torrent = True
        self.torrent_info = None
        self.channel_info = None

        # Create the category label, shown on cells that display a torrent on the home page
        self.category_label = QLabel(self)
        self.category_label.setFixedHeight(24)
        self.category_label.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))
        self.category_label.setStyleSheet("""
        border: 2px solid white;
        border-radius: 12px;
        background-color: transparent;
        color: white;
        padding-left: 4px;
        padding-right: 4px;
        font-weight: bold;
        """)
        self.category_label.move(QPoint(6, 6))
        self.category_label.show()

        # Create the dark overlay and download button over the thumbnail on hover
        self.dark_overlay = QWidget(self)
        self.dark_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.65);")
        self.dark_overlay.hide()

        self.download_button = QToolButton(self)
        self.download_button.setFixedSize(QSize(50, 50))
        self.download_button.setStyleSheet("""
        QToolButton {
        background-color: transparent;
        border: 2px solid white;
        border-radius: 25px;
        }
        QToolButton::hover {
        border: 2px solid #B5B5B5;
        }
        """)
        self.download_button.setIcon(QIcon(get_image_path('downloads.png')))
        self.download_button.setIconSize(QSize(24, 24))
        self.download_button.hide()

    def update_with_torrent(self, torrent):
        self.show_torrent = True
        self.torrent_info = torrent
        self.thumbnail_widget.initialize(torrent["name"], HOME_ITEM_FONT_SIZE)
        self.main_label.setText(torrent["name"])
        self.category_label.setText(torrent["category"])
        self.category_label.adjustSize()
        self.category_label.setHidden(False)
        self.setCursor(Qt.ArrowCursor)
        #self.detail_label.setText("Added " + pretty_date(torrent["added"]))

    def update_with_channel(self, channel):
        self.show_torrent = False
        self.channel_info = channel
        self.thumbnail_widget.initialize(channel["name"], HOME_ITEM_FONT_SIZE)

        self.main_label.setText(channel["name"])
        self.detail_label.setText("Updated " + pretty_date(channel["modified"]))
        self.category_label.setHidden(True)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event):
        if self.show_torrent:
            self.dark_overlay.resize(self.thumbnail_widget.size())
            self.dark_overlay.show()
            self.download_button.move((self.thumbnail_widget.width() - self.download_button.width()) / 2,
                                      (self.thumbnail_widget.height() - self.download_button.height()) / 2)
            self.download_button.show()

    def leaveEvent(self, event):
        self.dark_overlay.hide()
        self.download_button.hide()
