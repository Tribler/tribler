import os
import sys
from PyQt5.QtCore import QProcess, QProcessEnvironment, QTimer
from PyQt5.QtWidgets import QApplication
import TriblerGUI

from TriblerGUI.event_request_manager import EventRequestManager
from TriblerGUI.utilities import get_base_path, is_frozen

START_FAKE_API = True


class CoreManager(object):

    def __init__(self, api_port):
        environment = QProcessEnvironment.systemEnvironment()

        environment.insert("base_path", get_base_path())
        if not is_frozen():
            environment.insert("base_path", os.path.join(get_base_path(), ".."))

        self.api_port = api_port

        self.core_process = QProcess()
        self.core_process.setProcessEnvironment(environment)
        self.core_process.readyReadStandardOutput.connect(self.on_ready_read_stdout)
        self.core_process.readyReadStandardError.connect(self.on_ready_read_stderr)
        self.core_process.finished.connect(self.on_finished)
        self.events_manager = EventRequestManager(api_port)

        self.shutting_down = False
        self.recorded_stderr = ""
        self.use_existing_core = True

    def start(self):
        """
        First test whether we already have a Tribler process listening on port 8085. If so, use that one and don't
        start a new, fresh session.
        """
        def on_request_error(_):
            self.use_existing_core = False
            self.start_tribler_core()

        self.events_manager.connect()
        self.events_manager.reply.error.connect(on_request_error)

    def start_tribler_core(self):
        core_script_path = os.path.join(get_base_path(), 'scripts',
                                        'start_fake_core.py' if START_FAKE_API else 'start_core.py')
        if START_FAKE_API:
            self.core_process.start("python %s %d" % (core_script_path, self.api_port))
        else:
            self.core_process.start("python %s -n tribler" % core_script_path)

        self.events_manager.connect()

    def stop(self):
        self.core_process.terminate()

    def kill(self):
        self.core_process.kill()

    def on_ready_read_stdout(self):
        print("Tribler core: %s" % str(self.core_process.readAllStandardOutput()).rstrip())

    def throw_core_exception(self):
        raise RuntimeError(self.recorded_stderr)

    def on_ready_read_stderr(self):
        std_output = self.core_process.readAllStandardError()
        self.recorded_stderr += std_output

        # Check whether we have an exception
        has_exception = False
        for err_line in std_output.split('\n'):
            if "Traceback" in err_line:
                has_exception =True
                break

        if has_exception:
            self.timer = QTimer()
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self.throw_core_exception)
            self.timer.start(1000)

        sys.stderr.write(std_output)
        sys.stderr.flush()

    def on_finished(self):
        if self.shutting_down:
            QApplication.quit()
