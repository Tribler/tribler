import sys
from PyQt5 import uic
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QMainWindow, QListView, QListWidget, QLineEdit, QListWidgetItem, QApplication

from TriblerGUI.channel_list_item import ChannelListItem
from TriblerGUI.event_request_manager import EventRequestManager


class TriblerWindow(QMainWindow):

    def __init__(self):
        super(TriblerWindow, self).__init__()

        uic.loadUi('qt_resources/mainwindow.ui', self)

        # Remove the focus rect on OS X
        [widget.setAttribute(Qt.WA_MacShowFocusRect, 0) for widget in self.findChildren(QLineEdit) + self.findChildren(QListView)]

        self.channels_list = self.findChild(QListWidget, "channels_list")

        self.stackedWidget.setCurrentIndex(0)

        # Create some dummy channel items
        for i in range(0, 6):
            item = QListWidgetItem(self.channels_list)
            item.setSizeHint(QSize(-1, 60))
            widget_item = ChannelListItem(self.channels_list)
            self.channels_list.addItem(item)
            self.channels_list.setItemWidget(item, widget_item)

        self.event_request_manager = EventRequestManager()

        self.event_request_manager.received_free_space.connect(self.received_free_space)

        self.show()

    def received_free_space(self, free_space):
        self.statusBar.set_free_space(free_space)

app = QApplication(sys.argv)
window = TriblerWindow()
window.setWindowTitle("Tribler")
sys.exit(app.exec_())
