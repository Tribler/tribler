import os
import sys

from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication

from TriblerGUI.code_executor import CodeExecutor
from TriblerGUI.single_application import QtSingleApplication


class TriblerApplication(QtSingleApplication):
    """
    This class represents the main Tribler application.
    """
    def __init__(self, app_name, args):
        QApplication.__init__(self, args)
        self.code_executor = None
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

        if '--allow-code-injection' in sys.argv[1:]:
            variables = globals().copy()
            variables.update(locals())
            variables['window'] = self.activation_window()
            self.code_executor = CodeExecutor(5500, shell_variables=variables)
            self.activation_window().tribler_crashed.connect(self.code_executor.on_crash)

        if '--testnet' in sys.argv[1:]:
            os.environ['TESTNET'] = "YES"

    def event(self, event):
        if event.type() == QEvent.FileOpen and event.file().endswith(".torrent"):
            self.handle_uri('file:%s' % event.file())
        return QtSingleApplication.event(self, event)
