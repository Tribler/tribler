import os
import os.path
import sys

from PyQt5.QtCore import QCoreApplication, QEvent, Qt

from tribler.core.utilities.rest_utils import path_to_url
from tribler.core.utilities.unicode import ensure_unicode
from tribler.gui.code_executor import CodeExecutor
from tribler.gui.single_application import QtSingleApplication
from tribler.gui.utilities import connect

# Set the QT application parameters before creating any instances of the application.
QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"


# fmt: off

class TriblerApplication(QtSingleApplication):
    """
    This class represents the main Tribler application.
    """

    def __init__(self, app_name: str, args, another_process_is_primary: bool = False):
        QtSingleApplication.__init__(self, app_name, another_process_is_primary, args)
        self.code_executor = None
        connect(self.message_received, self.on_app_message)

    def on_app_message(self, msg):
        if msg.startswith('file') or msg.startswith('magnet'):
            self.handle_uri(msg)

    def handle_uri(self, uri):
        if self.tribler_window:
            self.tribler_window.handle_uri(uri)

    def parse_sys_args(self, args):
        for arg in args[1:]:
            if os.path.exists(arg):
                file_path = ensure_unicode(arg, 'utf8')
                uri = path_to_url(file_path)
                self.handle_uri(uri)
            elif arg.startswith('magnet'):
                self.handle_uri(arg)

        if '--allow-code-injection' in sys.argv[1:]:
            variables = globals().copy()
            variables.update(locals())
            variables['window'] = self.tribler_window
            self.code_executor = CodeExecutor(5500, shell_variables=variables)
            connect(self.tribler_window.events_manager.core_connected, self.code_executor.on_core_connected)
            connect(self.tribler_window.tribler_crashed, self.code_executor.on_crash)


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
            uri = path_to_url(event.file())
            self.handle_uri(uri)
        return QtSingleApplication.event(self, event)
