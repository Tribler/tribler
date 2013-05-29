# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
This module implements a base class for a non-blocking HTTP Server.
"""

import BaseHTTPServer
import socket

#
# ASYNCH REQUEST HANDLER
#


class AsynchHTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    """Base Request Handler for asynchronous (non-blocking)
    HTTPServer implementation."""

    def log_request(self, code="", size=0):
        """Override to avoid default logging."""
        pass

    def log_error(self, format_, *args):
        """Override to avoid default logging."""
        pass

    def handle(self):
        """
        Override to make sure handle only attempts to read
        a single message. The default implementation tries to read
        multiple messages if possible, given that the HTTP/1.1 protocol
        is used. The default implementation of handle is thus potentially
        blocking - something that does not go well with the non-blocking
        implementation of this Web Server.
        """
        self.handle_one_request()

    def setup(self):
        """Initialise Request Handler"""
        BaseHTTPServer.BaseHTTPRequestHandler.setup(self)
        self.protocol_version = 'HTTP/1.1'


#
# ASYNCH HTTP SERVER
#
_LOG_TAG = "HTTPServer"


class AsynchHTTPServer(BaseHTTPServer.HTTPServer):

    """Base implementation of asynchronous (non-blocking)
    HTTP Server."""

    def __init__(self, task_runner, port, request_handler_class,
                 logger=None):

        if not issubclass(request_handler_class, AsynchHTTPRequestHandler):
            msg = "Given RequestHandlerClass not" + \
                "subclass of AsynchHTTPRequestHandler."""
            raise AssertionError(msg)

        # Task Runner
        self._task_runner = task_runner

        # Base Class
        try:
            # Default Port
            BaseHTTPServer.HTTPServer.__init__(self, ('', port),
                                               request_handler_class)
        except socket.error:
            # Any Port
            BaseHTTPServer.HTTPServer.__init__(self, ('', 0),
                                          request_handler_class)

        # Host Port
        self._host = socket.gethostbyname(socket.gethostname())
        self._port = self.server_address[1]

        # Logging
        self._logger = logger
        self._log_tag = _LOG_TAG

        # Clients
        self._client_list = []  # [(sock, addr, task)]

        # Register Tasks with TaskRunner
        self._conn_task = self._task_runner.add_read_task(self.fileno(),
                                                 self.handle_connect)

    #
    # PRIVATE UTILITY
    #

    def startup(self):
        """Startup HTTPServer."""
        self.log("START Port %d" % self._port)

    def handle_connect(self):
        """
        Accept new tcp connection.
        The file descriptor associated with the HTTPServer socket
        is assumed to be readable.
        """
        sock, addr = self.socket.accept()
        handler = lambda: self.handle_request_noblock(sock, addr)
        task = self._task_runner.add_read_task(sock.fileno(), handler)
        self._client_list.append((sock, task))

    def handle_request_noblock(self, client_sock, client_address):
        """
        Non-blocking request handler.
        Assumes the given client_sock is readable.
        Inspired by implementation of _handle_request_noblock()
        from SocketServer.BaseServer. Skip GetRequest which involves
        accept is already done in handle_connect()
        """
        if self.verify_request(client_sock, client_address):
            try:
                self.process_request(client_sock, client_address)
            except:
                self.handle_error(client_sock, client_address)
                self.close_request(client_sock)
        # Task Cleanup
        for tup in self._client_list:
            sock, task = tup
            if sock == client_sock:
                task.cancel()
                self._client_list.remove(tup)

    def log(self, msg):
        """Logging."""
        if self._logger:
            self._logger.log(self._log_tag, msg)

    #
    # PUBLIC API
    #

    def get_port(self):
        """Return accept port of HTTPServer."""
        return self._port

    def get_host(self):
        """Return host ip of HTTPServer."""
        return self._host

    def close(self):
        """Close HTTP Server."""
        self.log("CLOSE")
        self._conn_task.cancel()
        for sock, task in self._client_list:
            task.cancel()
            sock.close()
        self.server_close()


#
# MAIN
#
if __name__ == "__main__":

    class _Mock_Logger:

        """Mock Logger object."""
        def log(self, tag, msg):
            """Log to standard out."""
            print tag, msg

    import Tribler.UPnP.common.taskrunner as taskrunner
    TR = taskrunner.TaskRunner()
    SERVER = AsynchHTTPServer(TR,
                              44444,
                              AsynchHTTPRequestHandler,
                              logger=_Mock_Logger())
    try:
        TR.run_forever()
    except KeyboardInterrupt:
        print
    SERVER.close()
    TR.stop()
