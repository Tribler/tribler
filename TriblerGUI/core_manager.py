import os
import sys
from PyQt5.QtCore import QProcess
from PyQt5.QtWidgets import QApplication
import TriblerGUI

from TriblerGUI.event_request_manager import EventRequestManager


START_FAKE_API = False


class CoreManager(object):

    def __init__(self):
        self.core_process = QProcess()
        self.core_process.readyReadStandardOutput.connect(self.on_ready_read_stdout)
        self.core_process.readyReadStandardError.connect(self.on_ready_read_stderr)
        self.core_process.finished.connect(self.on_finished)
        self.events_manager = EventRequestManager()

        self.shutting_down = False

    def start(self):
        if START_FAKE_API:
            self.core_process.start("python %s/scripts/start_fake_core.py" % os.path.dirname(TriblerGUI.__file__))
        else:
            self.core_process.start("python %s/scripts/start_core.py -n tribler" % os.path.dirname(TriblerGUI.__file__))

        self.events_manager.connect()

    def stop(self):
        self.core_process.terminate()

    def kill(self):
        self.core_process.kill()

    def on_ready_read_stdout(self):
        print "Tribler core: %s" % str(self.core_process.readAllStandardOutput()).rstrip()

    def on_ready_read_stderr(self):
        sys.stderr.write(self.core_process.readAllStandardError())
        sys.stderr.flush()

    def on_finished(self):
        if self.shutting_down:
            QApplication.quit()
