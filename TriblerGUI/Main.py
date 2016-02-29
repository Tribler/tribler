import json
import sys
from PyQt5 import uic
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QMainWindow, QListView, QListWidget, QLineEdit, QListWidgetItem, QApplication, QToolButton

from TriblerGUI.channel_list_item import ChannelListItem
from TriblerGUI.event_request_manager import EventRequestManager
from TriblerGUI.search_request_manager import SearchRequestManager


class TriblerWindow(QMainWindow):

    def __init__(self):
        super(TriblerWindow, self).__init__()

        uic.loadUi('qt_resources/mainwindow.ui', self)

        # Remove the focus rect on OS X
        [widget.setAttribute(Qt.WA_MacShowFocusRect, 0) for widget in self.findChildren(QLineEdit) + self.findChildren(QListView)]

        self.channels_list = self.findChild(QListWidget, "channels_list")
        self.top_search_bar = self.findChild(QLineEdit, "top_search_bar")
        self.top_search_button = self.findChild(QToolButton, "top_search_button")

        self.top_search_bar.returnPressed.connect(self.on_top_search_button_click)
        self.top_search_button.clicked.connect(self.on_top_search_button_click)

        self.stackedWidget.setCurrentIndex(0)

        self.channels_list.itemClicked.connect(self.on_channel_item_click)

        self.search_request_manager = SearchRequestManager()
        self.search_request_manager.received_search_results.connect(self.received_search_results)

        self.event_request_manager = EventRequestManager()
        self.event_request_manager.received_free_space.connect(self.received_free_space)

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

    def on_top_search_button_click(self):
        self.search_request_manager.search_channels(self.top_search_bar.text())

    def on_channel_item_click(self, channel_list_item):
        self.stackedWidget.setCurrentIndex(1)

app = QApplication(sys.argv)
window = TriblerWindow()
window.setWindowTitle("Tribler")
sys.exit(app.exec_())
