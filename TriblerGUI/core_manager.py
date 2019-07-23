from __future__ import absolute_import

import os
import subprocess
import sys

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication

from six import PY3, text_type

from twisted.internet.error import ReactorAlreadyInstalledError

# We always use a selectreactor
try:
    from twisted.internet import selectreactor
    selectreactor.install()
except ReactorAlreadyInstalledError:
    pass

from TriblerGUI.event_request_manager import EventRequestManager
from TriblerGUI.tribler_request_manager import QueuePriorityEnum, TriblerRequestManager
from TriblerGUI.utilities import get_base_path, is_frozen

START_FAKE_API = False


class CoreManager(QObject):
    """
    The CoreManager is responsible for managing the Tribler core (starting/stopping). When we are running the GUI tests,
    a fake API will be started.
    """
    tribler_stopped = pyqtSignal()
    core_state_update = pyqtSignal(str)

    def __init__(self, api_port):
        QObject.__init__(self, None)

        self.base_path = get_base_path()
        if not is_frozen():
            self.base_path = os.path.join(get_base_path(), "..")

        self.request_mgr = None
        self.core_process = None
        self.api_port = api_port
        self.events_manager = EventRequestManager(self.api_port)

        self.shutting_down = False
        self.recorded_stderr = ""
        self.use_existing_core = True
        self.is_core_running = False

        self.stop_timer = QTimer()
        self.stop_timer.timeout.connect(self.check_stopped)

        self.check_state_timer = QTimer()

    def check_stopped(self):
        """
        Checks if the core has stopped. Note that this method is called by stop timer which is called when trying to
        stop the core manager.
        There could be two cases when we stop the timer.
        1. Core process is None. This means some external core process was used (could be run through twistd plugin)
        which we don't kill so we stop the timer here.
        2. Core process poll method returns non None value. The return value of poll method is None if the process
        has not terminated so for any non None value we stop the timer.
        """
        if not self.core_process or self.core_process.poll() is not None:
            self.stop_timer.stop()
            self.on_finished()

    def start(self, core_args=None, core_env=None):
        """
        First test whether we already have a Tribler process listening on port 8085. If so, use that one and don't
        start a new, fresh session.
        """
        def on_request_error(_):
            self.use_existing_core = False
            self.start_tribler_core(core_args=core_args, core_env=core_env)

        self.events_manager.connect()
        self.events_manager.reply.error.connect(on_request_error)

    def start_tribler_core(self, core_args=None, core_env=None):
        if not START_FAKE_API:
            if not core_env:
                if PY3:
                    core_env = os.environ.copy()
                else:
                    system_encoding = sys.getfilesystemencoding()
                    core_env = {(k.encode(system_encoding) if isinstance(k, text_type) else str(k)):
                                    (v.encode(system_encoding) if isinstance(v, text_type) else str(v))
                                for k, v in os.environ.copy().items()}
                core_env["CORE_PROCESS"] = "1"
                core_env["CORE_BASE_PATH"] = self.base_path
                core_env["CORE_API_PORT"] = "%s" % self.api_port
            if not core_args:
                core_args = sys.argv
            self.core_process = subprocess.Popen([sys.executable] + core_args, env=core_env)
        self.check_core_ready()

    def check_core_ready(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("state", self.on_received_state, capture_errors=False,
                                         priority=QueuePriorityEnum.CRITICAL)

    def on_received_state(self, state):
        if not state or 'state' not in state or state['state'] not in ['STARTED', 'EXCEPTION']:
            self.check_state_timer = QTimer()
            self.check_state_timer.setSingleShot(True)
            self.check_state_timer.timeout.connect(self.check_core_ready)
            self.check_state_timer.start(50)
            return

        self.core_state_update.emit(state['readable_state'])

        if state['state'] == 'STARTED':
            self.events_manager.connect(reschedule_on_err=False)
            self.is_core_running = True
        elif state['state'] == 'EXCEPTION':
            raise RuntimeError(state['last_exception'])

    def stop(self, stop_app_on_shutdown=True):
        if self.core_process or self.is_core_running:
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
