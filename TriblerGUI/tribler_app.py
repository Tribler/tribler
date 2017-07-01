import os

from PyQt5.QtCore import QEvent
from TriblerGUI.single_application import QtSingleApplication
# QtWebEngineWidgets must be imported before a QCoreApplication instance is created, otherwise an import error occurs
# see: https://stackoverflow.com/questions/41172301/pyqt-modules-cant-be-imported-after-qtwidgets-qapplicationsys-argv
# TODO: Remove this if-statement when QtWebEngineWidgets is available for the GUI tests
if os.environ.get("TEST_GUI") != "yes":
    # TODO: Remove this try-except clause when QtWebEngineWidgets is a hard dependency
    try:
        from PyQt5.QtWebEngineWidgets import QWebEngineView
    except ImportError:
        # In the case QWebEngineView is not available, render the graph trust page.
        pass


class TriblerApplication(QtSingleApplication):
    """
    This class represents the main Tribler application.
    """
    def __init__(self, app_name, args):
        QtSingleApplication.__init__(self, app_name, args)
        self.messageReceived.connect(self.on_app_message)

    def on_app_message(self, msg):
        if msg.startswith('file') or msg.startswith('magnet'):
            self.handle_uri(msg)

    def handle_uri(self, uri):
        self.activation_window().pending_uri_requests.append(uri)
        if self.activation_window().tribler_started and not self.activation_window().start_download_dialog_active:
            self.activation_window().process_uri_request()

    def parse_sys_args(self, args):
        for arg in args[1:]:
            if os.path.exists(arg):
                self.handle_uri('file:%s' % arg)
            elif arg.startswith('magnet'):
                self.handle_uri(arg)

    def event(self, event):
        if event.type() == QEvent.FileOpen and event.file().endswith(".torrent"):
            self.handle_uri('file:%s' % event.file())
        return QtSingleApplication.event(self, event)
