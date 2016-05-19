import os
import sys

from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QListView, QLineEdit, QApplication, QTreeWidget, QSystemTrayIcon

from TriblerGUI.channel_list_item import ChannelListItem
from TriblerGUI.channel_torrent_list_item import ChannelTorrentListItem
from TriblerGUI.defs import PAGE_SEARCH_RESULTS, PAGE_CHANNEL_CONTENT, PAGE_CHANNEL_COMMENTS, PAGE_CHANNEL_ACTIVITY, \
    PAGE_HOME, PAGE_MY_CHANNEL, PAGE_VIDEO_PLAYER, PAGE_DOWNLOADS, PAGE_SETTINGS, PAGE_SUBSCRIBED_CHANNELS, \
    PAGE_CHANNEL_DETAILS
from TriblerGUI.dialogs.addtorrentdialog import AddTorrentDialog
from TriblerGUI.event_request_manager import EventRequestManager
from TriblerGUI.tribler_request_manager import TriblerRequestManager


# TODO martijn: temporary solution to convince VLC to find the plugin path
os.environ['VLC_PLUGIN_PATH'] = '/Applications/VLC.app/Contents/MacOS/plugins'


class TriblerWindow(QMainWindow):

    resize_event = pyqtSignal()

    def __init__(self):
        super(TriblerWindow, self).__init__()

        self.navigation_stack = []

        uic.loadUi('qt_resources/mainwindow.ui', self)

        # Remove the focus rect on OS X
        [widget.setAttribute(Qt.WA_MacShowFocusRect, 0) for widget in self.findChildren(QLineEdit) +
         self.findChildren(QListView) + self.findChildren(QTreeWidget)]

        self.menu_buttons = [self.left_menu_button_home, self.left_menu_button_my_channel,
                             self.left_menu_button_subscriptions, self.left_menu_button_video_player,
                             self.left_menu_button_settings, self.left_menu_button_downloads]

        self.channel_back_button.clicked.connect(self.on_page_back_clicked)

        self.channel_tab.initialize()
        self.channel_tab.clicked_tab_button.connect(self.on_channel_tab_button_clicked)

        # fetch the variables, needed for the video player port
        self.variables_request_mgr = TriblerRequestManager()
        self.variables_request_mgr.perform_request("variables", self.received_variables)

        self.event_request_manager = EventRequestManager()

        self.video_player_page.initialize_player()
        self.search_results_page.initialize_search_results_page()
        self.settings_page.initialize_settings_page()
        self.my_channel_page.initialize_my_channel_page()
        self.downloads_page.initialize_downloads_page()

        self.stackedWidget.setCurrentIndex(PAGE_HOME)

        # Create the system tray icon
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon()
            self.tray_icon.setIcon(QIcon(QPixmap("images/tribler.png")))
            self.tray_icon.show()

        self.show()

    def received_subscribed_channels(self, results):
        items = []
        for result in results['subscribed']:
            items.append((ChannelListItem, result))
        self.subscribed_channels_list.set_data_items(items)

    def received_torrents_in_channel(self, results):
        items = []
        for result in results['torrents']:
            items.append((ChannelTorrentListItem, result))
        self.channel_torrents_list.set_data_items(items)

    def received_variables(self, variables):
        self.video_player_page.video_player_port = variables["variables"]["ports"]["video~port"]

    def on_top_search_button_click(self):
        self.clicked_menu_button("-")
        self.stackedWidget.setCurrentIndex(PAGE_SEARCH_RESULTS)
        self.search_results_page.perform_search(self.top_search_bar.text())
        self.search_request_mgr = TriblerRequestManager()
        self.search_request_mgr.search_channels(self.top_search_bar.text(),
                                                self.search_results_page.received_search_results)

    def on_add_torrent_button_click(self):
        self.add_torrent_dialog = AddTorrentDialog(self)
        self.add_torrent_dialog.show()

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

    def deselect_all_menu_buttons(self, except_select=None):
        for button in self.menu_buttons:
            if button == except_select:
                continue
            button.setChecked(False)

    def clicked_menu_button_home(self):
        self.deselect_all_menu_buttons(self.left_menu_button_home)
        self.stackedWidget.setCurrentIndex(PAGE_HOME)
        self.navigation_stack = []

    def clicked_menu_button_my_channel(self):
        self.deselect_all_menu_buttons(self.left_menu_button_my_channel)
        self.stackedWidget.setCurrentIndex(PAGE_MY_CHANNEL)
        self.my_channel_page.load_my_channel_overview()
        self.navigation_stack = []

    def clicked_menu_button_video_player(self):
        self.deselect_all_menu_buttons(self.left_menu_button_video_player)
        self.stackedWidget.setCurrentIndex(PAGE_VIDEO_PLAYER)
        self.navigation_stack = []

    def clicked_menu_button_downloads(self):
        self.deselect_all_menu_buttons(self.left_menu_button_downloads)
        self.stackedWidget.setCurrentIndex(PAGE_DOWNLOADS)
        self.navigation_stack = []
        self.downloads_page.load_downloads()

    def clicked_menu_button_settings(self):
        self.deselect_all_menu_buttons(self.left_menu_button_settings)
        self.stackedWidget.setCurrentIndex(PAGE_SETTINGS)
        self.settings_page.load_settings()
        self.navigation_stack = []

    def clicked_menu_button_subscriptions(self):
        self.deselect_all_menu_buttons(self.left_menu_button_subscriptions)
        self.subscribed_channels_request_manager = TriblerRequestManager()
        self.subscribed_channels_request_manager.perform_request("channels/subscribed", self.received_subscribed_channels)
        self.stackedWidget.setCurrentIndex(PAGE_SUBSCRIBED_CHANNELS)
        self.navigation_stack = []

    def on_channel_item_click(self, channel_list_item):
        channel_info = channel_list_item.data(Qt.UserRole)
        self.get_torents_in_channel_manager = TriblerRequestManager()
        self.get_torents_in_channel_manager.perform_request("channels/%s/torrents" % channel_info['dispersy_cid'], self.received_torrents_in_channel)
        self.navigation_stack.append(self.stackedWidget.currentIndex())
        self.stackedWidget.setCurrentIndex(PAGE_CHANNEL_DETAILS)

        # initialize the page about a channel
        self.channel_name_label.setText(channel_info['name'])
        self.channel_num_subs_label.setText(str(channel_info['votes']))

    def on_page_back_clicked(self):
        prev_page = self.navigation_stack.pop()
        self.stackedWidget.setCurrentIndex(prev_page)

    def resizeEvent(self, event):
        self.resize_event.emit()

app = QApplication(sys.argv)
window = TriblerWindow()
window.setWindowTitle("Tribler")
sys.exit(app.exec_())
