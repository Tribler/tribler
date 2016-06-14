# TODO martijn: temporary solution to convince VLC to find the plugin path
import os

import sys
from PyQt5.QtWidgets import QApplication

from TriblerGUI.tribler_window import TriblerWindow

os.environ['VLC_PLUGIN_PATH'] = '/Applications/VLC.app/Contents/MacOS/plugins'

app = QApplication(sys.argv)
window = TriblerWindow()
window.setWindowTitle("Tribler")
sys.exit(app.exec_())
