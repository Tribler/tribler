import json
import os
import sys
from PyQt5 import uic
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import QMainWindow, QListView, QListWidget, QLineEdit, QListWidgetItem, QApplication, QToolButton, \
    QWidget, QLabel, QTreeWidget, QTreeWidgetItem, QProgressBar, QStackedWidget
from TriblerGUI.channel_activity_list_item import ChannelActivityListItem
from TriblerGUI.channel_comment_list_item import ChannelCommentListItem

from TriblerGUI.channel_list_item import ChannelListItem
from TriblerGUI.channel_torrent_list_item import ChannelTorrentListItem
from TriblerGUI.event_request_manager import EventRequestManager
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import create_rounded_image

# TODO martijn: temporary solution to convince VLC to find the plugin path
os.environ['VLC_PLUGIN_PATH'] = '/Applications/VLC.app/Contents/MacOS/plugins'


# Define stacked widget page indices
PAGE_HOME = 0
PAGE_MY_CHANNEL = 1
PAGE_CHANNELS_OVERVIEW = 2
PAGE_CHANNEL_DETAILS = 3
PAGE_SETTINGS = 4
PAGE_VIDEO_PLAYER = 5
PAGE_SUBSCRIBED_CHANNELS = 6
PAGE_DOWNLOADS = 7

PAGE_CHANNEL_CONTENT = 0
PAGE_CHANNEL_COMMENTS = 1
PAGE_CHANNEL_ACTIVITY = 2


