from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QProgressBar

from tribler_gui.utilities import connect


class TimeoutProgressBar(QProgressBar):

    timeout = pyqtSignal()

    def __init__(self, parent=None, timeout=10000):
        super().__init__(parent)
        self.timeout_interval = timeout
        self.timer = QTimer()
        self.timer.setSingleShot(False)
        self.timer.setInterval(100)  # update the progress bar tick

        connect(self.timer.timeout, self._update)
        self.setMaximum(self.timeout_interval)

    def _update(self):
        self.setValue(self.value() + self.timer.interval())
        if self.value() >= self.maximum():
            self.timer.stop()
            self.timeout.emit()

    def start(self):
        self.setValue(0)
        self.timer.start()

    def stop(self):
        self.setValue(0)
        self.timer.stop()
