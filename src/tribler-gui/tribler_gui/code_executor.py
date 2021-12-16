import binascii
import logging
import sys
import traceback
from base64 import b64decode, b64encode
from code import InteractiveConsole

from PyQt5.QtNetwork import QTcpServer

from tribler_gui.utilities import connect


class CodeExecutor:
    """
    This class is responsible for executing code (when starting Tribler in debug mode).
    The protocol to execute code is as follows.
    First, a client that wants to execute some code opens a connection with the TCP server and sends the
    string: <code in base64 format> <task_id>\n
    This code will be executed and the result will be sent to the client in the following format:
    result <result> <task_id>\n.
    If Tribler crashes, the server sends the following result: crash <stack trace in base64 format>

    Note that the socket uses the newline as separator.
    """

    def __init__(self, port, shell_variables=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tcp_server = QTcpServer()
        self.sockets = []
        self.stack_trace = None
        if not self.tcp_server.listen(port=port):
            self.logger.error("Unable to start code execution socket! Error: %s", self.tcp_server.errorString())
        else:
            connect(self.tcp_server.newConnection, self._on_new_connection)

        self.shell = Console(locals=shell_variables or {})

    def _on_new_connection(self):
        self.logger.info("CodeExecutor has new connection")

        while self.tcp_server.hasPendingConnections():
            socket = self.tcp_server.nextPendingConnection()
            connect(socket.readyRead, self._on_socket_read_ready)
            connect(socket.disconnected, self._on_socket_disconnect(socket))
            self.sockets.append(socket)

            # If Tribler has crashed, notify the other side immediately
            if self.stack_trace:
                self.on_crash(self.stack_trace)

    def run_code(self, code, task_id):
        self.logger.info(f"Run code for task {task_id}")
        self.logger.debug(f"Code for execution:\n{code}")

        try:
            self.shell.runcode(code)
        except SystemExit:
            pass

        if self.shell.last_traceback:
            self.on_crash(self.shell.last_traceback)
            return

        self.logger.info("Code execution with task %s finished:", task_id)

        return_value = b64encode(self.shell.locals.get('return_value', '').encode('utf-8'))
        for socket in self.sockets:
            socket.write(b"result %s %s\n" % (return_value, task_id))

    def on_crash(self, exception_text):
        self.logger.error(f"Crash in CodeExecutor:\n{exception_text}")

        self.stack_trace = exception_text
        for socket in self.sockets:
            socket.write(b"crash %s\n" % b64encode(exception_text.encode('utf-8')))

    def _on_socket_read_ready(self):
        data = bytes(self.sockets[0].readAll())
        parts = data.split(b" ")
        if len(parts) != 2:
            return

        try:
            code = b64decode(parts[0]).decode('utf8')
            task_id = parts[1].replace(b'\n', b'')
            self.run_code(code, task_id)
        except binascii.Error:
            self.logger.error("Invalid base64 code string received!")

    def _on_socket_disconnect(self, socket):
        def on_socket_disconnect_handler():
            self.sockets.remove(socket)
        return on_socket_disconnect_handler

class Console(InteractiveConsole):
    last_traceback = None

    def showtraceback(self) -> None:
        last_type, last_value, last_tb = sys.exc_info()
        try:
            self.last_traceback = ''.join(traceback.format_exception(last_type, last_value, last_tb))
            super().showtraceback()  # report the error to Sentry
        finally:
            del last_tb
