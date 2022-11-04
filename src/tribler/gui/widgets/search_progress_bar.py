import time

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QProgressBar

from tribler.gui.utilities import connect

MAX_VALUE = 10000
UPDATE_DELAY = 0.5
REMOTE_DELAY = 0.25


class SearchProgressBar(QProgressBar):
    ready_to_update_results = pyqtSignal()

    def __init__(self, parent=None, timeout=20):
        super().__init__(parent)
        self.timeout_interval = timeout
        self.timer = QTimer()
        self.timer.setSingleShot(False)
        self.timer.setInterval(100)  # update the progress bar tick

        self.start_time = None
        self.last_update_time = None
        self.last_remote_result_time = None
        self.has_new_remote_results = False
        self.peers_total = 0
        self.peers_responded = 0
        self.new_remote_items_count = 0
        self.total_remote_items_count = 0

        self._value = 0
        self.setValue(0)
        self.setMaximum(MAX_VALUE)

        connect(self.timer.timeout, self._update)

    def start(self):
        t = time.time()
        self.start_time = t
        self.peers_total = 0
        self.peers_responded = 0
        self.setToolTip('')
        self.setValue(0)
        self.timer.start()
        self.show()

    def _update(self):
        if self.start_time is None:
            return

        t = time.time()

        time_progress = (t - self.start_time) / self.timeout_interval
        response_progress = (self.peers_responded / self.peers_total) if self.peers_total else 0
        scale = 1 - ((1 - time_progress) * (1 - response_progress)) ** 2
        value = int(scale * MAX_VALUE)
        self.setValue(value)

        timeout = time_progress >= 1
        most_peers_responded = self.peers_total > 0 and self.peers_responded / self.peers_total >= 0.8
        active_transfers_finished = self.last_remote_result_time and t - self.last_remote_result_time > REMOTE_DELAY

        should_stop = timeout or (most_peers_responded and active_transfers_finished)

        if self.last_update_time is not None and self.has_new_remote_results \
                and (t - self.last_update_time > UPDATE_DELAY and active_transfers_finished or should_stop):
            self.last_update_time = t
            self.has_new_remote_results = False
            self.new_remote_items_count = 0
            self.ready_to_update_results.emit()

        if should_stop:
            self.stop()

    def stop(self):
        self.start_time = None
        self.timer.stop()
        self.hide()

    def mousePressEvent(self, _):
        self.stop()

    def on_local_results(self):
        self.last_update_time = time.time()
        self.has_new_remote_results = False
        self._update()

    def set_remote_total(self, total: int):
        self.peers_total = total
        self.setToolTip(f'0/{total} remote responded')
        self._update()

    def on_remote_results(self, new_items_count, peers_responded):
        self.last_remote_result_time = time.time()
        tool_tip = f'{peers_responded}/{self.peers_total} peers responded'
        if self.total_remote_items_count:
            tool_tip += f', {self.total_remote_items_count} new results'
        self.setToolTip(tool_tip)
        self.has_new_remote_results = True
        self.new_remote_items_count += new_items_count
        self.total_remote_items_count += new_items_count
        self.peers_responded = peers_responded
        self._update()
