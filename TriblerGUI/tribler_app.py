import os

from PyQt5.QtCore import QEvent
from TriblerGUI.single_application import QtSingleApplication


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
        if not self.activation_window().tribler_started:
            self.activation_window().pending_uri_requests.append(uri)
        else:
            if uri.startswith('file'):
                self.activation_window().on_selected_torrent_file(uri[5:])
            elif uri.startswith('magnet'):
                self.activation_window().on_added_magnetlink(uri)

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
