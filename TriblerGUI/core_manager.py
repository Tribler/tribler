import logging
from threading import Thread

import keyring
from twisted.internet.error import ReactorAlreadyInstalledError

# We always use a selectreactor
from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.Utilities.install_dir import get_lib_path
from TriblerGUI.defs import API_PORT

try:
    from twisted.internet import selectreactor
    selectreactor.install()
except ReactorAlreadyInstalledError:
    pass

import multiprocessing
import os
import sys
from PyQt5.QtCore import QTimer, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication
import signal
from Tribler.Core.Modules.process_checker import ProcessChecker
from Tribler.Core.Session import Session

from TriblerGUI.event_request_manager import EventRequestManager
from TriblerGUI.tribler_request_manager import TriblerRequestManager, QueuePriorityEnum
from TriblerGUI.utilities import get_base_path, is_frozen

START_FAKE_API = False


def start_tribler_core(base_path, child_pipe):
    """
    This method is invoked by multiprocessing when the Tribler core is started and will start a Tribler session.
    Note that there is no direct communication between the GUI process and the core: all communication is performed
    through the HTTP API.
    """
    from twisted.internet import reactor
    from check_os import setup_core_logging
    setup_core_logging()

    def on_tribler_shutdown(_):
        reactor.stop()

    def shutdown(session, *_):
        logging.info("Stopping Tribler core")
        session.shutdown().addCallback(on_tribler_shutdown)

    sys.path.insert(0, base_path)

    def get_keyring_password(service, username):
        child_pipe.send(('get_keyring_password', {'service': service, 'username': username}))
        return child_pipe.recv()

    def set_keyring_password(service, username, password):
        child_pipe.send(('set_keyring_password', {'service': service, 'username': username, 'password': password}))
        child_pipe.recv()

    def patch_wallet_methods():
        try:
            from Tribler.community.market.wallet.btc_wallet import BitcoinWallet
            BitcoinWallet.get_wallet_password = lambda _: get_keyring_password('tribler', 'btc_wallet_password')
            BitcoinWallet.set_wallet_password = lambda _, password: set_keyring_password('tribler',
                                                                                         'btc_wallet_password',
                                                                                         password)
        except ImportError:
            pass

    def patch_iom_methods():
        try:
            sys.path.append(os.path.join(get_lib_path(), 'internetofmoney'))

            get_symmetric_key = lambda _: get_keyring_password('internetofmoney', 'symmetric_key')
            set_symmetric_key = lambda _, password: set_keyring_password('internetofmoney', 'symmetric_key', password)

            from Tribler.internetofmoney.Managers.ABN.ABNManager import ABNManager
            ABNManager.get_symmetric_key = get_symmetric_key
            ABNManager.set_symmetric_key = set_symmetric_key

            from Tribler.internetofmoney.Managers.PayPal.PayPalManager import PayPalManager
            PayPalManager.get_symmetric_key = get_symmetric_key
            PayPalManager.set_symmetric_key = set_symmetric_key

            from Tribler.internetofmoney.Managers.Rabo.RaboManager import RaboManager
            RaboManager.get_symmetric_key = get_symmetric_key
            RaboManager.set_symmetric_key = set_symmetric_key
        except ImportError:
            pass

    def start_tribler():
        config = TriblerConfig()
        patch_wallet_methods()
        patch_iom_methods()

        config.set_http_api_port(API_PORT)
        config.set_http_api_enabled(True)

        # Check if we are already running a Tribler instance
        process_checker = ProcessChecker(config.get_state_dir())
        if process_checker.already_running:
            return
        else:
            process_checker.create_lock_file()

        session = Session(config)

        signal.signal(signal.SIGTERM, lambda signum, stack: shutdown(session, signum, stack))
        session.start()

    reactor.callWhenRunning(start_tribler)
    reactor.run()


class CoreManager(QObject):
    """
    The CoreManager is responsible for managing the Tribler core (starting/stopping). When we are running the GUI tests,
    a fake API will be started.
    """
    tribler_stopped = pyqtSignal()
    core_state_update = pyqtSignal(str)

    def __init__(self):
        QObject.__init__(self, None)

        self.base_path = get_base_path()
        if not is_frozen():
            self.base_path = os.path.join(get_base_path(), "..")

        self.request_mgr = None
        self.core_process = None
        self.events_manager = EventRequestManager()

        self.shutting_down = False
        self.recorded_stderr = ""
        self.use_existing_core = True

        self.stop_timer = QTimer()
        self.stop_timer.timeout.connect(self.check_stopped)

        self.check_state_timer = QTimer()

    def check_stopped(self):
        if not self.core_process.is_alive():
            self.stop_timer.stop()
            self.on_finished()

    def start(self):
        """
        First test whether we already have a Tribler process listening on port 8085. If so, use that one and don't
        start a new, fresh session.
        """
        def on_request_error(_):
            self.use_existing_core = False
            self.start_tribler_core()

        self.events_manager.connect(reschedule_on_err=False)
        self.events_manager.reply.error.connect(on_request_error)

    def pipe_wait(self, child_conn):
        """
        This method is executed in a separate thread and is only here since there are some calls that are crashing on
        macOS in a subprocess (due to libdispatch.dylib).
        """
        while True:
            cmd, arg = child_conn.recv()
            if cmd == "get_keyring_password":
                child_conn.send(keyring.get_password('tribler', arg['username']))
            elif cmd == "set_keyring_password":
                keyring.set_password('tribler', arg['username'], arg['password'])
                child_conn.send('done')

    def start_tribler_core(self):
        if START_FAKE_API:
            from TriblerGUI.scripts.start_fake_core import start_fake_core
            self.core_process = multiprocessing.Process(target=start_fake_core, args=(API_PORT,))
        else:
            parent_conn, child_conn = multiprocessing.Pipe()
            self.core_process = multiprocessing.Process(target=start_tribler_core, args=(self.base_path, child_conn))

            pipe_thread = Thread(target=lambda: self.pipe_wait(parent_conn), name="tribler-pipe-read")
            pipe_thread.setDaemon(True)
            pipe_thread.start()

        self.core_process.start()
        self.check_core_ready()

    def check_core_ready(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("state", self.on_received_state, capture_errors=False,
                                         priority=QueuePriorityEnum.CRITICAL)

    def on_received_state(self, state):
        if not state or state['state'] not in ['STARTED', 'EXCEPTION']:
            self.check_state_timer = QTimer()
            self.check_state_timer.setSingleShot(True)
            self.check_state_timer.timeout.connect(self.check_core_ready)
            self.check_state_timer.start(50)
            return

        self.core_state_update.emit(state['readable_state'])

        if state['state'] == 'STARTED':
            self.events_manager.connect(reschedule_on_err=False)
        elif state['state'] == 'EXCEPTION':
            raise RuntimeError(state['last_exception'])

    def stop(self, stop_app_on_shutdown=True):
        if self.core_process:
            self.events_manager.shutting_down = True
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("shutdown", lambda _: None, method="PUT",
                                             priority=QueuePriorityEnum.CRITICAL)

            if stop_app_on_shutdown:
                self.stop_timer.start(100)

    def throw_core_exception(self):
        raise RuntimeError(self.recorded_stderr)

    def on_finished(self):
        self.tribler_stopped.emit()
        if self.shutting_down:
            QApplication.quit()
