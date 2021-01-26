from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget

from tribler_core.modules.resource_monitor.base import ResourceMonitor


class GuiResourceMonitor(ResourceMonitor, QWidget):
    """
    Implementation class of ResourceMonitor by the GUI process. The GUI process uses
    QTimer to implement start() and stop() methods.
    """
    def __init__(self, history_size=30):
        QWidget.__init__(self)
        ResourceMonitor.__init__(self, history_size=history_size)
        self.resource_monitor_timer = None

    def start(self):
        """
        Start the resource monitor by scheduling a QTimer.
        """
        self.resource_monitor_timer = QTimer()
        self.resource_monitor_timer.setSingleShot(False)
        self.resource_monitor_timer.timeout.connect(self.check_resources)
        self.resource_monitor_timer.start(5000)

    def stop(self):
        if self.resource_monitor_timer:
            try:
                self.resource_monitor_timer.stop()
                self.resource_monitor_timer.deleteLater()
            except RuntimeError:
                self._logger.error(f"Failed to stop GUI resource monitor timer in Debug pane")
        super(GuiResourceMonitor, self).stop()
