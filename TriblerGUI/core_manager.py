import logging
from twisted.internet.error import ReactorAlreadyInstalledError

# We always use a selectreactor
try:
    from twisted.internet import selectreactor
    selectreactor.install()
except ReactorAlreadyInstalledError:
    pass

import multiprocessing
import os
import sys
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
import sqlite3
import signal
from Tribler.Core.Modules.process_checker import ProcessChecker
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig

from TriblerGUI.event_request_manager import EventRequestManager
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_base_path, is_frozen

START_FAKE_API = False


def start_tribler_core(base_path):
    """
    This method is invoked by multiprocessing when the Tribler core is started and will start a Tribler session.
    Note that there is no direct communication between the GUI process and the core: all communication is performed
    through the HTTP API.
    """
    from twisted.internet import reactor

    def on_tribler_shutdown(_):
        reactor.stop()

    def shutdown(session, *_):
        logging.info("Stopping Tribler core")
        session.shutdown().addCallback(on_tribler_shutdown)

    sys.path.insert(0, base_path)

    def start_tribler():
        config = SessionStartupConfig().load()
        config.set_http_api_port(8085)
        config.set_http_api_enabled(True)

        # Check if we are already running a Tribler instance
        process_checker = ProcessChecker()
        if process_checker.already_running:
            return

        session = Session(config)

        signal.signal(signal.SIGTERM, lambda signum, stack: shutdown(session, signum, stack))
        session.start()

    reactor.callWhenRunning(start_tribler)
    reactor.run()


class CoreManager(object):
    """
    The CoreManager is responsible for managing the Tribler core (starting/stopping). When we are running the GUI tests,
    a fake API will be started.
    """

    def __init__(self, api_port):
        self.base_path = get_base_path()
        if not is_frozen():
            self.base_path = os.path.join(get_base_path(), "..")

        self.api_port = api_port

        self.request_mgr = None
        self.core_process = None
        self.events_manager = EventRequestManager(api_port)

        self.shutting_down = False
        self.recorded_stderr = ""
        self.use_existing_core = True

        self.stop_timer = QTimer()
        self.stop_timer.timeout.connect(self.check_stopped)

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

    def start_tribler_core(self):
        if START_FAKE_API:
            from TriblerGUI.scripts.start_fake_core import start_fake_core
            self.core_process = multiprocessing.Process(target=start_fake_core, args=(self.api_port,))
        else:
            # Workaround for MacOS
            sqlite3.connect(':memory:').close()

            self.core_process = multiprocessing.Process(target=start_tribler_core, args=(self.base_path,))
        self.core_process.start()
        self.check_core_ready()

    def check_core_ready(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("state", self.on_received_state, capture_errors=False)

    def on_received_state(self, state):
        if not state:
            self.check_core_ready()
        elif state['state'] == 'STARTED':
            self.events_manager.connect(reschedule_on_err=False)
        elif state['state'] == 'EXCEPTION':
            raise RuntimeError(state['last_exception'])
        else:
            self.check_core_ready()

    def stop(self):
        if self.core_process:
            self.core_process.terminate()
            self.stop_timer.start()

    def throw_core_exception(self):
        raise RuntimeError(self.recorded_stderr)

    def on_finished(self):
        if self.shutting_down:
            QApplication.quit()
