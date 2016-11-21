from urllib import quote_plus

from PyQt5.QtCore import QPoint, QSize, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QLabel, QSizePolicy, QToolButton

from TriblerGUI.dialogs.startdownloaddialog import StartDownloadDialog
from TriblerGUI.tribler_window import fc_home_recommended_item
from TriblerGUI.utilities import pretty_date, get_image_path, format_size, get_gui_setting

HOME_ITEM_FONT_SIZE = 44


class HomeRecommendedItem(QWidget, fc_home_recommended_item):
    """
    This class represents a HomeRecommendedItem widget which is shown on the home page. This widget can either show
    a channel or a torrent.
    """

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        fc_home_recommended_item.__init__(self)

        self.setupUi(self)

        self.show_torrent = True
        self.torrent_info = None
        self.channel_info = None
        self.download_uri = None
        self.dialog = None

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
        self.download_button.setFixedSize(QSize(40, 40))
        self.download_button.setStyleSheet("""
        QToolButton {
            background-color: transparent;
            border: 2px solid white;
            border-radius: 20px;
        }

        QToolButton::hover {
            border: 2px solid #B5B5B5;
        }
        """)
        self.download_button.setIcon(QIcon(get_image_path('downloads.png')))
        self.download_button.setIconSize(QSize(18, 18))
        self.download_button.clicked.connect(self.on_download_button_clicked)
        self.download_button.hide()

    def on_download_button_clicked(self):
        gui_settings = self.window().gui_settings
        self.download_uri = quote_plus((u"magnet:?xt=urn:btih:%s&dn=%s" %
                                        (self.torrent_info["infohash"], self.torrent_info['name'])).encode('utf-8'))

        if get_gui_setting(gui_settings, "ask_download_settings", True, is_bool=True):
            self.dialog = StartDownloadDialog(self.window().stackedWidget, self.download_uri, self.torrent_info["name"])
            self.dialog.button_clicked.connect(self.on_start_download_action)
            self.dialog.show()
        else:
            self.window().perform_start_download_request(self.download_uri,
                                                         get_gui_setting(gui_settings, "default_anonymity_enabled",
                                                                         True, is_bool=True),
                                                         get_gui_setting(gui_settings, "default_safeseeding_enabled",
                                                                         True, is_bool=True), [], 0)

    def on_start_download_action(self, action):
        if action == 1:
            self.window().perform_start_download_request(self.download_uri,
                                                         self.dialog.dialog_widget.anon_download_checkbox.isChecked(),
                                                         self.dialog.dialog_widget.safe_seed_checkbox.isChecked(),
                                                         self.dialog.get_selected_files(),
                                                         self.dialog.dialog_widget.files_list_view.topLevelItemCount())

        self.dialog.setParent(None)
        self.dialog = None

    def update_with_torrent(self, torrent):
        self.show_torrent = True
        self.torrent_info = torrent
        self.thumbnail_widget.initialize(torrent["name"], HOME_ITEM_FONT_SIZE)
        self.main_label.setText(torrent["name"])
        self.category_label.setText(torrent["category"])
        self.category_label.adjustSize()
        self.category_label.setHidden(False)
        self.setCursor(Qt.ArrowCursor)
        self.detail_label.setText("Size: " + format_size(torrent["size"]))

    def update_with_channel(self, channel):
        self.show_torrent = False
        self.channel_info = channel
        self.thumbnail_widget.initialize(channel["name"], HOME_ITEM_FONT_SIZE)

        self.main_label.setText(channel["name"])
        self.detail_label.setText("Updated " + pretty_date(channel["modified"]))
        self.category_label.setHidden(True)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, _):
        if self.show_torrent:
            self.dark_overlay.resize(self.thumbnail_widget.size())
            self.dark_overlay.show()
            self.download_button.move((self.thumbnail_widget.width() - self.download_button.width()) / 2,
                                      (self.thumbnail_widget.height() - self.download_button.height()) / 2)
            self.download_button.show()

    def leaveEvent(self, _):
        self.dark_overlay.hide()
        self.download_button.hide()
