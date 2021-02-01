import statistics
import threading
import time

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QWidget

from tribler_common.sentry_reporter.sentry_mixin import AddBreadcrumbOnShowMixin

from tribler_gui.utilities import connect


class MonitorWidget(AddBreadcrumbOnShowMixin, QWidget):
    """
    An "ECG" plot of the IPv8 core update frequency.

    The updates (which we technically refer to as "boops") are measured by the IPv8 core itself.
    Each boop will be scaled in height based on the additional drift over the core update frequency.
    Each boop will be scaled in width to make sure they don't overlap in the display of the past 10 seconds.
    10 px under each boop the timestamp will be drawn.

    The mean and median of the core drift are shown in the upper left of the plot.

    Drawing enters on the right side of the screen.
    Drawing finishes at -10% of the left side of the screen to make sure the boops are not cut off.
    """

    def __init__(self):
        super().__init__()

        self.is_paused = False

        self.update_lock = threading.Lock()
        self.draw_times = []
        self.median_drift = "?"
        self.mean_drift = "?"
        self.walk_interval_target = "?"

        self.timer = QTimer()
        connect(self.timer.timeout, self.repaint)
        self.timer.start(33)

        self.backup_size = None

    def pause(self):
        self.is_paused = True
        self.timer.stop()

    def resume(self):
        self.is_paused = False
        self.set_history([])
        self.repaint()
        self.timer.start(33)

    def set_history(self, history):
        # We store/draw 11.0 seconds of history for 10.0 seconds of plot.
        # This is so the boops don't visually pop out of existence on the left side.
        # Instead, they smoothly run off screen.
        with self.update_lock:
            self.draw_times = [
                (entry["timestamp"], entry["drift"]) for entry in history if entry["timestamp"] > time.time() - 11.0
            ]
            if self.draw_times:
                drifts = [entry[1] for entry in self.draw_times]
                self.median_drift = round(statistics.median(drifts), 5)
                self.mean_drift = round(statistics.mean(drifts), 5)
                if len(drifts) > 1:
                    self.walk_interval_target = round(
                        self.draw_times[-1][0] - self.draw_times[-2][0] - self.draw_times[-1][1], 4
                    )
                else:
                    self.walk_interval_target = "?"
            else:
                self.median_drift = "?"
                self.mean_drift = "?"
                self.walk_interval_target = "?"

    def paintEvent(self, e):
        painter = QPainter()
        painter.begin(self)
        self.custom_paint(painter)
        painter.end()

    def custom_paint(self, painter):
        size = self.size()
        current_time = time.time()

        # Reduce flicker while performing the layout algorithm.
        # If we were already loaded before and are now being resized, use the last known size.
        if size.width() <= 1 or size.height() <= 1:
            if self.backup_size is None:
                return
            size = self.backup_size
        else:
            self.backup_size = size

        # Draw the statistics
        painter.setPen(Qt.white)
        painter.drawText(0, 20, f" Target:\t{self.walk_interval_target}")
        painter.drawText(0, 40, f" Mean:\t+{self.mean_drift}")
        painter.drawText(0, 60, f" Median:\t+{self.median_drift}")

        # Draw the baseline frequency bands (a perfect score of 0.0 drift).
        midy = (size.height() - 1) // 2
        painter.setPen(Qt.darkGray)
        painter.drawLine(0, midy + 40, size.width() - 1, midy + 40)
        painter.drawLine(0, midy - 50, size.width() - 1, midy - 50)

        # Draw the centerline.
        painter.setPen(Qt.green)
        painter.drawLine(0, midy, size.width() - 1, midy)

        # Calculate the required scaling.
        time_window = 10.0
        x_time_start = current_time - time_window
        boop_px = 60
        boop_secs = 0.25
        boop_xscale = size.width() / boop_px / time_window * boop_secs

        # Go through all core measurements and draw boops.
        with self.update_lock:
            for draw_time, drift in self.draw_times:
                x = int((draw_time - x_time_start) / time_window * size.width())
                self.draw_boop(painter, size, x, boop_xscale, 1 + drift * 10, str(round(draw_time, 3)))

    def draw_boop(self, painter, size, x, xscale=1.0, yscale=1.0, label=""):
        midy = (size.height() - 1) // 2

        # Erase the centerline on the area we will be drawing.
        painter.setPen(Qt.black)
        painter.drawLine(x, midy, x + int(60 * xscale), midy)
        painter.setPen(Qt.green)

        # The boop shape.
        painter.drawLine(x, midy, x + int(5 * xscale), midy - int(10 * yscale))
        painter.drawLine(x + int(5 * xscale), midy - int(10 * yscale), x + int(10 * xscale), midy)
        painter.drawLine(x + int(10 * xscale), midy, x + int(15 * xscale), midy)
        painter.drawLine(x + int(15 * xscale), midy, x + int(20 * xscale), midy + int(10 * yscale))
        painter.drawLine(x + int(20 * xscale), midy + int(10 * yscale), x + int(30 * xscale), midy - int(50 * yscale))
        painter.drawLine(x + int(30 * xscale), midy - int(50 * yscale), x + int(50 * xscale), midy + int(40 * yscale))
        painter.drawLine(x + int(50 * xscale), midy + int(40 * yscale), x + int(60 * xscale), midy)

        # If required, rotate the label 90 degrees and draw it 10 px under the boop.
        # This 10 px offset is scale independent.
        if label:
            painter.save()
            painter.translate(x + int(30 * xscale), midy + 10 + int(40 * yscale))
            painter.rotate(90)
            painter.setPen(Qt.white)
            painter.drawText(0, 0, label)
            painter.restore()
