from __future__ import absolute_import

from base64 import b64encode
import binascii
import code
import io
import logging
import sys

from PyQt5.QtNetwork import QTcpServer


class CodeExecutor(object):
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

    def __init__(self, port, shell_variables={}):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tcp_server = QTcpServer()
        self.sockets = []
        self.stack_trace = None
        if not self.tcp_server.listen(port=port):
            self.logger.error("Unable to start code execution socket! Error: %s", self.tcp_server.errorString())
        else:
            self.tcp_server.newConnection.connect(self._on_new_connection)

        self.shell = Console(locals=shell_variables)

    def _on_new_connection(self):
        while self.tcp_server.hasPendingConnections():
            socket = self.tcp_server.nextPendingConnection()
            socket.readyRead.connect(self._on_socket_read_ready)
            socket.disconnected.connect(lambda dc_socket=socket: self._on_socket_disconnect(dc_socket))
            self.sockets.append(socket)

            # If Tribler has crashed, notify the other side immediately
            if self.stack_trace:
                self.on_crash(self.stack_trace)

    def run_code(self, code, task_id):
        self.shell.runcode(code)
        stdout = self.shell.stdout.read()
        stderr = self.shell.stderr.read()

        self.logger.info("Code execution with task %s finished:", task_id)
        self.logger.info("Stdout of task %s: %s", task_id, stdout)
        if ('Traceback' in stderr or 'SyntaxError' in stderr) and 'SystemExit' not in stderr:
            self.logger.info("Executed code with failure: %s", b64encode(code))
            raise RuntimeError("Error during remote code execution! %s" % stderr)

        # Determine the return value
        if 'return_value' not in self.shell.console.locals:
            return_value = ''.encode('base64')
        else:
            return_value = str(self.shell.console.locals['return_value']).encode('base64')

        for socket in self.sockets:
            socket.write("result %s %s\n" % (return_value, task_id))

    def on_crash(self, exception_text):
        self.stack_trace = exception_text
        for socket in self.sockets:
            socket.write("crash %s\n" % exception_text.encode('base64'))

    def _on_socket_read_ready(self):
        data = str(self.sockets[0].readAll())
        parts = data.split(" ")
        if len(parts) != 2:
            return

        try:
            code = parts[0].decode('base64')
            task_id = parts[1].replace('\n', '')
            self.run_code(code, task_id)
        except binascii.Error:
            self.logger.error("Invalid base64 code string received!")

    def _on_socket_disconnect(self, socket):
        self.sockets.remove(socket)


class Stream(object):
    def __init__(self):
        self.stream = io.BytesIO()

    def read(self, *args, **kwargs):
        result = self.stream.read(*args, **kwargs)
        self.stream = io.BytesIO(self.stream.read())

        return result

    def write(self, *args, **kwargs):
        p = self.stream.tell()
        self.stream.seek(0, io.SEEK_END)
        result = self.stream.write(*args, **kwargs)
        self.stream.seek(p)

        return result


class Console(object):
    def __init__(self, locals=None):
        self.console = code.InteractiveConsole(locals=locals)

        self.stdout = Stream()
        self.stderr = Stream()

    def runcode(self, *args, **kwargs):
        stdout = sys.stdout
        sys.stdout = self.stdout

        stderr = sys.stderr
        sys.stderr = self.stderr

        result = None
        try:
            result = self.console.runcode(*args, **kwargs)
        except SyntaxError:
            self.console.showsyntaxerror()
        except:
            self.console.showtraceback()

        sys.stdout = stdout
        sys.stderr = stderr

        return result

    def execute(self, command):
        return self.runcode(code.compile_command(command))
