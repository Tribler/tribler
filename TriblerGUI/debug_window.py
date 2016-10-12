from time import localtime, strftime

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QTreeWidgetItem

from TriblerGUI.utilities import get_ui_file_path
from TriblerGUI.tribler_request_manager import performed_requests as tribler_performed_requests, TriblerRequestManager


class DebugWindow(QMainWindow):

    def __init__(self):
        super(DebugWindow, self).__init__()

        uic.loadUi(get_ui_file_path('debugwindow.ui'), self)
        self.setWindowTitle("Tribler debug pane")

        self.window().debug_tab_widget.setCurrentIndex(0)
        self.window().debug_tab_widget.currentChanged.connect(self.tab_changed)

    def tab_changed(self, index):
        if index == 1:
            self.load_requests_tab()
        elif index == 2:
            self.load_multichain_tab()

    def load_requests_tab(self):
        self.window().requests_tree_widget.clear()
        for endpoint, method, data, timestamp, status_code in sorted(tribler_performed_requests.values(), key=lambda x: x[3]):
            item = QTreeWidgetItem(self.window().requests_tree_widget)
            item.setText(0, "%s %s %s" % (method, endpoint, data))
            item.setText(1, "%d" % status_code)
            item.setText(2, "%s" % strftime("%H:%M:%S", localtime(timestamp)))
            self.window().requests_tree_widget.addTopLevelItem(item)

    def load_multichain_tab(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("multichain/statistics", self.on_multichain_statistics)

    def on_multichain_statistics(self, data):
        self.window().multichain_tree_widget.clear()
        for key, value in data["statistics"].iteritems():
            item = QTreeWidgetItem(self.window().multichain_tree_widget)
            item.setText(0, key)
            item.setText(1, "%s" % value)
            self.window().multichain_tree_widget.addTopLevelItem(item)
