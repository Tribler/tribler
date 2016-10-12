import os
import sys
from PyQt5.QtCore import QProcess, QProcessEnvironment
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

    def start(self):
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

    def on_ready_read_stderr(self):
        sys.stderr.write(self.core_process.readAllStandardError())
        sys.stderr.flush()

    def on_finished(self):
        if self.shutting_down:
            QApplication.quit()
