from Queue import Empty
import multiprocessing
import os
import sys
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
import sqlite3
from twisted.python.log import addObserver
from Tribler.Core.Modules.process_checker import ProcessChecker
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig

from TriblerGUI.event_request_manager import EventRequestManager
from TriblerGUI.utilities import get_base_path, is_frozen

START_FAKE_API = False


def start_tribler_core(core_queue, base_path):
    from twisted.internet import reactor

    def unhandled_error_observer(event):
        if event['isError']:
            core_queue.put(event['log_text'])

    addObserver(unhandled_error_observer)

    def on_tribler_started(session):
        """
        We print a magic string when Tribler has started. While this solution is not pretty, it is more reliable than
        trying to connect to the events endpoint with an interval.
        """
        core_queue.put("TRIBLER_STARTED")

    sys.path.insert(0, base_path)

    def start_tribler():
        config = SessionStartupConfig()
        config.set_http_api_port(8085)
        config.set_http_api_enabled(True)

        # Check if we are already running a Tribler instance
        process_checker = ProcessChecker()
        if process_checker.already_running:
            #shutdown_process("Another Tribler instance is already using statedir %s" % config.get_state_dir())
            return

        session = Session(config)
        upgrader = session.prestart()
        if upgrader.failed:
            pass
            #shutdown_process("The upgrader failed: .Tribler directory backed up, aborting")

        session.start().addCallback(on_tribler_started)

    reactor.callWhenRunning(start_tribler)
    reactor.run()


class CoreManager(object):

    def __init__(self, api_port):
        self.base_path = get_base_path()
        if not is_frozen():
            self.base_path = os.path.join(get_base_path(), "..")

        self.api_port = api_port

        self.core_process = None
        self.events_manager = EventRequestManager(api_port)

        self.shutting_down = False
        self.recorded_stderr = ""
        self.use_existing_core = True
        self.core_queue = multiprocessing.Queue()

        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.check_queue)

        self.stop_timer = QTimer()
        self.stop_timer.timeout.connect(self.check_stopped)

    def check_queue(self):
        try:
            data = self.core_queue.get_nowait()
            if data == "TRIBLER_STARTED":
                self.events_manager.connect()
                self.queue_timer.stop()
                self.queue_timer.start(1000)
            else:
                raise RuntimeError(data)
        except Empty:
            pass

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
            print "got error - starting Tribler core..."
            self.use_existing_core = False
            self.start_tribler_core()

        self.events_manager.connect(reschedule_on_err=False)
        self.events_manager.reply.error.connect(on_request_error)

    def start_tribler_core(self):
        core_script_path = os.path.join(get_base_path(), 'scripts',
                                        'start_fake_core.py' if START_FAKE_API else 'start_core.py')
        if START_FAKE_API:
            self.core_process.start("python %s %d" % (core_script_path, self.api_port))
        else:
            # Workaround for MacOS
            sqlite3.connect(':memory:').close()

            self.core_process = multiprocessing.Process(target=start_tribler_core, args=(self.core_queue, self.base_path,))
            self.core_process.start()
            self.queue_timer.start(200)

    def stop(self):
        self.core_process.terminate()
        self.stop_timer.start()

    def throw_core_exception(self):
        raise RuntimeError(self.recorded_stderr)

    def on_finished(self):
        print "SUBPROCESS FINISHED"
        if self.shutting_down:
            QApplication.quit()
