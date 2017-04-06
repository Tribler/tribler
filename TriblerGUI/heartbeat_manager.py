from PyQt5.QtCore import QObject, pyqtSignal, QTimer

from TriblerGUI.tribler_request_manager import TriblerRequestManager


class HeartbeatManager(QObject):
    """
    This class handles heartbeat requests made to the Tribler core. This is used to check whether the core is still
    alive and working.
    """
    heartbeat_timeout = pyqtSignal(str)

    def __init__(self):
        QObject.__init__(self)

        self.heartbeat_timer = QTimer()
        self.heartbeat_timeout_timer = QTimer()
        self.request_mgr = TriblerRequestManager()

    def start(self):
        self.schedule_heartbeat()

    def stop(self):
        self.request_mgr.cancel_request()
        self.heartbeat_timer.stop()
        self.heartbeat_timeout_timer.stop()

    def schedule_heartbeat(self):
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.setSingleShot(True)
        self.heartbeat_timer.timeout.connect(self.send_heartbeat)
        self.heartbeat_timer.start(5000)

    def send_heartbeat(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request('alive', self.on_heartbeat_response, capture_errors=False)

        # Schedule timeout timer
        self.heartbeat_timeout_timer = QTimer()
        self.heartbeat_timeout_timer.setSingleShot(True)
        self.heartbeat_timeout_timer.timeout.connect(self.on_heartbeat_timeout)
        self.heartbeat_timeout_timer.start(10000)

    def on_heartbeat_timeout(self):
        self.heartbeat_timeout.emit("Heartbeat didn't complete within desired amount of time")

    def on_heartbeat_response(self, response, error):
        self.heartbeat_timeout_timer.stop()
        if response is None:
            self.heartbeat_timeout.emit("Heartbeat response error: %s" % error)
        elif 'error' in response:
            self.heartbeat_timeout.emit("Invalid heartbeat response: %s" %
                                        TriblerRequestManager.get_message_from_error(response))
        else:
            self.schedule_heartbeat()
