import logging
import socket
from typing import Callable

import psutil
from PyQt5.QtCore import QObject, QTimer

from tribler.gui.utilities import connect


class PortChecker(QObject):
    """
    PortChecker finds the closest port opened by a process identified by given pid and the base port.
    A callback can also be set which is triggered when the port is detected.

    Usage:
    port_checker = PortChecker(pid, base_port, callback)
    port_checker.start_checking()

    # The detected port can be retrieved as:
    port_checker.detected_port
    """

    def __init__(self,
                 pid: int,
                 base_port: int,
                 callback: Callable[[int], None] = None,
                 num_ports_to_check: int = 10,
                 check_interval_in_ms: int = 1000,
                 timeout_in_ms: int = 120000):
        QObject.__init__(self, None)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._process = self.get_process_from_pid(pid)
        self._callback = callback

        self.base_port = base_port
        self.detected_port = None

        self.num_ports_to_check = num_ports_to_check
        self.check_interval_in_ms = check_interval_in_ms
        self.timeout_in_ms = timeout_in_ms

        self._checker_timer = None
        self._timeout_timer = None

    def start_checking(self):
        self._logger.info("Starting port checker")
        self._checker_timer = QTimer()
        self._checker_timer.setSingleShot(True)
        connect(self._checker_timer.timeout, self.check_port)

        self._timeout_timer = QTimer()
        self._timeout_timer.setSingleShot(True)
        connect(self._timeout_timer.timeout, self.stop_checking)

        self._checker_timer.start(self.check_interval_in_ms)
        self._timeout_timer.start(self.timeout_in_ms)

    def stop_checking(self):
        self._logger.info("Stopping port checker")
        if self._checker_timer:
            self._checker_timer.stop()
        if self._timeout_timer:
            self._timeout_timer.stop()

    def check_port(self):
        self._logger.info(f"Checking ports; Base Port: {self.base_port}")
        self.detect_port_from_process()
        if self.detected_port and self._callback:
            self._logger.info(f"Detected Port: {self.detected_port}; Base Port: {self.base_port}; Calling callback.")
            self._callback(self.detected_port)
        elif self._checker_timer:
            self._checker_timer.start(self.check_interval_in_ms)

    @classmethod
    def get_process_from_pid(cls, pid):
        try:
            return psutil.Process(pid)
        except psutil.NoSuchProcess:
            return None

    def detect_port_from_process(self):
        if not self._process:
            return

        connections = self._process.connections(kind='inet4')
        candidate_ports = [connection.laddr.port for connection in connections
                           if self._is_connection_in_range(connection)]

        if candidate_ports:
            self.detected_port = min(candidate_ports)

    def _is_connection_in_range(self, connection):
        return connection.laddr.ip == '127.0.0.1' \
               and connection.status == 'LISTEN' \
               and connection.type == socket.SocketKind.SOCK_STREAM \
               and self.base_port <= connection.laddr.port < self.base_port + self.num_ports_to_check
