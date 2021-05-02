import os
import sys

from PyQt5.QtCore import QCoreApplication, QEvent, Qt

from tribler_core.utilities.unicode import ensure_unicode

from tribler_gui.code_executor import CodeExecutor
from tribler_gui.single_application import QtSingleApplication
from tribler_gui.utilities import connect

# Set the QT application parameters before creating any instances of the application.
QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = "1"


class TriblerApplication(QtSingleApplication):
    """
    This class represents the main Tribler application.
    """

    def __init__(self, app_name, args):
        QtSingleApplication.__init__(self, app_name, args)
        self.code_executor = None
        connect(self.messageReceived, self.on_app_message)

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
                self.handle_uri(f"file:{ensure_unicode(arg, 'utf8')}")
            elif arg.startswith('magnet'):
                self.handle_uri(arg)

        if '--allow-code-injection' in sys.argv[1:]:
            variables = globals().copy()
            variables.update(locals())
            variables['window'] = self.activation_window()
            self.code_executor = CodeExecutor(5500, shell_variables=variables)
            connect(self.activation_window().tribler_crashed, self.code_executor.on_crash)

        if '--testnet' in sys.argv[1:]:
            os.environ['TESTNET'] = "YES"
        if '--trustchain-testnet' in sys.argv[1:]:
            os.environ['TRUSTCHAIN_TESTNET'] = "YES"
        if '--chant-testnet' in sys.argv[1:]:
            os.environ['CHANT_TESTNET'] = "YES"
        if '--tunnel-testnet' in sys.argv[1:]:
            os.environ['TUNNEL_TESTNET'] = "YES"

    def event(self, event):
        if event.type() == QEvent.FileOpen and event.file().endswith(".torrent"):
            self.handle_uri(f'file:{event.file()}')
        return QtSingleApplication.event(self, event)
