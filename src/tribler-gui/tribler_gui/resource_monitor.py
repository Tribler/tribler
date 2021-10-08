from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget

from tribler_core.components.resource_monitor.implementation.base import ResourceMonitor

GUI_RESOURCE_CHECK_INTERVAL = 5000  # milliseconds
GUI_RESOURCE_HISTORY_SIZE = 1000


class GuiResourceMonitor(ResourceMonitor, QWidget):
    """
    Implementation class of ResourceMonitor by the GUI process. The GUI process uses
    QTimer to implement start() and stop() methods.
    """
    def __init__(self):
        QWidget.__init__(self)
        ResourceMonitor.__init__(self, history_size=GUI_RESOURCE_HISTORY_SIZE)
        self.resource_monitor_timer = None

    def start(self):
        """
        Start the resource monitor by scheduling a QTimer.
        """
        self.resource_monitor_timer = QTimer()
        self.resource_monitor_timer.setSingleShot(False)
        self.resource_monitor_timer.timeout.connect(self.check_resources)
        self.resource_monitor_timer.start(GUI_RESOURCE_CHECK_INTERVAL)

    def stop(self):
        if self.resource_monitor_timer:
            try:
                self.resource_monitor_timer.stop()
                self.resource_monitor_timer.deleteLater()
            except RuntimeError:
                self._logger.error("Failed to stop GUI resource monitor timer in Debug pane")