class TriblerWindow(QMainWindow):

    resize_event = pyqtSignal()

    def __init__(self):
        super(TriblerWindow, self).__init__()

        self.settings = None
        self.navigation_stack = []

        uic.loadUi('qt_resources/mainwindow.ui', self)

        # Remove the focus rect on OS X
        [widget.setAttribute(Qt.WA_MacShowFocusRect, 0) for widget in self.findChildren(QLineEdit) + self.findChildren(QListView) + self.findChildren(QTreeWidget)]

        self.channels_list = self.findChild(QListWidget, "channels_list")
        self.subscribed_channels_list = self.findChild(QListWidget, "subscribed_channels_list")
        self.channel_torrents_list = self.findChild(QListWidget, "channel_torrents_list")
        self.top_menu_button = self.findChild(QToolButton, "top_menu_button")
        self.top_search_bar = self.findChild(QLineEdit, "top_search_bar")
        self.top_search_button = self.findChild(QToolButton, "top_search_button")
        self.my_profile_button = self.findChild(QToolButton, "my_profile_button")
        self.video_player_page = self.findChild(QWidget, "video_player_page")
        self.my_channel_page = self.findChild(QWidget, "my_channel_page")
        self.left_menu = self.findChild(QWidget, "left_menu")

        self.top_search_bar.returnPressed.connect(self.on_top_search_button_click)
        self.top_search_button.clicked.connect(self.on_top_search_button_click)
        self.top_menu_button.clicked.connect(self.on_top_menu_button_click)
        self.channels_list.itemClicked.connect(self.on_channel_item_click)
        self.subscribed_channels_list.itemClicked.connect(self.on_channel_item_click)

        self.left_menu_home_button = self.findChild(QWidget, "left_menu_home_button")
        self.left_menu_home_button.clicked_menu_button.connect(self.clicked_menu_button)
        self.left_menu_my_channel_button = self.findChild(QWidget, "left_menu_my_channel_button")
        self.left_menu_my_channel_button.clicked_menu_button.connect(self.clicked_menu_button)
        self.left_menu_subscribed_button = self.findChild(QWidget, "left_menu_subscribed_button")
        self.left_menu_subscribed_button.clicked_menu_button.connect(self.clicked_menu_button)
        self.left_menu_downloads_button = self.findChild(QWidget, "left_menu_downloads_button")
        self.left_menu_downloads_button.clicked_menu_button.connect(self.clicked_menu_button)
        self.left_menu_videoplayer_button = self.findChild(QWidget, "left_menu_videoplayer_button")
        self.left_menu_videoplayer_button.clicked_menu_button.connect(self.clicked_menu_button)
        self.left_menu_settings_button = self.findChild(QWidget, "left_menu_settings_button")
        self.left_menu_settings_button.clicked_menu_button.connect(self.clicked_menu_button)

        self.menu_buttons = [self.left_menu_home_button, self.left_menu_my_channel_button,
                             self.left_menu_subscribed_button, self.left_menu_videoplayer_button,
                             self.left_menu_settings_button, self.left_menu_downloads_button]

        channel_back_button = self.findChild(QToolButton, "channel_back_button")
        channel_back_button.clicked.connect(self.on_page_back_clicked)

        self.stackedWidget.setCurrentIndex(PAGE_CHANNELS_OVERVIEW)

        self.tribler_request_manager = TriblerRequestManager()
        self.tribler_request_manager.received_search_results.connect(self.received_search_results)
        self.tribler_request_manager.received_torrents_in_channel.connect(self.received_torrents_in_channel)
        self.tribler_request_manager.received_settings.connect(self.received_settings)
        self.tribler_request_manager.received_channels.connect(self.received_channels)
        self.tribler_request_manager.received_subscribed_channels.connect(self.received_subscribed_channels)

        self.channel_tab = self.findChild(QWidget, "channel_tab")
        self.channel_tab.initialize()
        self.channel_tab.clicked_tab_button.connect(self.on_channel_tab_button_clicked)
        self.channel_stacked_widget = self.findChild(QStackedWidget, "channel_stacked_widget")

        self.channel_comments_list = self.findChild(QTreeWidget, "channel_comments_list")
        self.channel_activities_list = self.findChild(QListWidget, "channel_activities_list")

        # TODO Martijn: for now, fill the comments and activity with some dummy data
        for i in range(0, 10):
            parent_item = QTreeWidgetItem(self.channel_comments_list)
            widget_item = ChannelCommentListItem(self.channel_comments_list, 0)
            self.channel_comments_list.setItemWidget(parent_item, 0, widget_item)

            child_item = QTreeWidgetItem(self.channel_comments_list)
            widget_item = ChannelCommentListItem(self.channel_comments_list, 1)
            self.channel_comments_list.setItemWidget(child_item, 0, widget_item)

        for i in range(0, 10):
            item = QListWidgetItem(self.channel_activities_list)
            widget_item = ChannelActivityListItem(self.channel_activities_list)
            item.setSizeHint(widget_item.sizeHint())
            self.channel_activities_list.setItemWidget(item, widget_item)

        # fetch the settings
        self.tribler_request_manager.get_settings()

        self.event_request_manager = EventRequestManager()
        self.event_request_manager.received_free_space.connect(self.received_free_space)

        # Set profile image
        placeholder_pix = QPixmap("images/profile_placeholder.jpg")
        placeholder_pix = placeholder_pix.scaledToHeight(self.my_profile_button.width(), Qt.SmoothTransformation)
        placeholder_pix = create_rounded_image(placeholder_pix)
        self.my_profile_button.setIcon(QIcon(placeholder_pix))
        self.my_profile_button.setIconSize(QSize(self.my_profile_button.width(), self.my_profile_button.height()))

        self.left_menu.hide()

        self.video_player_page.initialize_player()
        self.my_channel_page.initialize_my_channel_page()

        self.downloads_tab = self.findChild(QWidget, "downloads_tab")
        self.downloads_tab.initialize()
        self.downloads_tab.clicked_tab_button.connect(self.on_downloads_tab_button_clicked)

        # TODO Martijn: for now, fill the downloads with some dummy data
        self.downloads_list = self.findChild(QTreeWidget, "downloads_list")

        for i in range(0, 10):
            item = QTreeWidgetItem(self.downloads_list)
            item.setSizeHint(0, QSize(-1, 24))
            item.setSizeHint(2, QSize(-1, 1))
            item.setText(0, "My.test.torrent.HD.iso")
            item.setText(1, "301.1 MB")

            slider = QProgressBar()
            slider.setStyleSheet("""
            QProgressBar {
                margin: 4px;
                background-color: white;
                color: #ddd;
                font-size: 12px;
                text-align: center;
             }

             QProgressBar::chunk {
                background-color: #e67300;
             }
            """)
            slider.setValue(58)
            self.downloads_list.setItemWidget(item, 2, slider)

            item.setText(3, "Downloading")
            item.setText(4, "4")
            item.setText(5, "5")
            item.setText(6, "801.3 KB")
            item.setText(7, "0.4 KB")
            item.setText(8, "34:12:03")

        self.show()

    def received_free_space(self, free_space):
        self.statusBar.set_free_space(free_space)

    def received_channels(self, json_results):
        self.channels_list.clear()
        results = json.loads(json_results)

        delay = 0
        for result in results['channels']:
            item = QListWidgetItem(self.channels_list)
            item.setSizeHint(QSize(-1, 60))
            item.setData(Qt.UserRole, result)
            widget_item = ChannelListItem(self.channels_list, delay, result)
            self.channels_list.addItem(item)
            self.channels_list.setItemWidget(item, widget_item)
            delay += 50

    def received_subscribed_channels(self, json_results):
        self.subscribed_channels_list.clear()
        results = json.loads(json_results)

        delay = 0
        for result in results['subscribed']:
            item = QListWidgetItem(self.subscribed_channels_list)
            item.setSizeHint(QSize(-1, 60))
            item.setData(Qt.UserRole, result)
            widget_item = ChannelListItem(self.subscribed_channels_list, delay, result)
            self.subscribed_channels_list.addItem(item)
            self.subscribed_channels_list.setItemWidget(item, widget_item)
            delay += 50

    def received_search_results(self, json_results):
        self.channels_list.clear()
        results = json.loads(json_results)

        delay = 0
        for result in results['channels']:
            item = QListWidgetItem(self.channels_list)
            item.setSizeHint(QSize(-1, 60))
            item.setData(Qt.UserRole, result)
            widget_item = ChannelListItem(self.channels_list, delay, result)
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

    def received_settings(self, json_results):
        results = json.loads(json_results)
        self.video_player_page.video_player_port = results['video']['port']
        self.settings = json.loads(json_results)

        # fetch popular channels and display them
        self.tribler_request_manager.get_channels()

    def on_top_search_button_click(self):
        self.stackedWidget.setCurrentIndex(PAGE_CHANNELS_OVERVIEW)
        self.tribler_request_manager.search_channels(self.top_search_bar.text())

    def on_top_menu_button_click(self):
        if self.left_menu.isHidden():
            self.left_menu.show()
        else:
            self.left_menu.hide()

    def on_channel_tab_button_clicked(self, button_name):
        if button_name == "channel_content_button":
            self.channel_stacked_widget.setCurrentIndex(PAGE_CHANNEL_CONTENT)
        elif button_name == "channel_comments_button":
            self.channel_stacked_widget.setCurrentIndex(PAGE_CHANNEL_COMMENTS)
        elif button_name == "channel_activity_button":
            self.channel_stacked_widget.setCurrentIndex(PAGE_CHANNEL_ACTIVITY)

    def on_downloads_tab_button_clicked(self, button_name):
        print button_name

    def clicked_menu_button(self, menu_button_name):
        # Deselect menu buttons
        for button in self.menu_buttons:
            button.unselectMenuButton()

        if menu_button_name == "left_menu_home_button":
            self.left_menu_home_button.selectMenuButton()
            self.stackedWidget.setCurrentIndex(PAGE_HOME)
        elif menu_button_name == "left_menu_my_channel_button":
            self.left_menu_my_channel_button.selectMenuButton()
            self.stackedWidget.setCurrentIndex(PAGE_MY_CHANNEL)
        elif menu_button_name == "left_menu_videoplayer_button":
            self.left_menu_videoplayer_button.selectMenuButton()
            self.stackedWidget.setCurrentIndex(PAGE_VIDEO_PLAYER)
        elif menu_button_name == "left_menu_downloads_button":
            self.left_menu_downloads_button.selectMenuButton()
            self.stackedWidget.setCurrentIndex(PAGE_DOWNLOADS)
        elif menu_button_name == "left_menu_settings_button":
            self.left_menu_settings_button.selectMenuButton()
            self.stackedWidget.setCurrentIndex(PAGE_SETTINGS)
        elif menu_button_name == "left_menu_subscribed_button":
            self.left_menu_subscribed_button.selectMenuButton()
            self.tribler_request_manager.get_subscribed_channels()
            self.stackedWidget.setCurrentIndex(PAGE_SUBSCRIBED_CHANNELS)
        self.navigation_stack = []

    def on_channel_item_click(self, channel_list_item):
        channel_info = channel_list_item.data(Qt.UserRole)
        self.tribler_request_manager.get_torrents_in_channel(str(channel_info['id']))
        self.navigation_stack.append(self.stackedWidget.currentIndex())
        self.stackedWidget.setCurrentIndex(PAGE_CHANNEL_DETAILS)

        # initialize the page about a channel
        channel_detail_pane = self.findChild(QWidget, "channel_details")
        channel_name_label = channel_detail_pane.findChild(QLabel, "channel_name_label")
        channel_num_subs_label = channel_detail_pane.findChild(QLabel, "channel_num_subs_label")

        channel_name_label.setText(channel_info['name'])
        channel_num_subs_label.setText(str(channel_info['votes']))

    def on_page_back_clicked(self):
        prev_page = self.navigation_stack.pop()
        self.stackedWidget.setCurrentIndex(prev_page)

    def resizeEvent(self, event):
        self.resize_event.emit()

app = QApplication(sys.argv)
window = TriblerWindow()
window.setWindowTitle("Tribler")
sys.exit(app.exec_())
