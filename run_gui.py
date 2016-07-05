# TODO martijn: temporary solution to convince VLC to find the plugin path
import os

import sys

from TriblerGUI.single_application import QtSingleApplication
from TriblerGUI.tribler_window import TriblerWindow

os.environ['VLC_PLUGIN_PATH'] = '/Applications/VLC.app/Contents/MacOS/plugins'

app = QtSingleApplication("triblerapp2", sys.argv)

if app.isRunning():
    sys.exit(1)

window = TriblerWindow()
window.setWindowTitle("Tribler")
app.setActivationWindow(window)
sys.exit(app.exec_())
