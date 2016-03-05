import json
import sys
from PyQt5 import uic
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import QMainWindow, QListView, QListWidget, QLineEdit, QListWidgetItem, QApplication, QToolButton, \
    QWidget, QLabel

from TriblerGUI import leftmenubutton
from TriblerGUI.channel_list_item import ChannelListItem
from TriblerGUI.channel_torrent_list_item import ChannelTorrentListItem
from TriblerGUI.event_request_manager import EventRequestManager
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import create_rounded_image


class TriblerWindow(QMainWindow):

    def __init__(self):
        super(TriblerWindow, self).__init__()

        uic.loadUi('qt_resources/mainwindow.ui', self)

        # Remove the focus rect on OS X
        [widget.setAttribute(Qt.WA_MacShowFocusRect, 0) for widget in self.findChildren(QLineEdit) + self.findChildren(QListView)]

        self.channels_list = self.findChild(QListWidget, "channels_list")
        self.channel_torrents_list = self.findChild(QListWidget, "channel_torrents_list")
        self.top_menu_button = self.findChild(QToolButton, "top_menu_button")
        self.top_search_bar = self.findChild(QLineEdit, "top_search_bar")
        self.top_search_button = self.findChild(QToolButton, "top_search_button")
        self.my_profile_button = self.findChild(QToolButton, "my_profile_button")
        self.left_menu = self.findChild(QWidget, "left_menu")

        self.top_search_bar.returnPressed.connect(self.on_top_search_button_click)
        self.top_search_button.clicked.connect(self.on_top_search_button_click)
        self.top_menu_button.clicked.connect(self.on_top_menu_button_click)
        self.channels_list.itemClicked.connect(self.on_channel_item_click)

        self.left_menu_home_button = self.findChild(QWidget, "left_menu_home_button")
        self.left_menu_home_button.clicked_menu_button.connect(self.clicked_menu_button)
        self.left_menu_my_channel_button = self.findChild(QWidget, "left_menu_my_channel_button")
        self.left_menu_my_channel_button.clicked_menu_button.connect(self.clicked_menu_button)

        self.stackedWidget.setCurrentIndex(0)

        self.tribler_request_manager = TriblerRequestManager()
        self.tribler_request_manager.received_search_results.connect(self.received_search_results)
        self.tribler_request_manager.received_torrents_in_channel.connect(self.received_torrents_in_channel)

        self.event_request_manager = EventRequestManager()
        self.event_request_manager.received_free_space.connect(self.received_free_space)

        # Set profile image
        placeholder_pix = QPixmap("images/profile_placeholder.jpg")
        placeholder_pix = placeholder_pix.scaledToHeight(self.my_profile_button.width(), Qt.SmoothTransformation)
        placeholder_pix = create_rounded_image(placeholder_pix)
        self.my_profile_button.setIcon(QIcon(placeholder_pix))
        self.my_profile_button.setIconSize(QSize(self.my_profile_button.width(), self.my_profile_button.height()))

        self.left_menu.hide()

        self.show()

    def received_free_space(self, free_space):
        self.statusBar.set_free_space(free_space)

    def received_search_results(self, json_results):
        self.channels_list.clear()
        results = json.loads(json_results)

        for result in results['channels']:
            item = QListWidgetItem(self.channels_list)
            item.setSizeHint(QSize(-1, 60))
            item.setData(Qt.UserRole, result)
            widget_item = ChannelListItem(self.channels_list, result)
            self.channels_list.addItem(item)
            self.channels_list.setItemWidget(item, widget_item)

    def received_torrents_in_channel(self, json_results):
        self.channel_torrents_list.clear()
        results = json.loads(json_results)

        for result in results['torrents']:
            item = QListWidgetItem(self.channel_torrents_list)
            item.setSizeHint(QSize(-1, 60))
            item.setData(Qt.UserRole, result)
            widget_item = ChannelTorrentListItem(self.channel_torrents_list, result)
            self.channel_torrents_list.addItem(item)
            self.channel_torrents_list.setItemWidget(item, widget_item)

    def on_top_search_button_click(self):
        self.stackedWidget.setCurrentIndex(2)
        self.tribler_request_manager.search_channels(self.top_search_bar.text())

    def on_top_menu_button_click(self):
        if self.left_menu.isHidden():
            self.left_menu.show()
        else:
            self.left_menu.hide()

    def clicked_menu_button(self, menu_button_name):
        if menu_button_name == "left_menu_home_button":
            self.stackedWidget.setCurrentIndex(0)
        elif menu_button_name == "left_menu_my_channel_button":
            self.stackedWidget.setCurrentIndex(1)

    def on_channel_item_click(self, channel_list_item):
        channel_info = channel_list_item.data(Qt.UserRole)
        self.tribler_request_manager.get_torrents_in_channel(str(channel_info['id']))
        self.stackedWidget.setCurrentIndex(3)

        # initialize the page about a channel
        channel_detail_pane = self.findChild(QWidget, "channel_details")
        channel_name_label = channel_detail_pane.findChild(QLabel, "channel_name_label")
        channel_num_subs_label = channel_detail_pane.findChild(QLabel, "channel_num_subs_label")

        channel_name_label.setText(channel_info['name'])
        channel_num_subs_label.setText(str(channel_info['votes']))


app = QApplication(sys.argv)
window = TriblerWindow()
window.setWindowTitle("Tribler")
sys.exit(app.exec_())
