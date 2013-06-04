# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
This module implements the client side of an non-blocking,
http request-response exchange, supported by a TaskRunner.
A blocking interace is also provided on top of the non-blocking.

The implementation also sets up the connection i a non-blocking
manner. This essentially makes it a
connect-request-response protocol.
"""

import socket
import errno
import exceptions
import os
import threadhotel

#
# BLOCKING HTTP CLIENT
#


class SynchHTTPClient:

    """
    This class wraps the AsynchHTTPClient to provide
    a traditional blocking API.
    """
    FAIL, OK = "FAIL", "OK"

    def __init__(self, asynchhttpclient):
        self._threadhotel = threadhotel.ThreadHotel()
        self._asynchclient = asynchhttpclient

    def request(self, host, port, request_data):
        """
        Returns tuple (status, reply).
        - Status indicates whether the request failed or succeded.
        - If Status is FAIL, the reply explains what went wrong.
        - Reply is tuple of: (header, body)
        - If Status is OK, the reply includes the http response.
        - Reply is tuple of: (error, comment)
        """
        rid = self._asynchclient.get_request_id()
        self._threadhotel.reserve(rid)
        self._asynchclient.request(rid, host, port, request_data,
                                   self._abort_handler, self._response_handler, timeout=10)
        return self._threadhotel.wait_reply(rid)

    def _abort_handler(self, rid, error, comment):
        """Abort handler."""
        reply = (error, comment)
        self._threadhotel.wakeup(rid, SynchHTTPClient.FAIL, reply)

    def _response_handler(self, rid, header, body):
        """Response handler."""
        reply = (header, body)
        self._threadhotel.wakeup(rid, SynchHTTPClient.OK, reply)


#
#  NON-BLOCKING  HTTP CLIENT
#
_LOG_TAG = "HTTPClient"


class AsynchHTTPClient:

    """
    This class runs non-blocking asynchronous http requests
    to multiple HTTP servers at once. Specify a_handler or r_handler
    for asynchrounous upcalls. If not, the httpClient supports
    fire-and-forget semantics (from an external point of view).
    Internally, the httpClient will not forget a request until it has
    either timeout out, aborted due to failure or succeeded.
    """

    def __init__(self, task_runner, logger=None):
        self._task_runner = task_runner
        self._request_id = 0
        self._requests = {}  # requestID: (request, aHandler, rHandler)
        # Logging
        self._log_tag = _LOG_TAG
        self._logger = logger

    #
    # PUBLIC API
    #

    def get_request_id(self):
        """Generate new request id."""
        self._request_id += 1
        return self._request_id

    def request(self, rid, host, port, request_data,
                a_handler=None, r_handler=None, timeout=10):
        """
        Issue a new http request.

        host, port -- web server.
        request_data -- string data including both header and body.
        a_handler(error, message) -- handler to be invoked if request aborts.
        r_handler(header, body) -- handler to be invoked with response.
        """
        request = HTTPRequest(self._task_runner, rid, recv_timeout=timeout)
        request.set_abort_handler(self._handle_abort)
        request.set_response_handler(self._handle_response)
        self._requests[rid] = (request, a_handler, r_handler)
        request.dispatch(host, port, request_data)
        self._log("Request Dispatched [%d]" % rid)
        return rid

    def close(self):
        """Stop all requests and close their sockets."""
        for tup in self._requests.values():
            request = tup[0]
            request.close()

    #
    # PRIVATE HANDLERS
    #

    def _handle_response(self, rid, header, body):
        """Dispatches responses by invoking given r_handler."""
        self._log("Response Received [%d]" % rid)
        request = self._requests[rid][0]
        r_handler = self._requests[rid][2]
        del self._requests[rid]
        request.close()
        if r_handler:
            r_handler(rid, header, body)

    def _handle_abort(self, rid, error, why):
        """Dispatches aborts by invoking given a_handler."""
        self._log("HTTP Request Aborted [%d]" % rid)
        request = self._requests[rid][0]
        a_handler = self._requests[rid][1]
        del self._requests[rid]
        request.close()
        if a_handler:
            a_handler(rid, error, why)

    #
    # PRIVATE UTILITY
    #

    def _log(self, msg):
        """Logger."""
        if self._logger:
            self._logger.log(self._log_tag, msg)


#
# HTTP REQUEST
#

class HTTPRequestError(exceptions.Exception):

    """Error associated with the request response protocol."""
    pass


class HTTPRequest:

    """
    This implements a single non-blocking connect-request-response
    protocol from an HTTPClient to a HTTPServer.
    For now, this class does not support sequential requests-responses on the
    same connection. Neither does it support instance reuse.
    """
    STATE_INIT = 0
    STATE_CONNECT_STARTED = 1
    STATE_CONNECT_OK = 2
    STATE_SEND_STARTED = 3
    STATE_SEND_OK = 4
    STATE_RECV_STARTED = 5
    STATE_RECV_OK = 6
    STATE_DONE = 7

    def __init__(self, task_runner, request_id,
                 recv_timeout=10, conn_timeout=1,
                 conn_attempts=3, logger=None):
        self._task_runner = task_runner
        self._request_id = request_id
        # Create Socket
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setblocking(False)
        # Protocol State
        self._state = HTTPRequest.STATE_INIT
        # Request Data
        self._request_data = None
        self._bytes_sent = 0
        # Response Data
        self._response_data = ""
        self._recv_count = 0
        # Tasks
        self._conn_task = None
        self._conn_to_task = None
        self._send_task = None
        self._recv_task = None
        self._recv_to_task = None
        # Connect Attempts
        self._connect_attempts = 0
        self._max_connect_attempts = conn_attempts
        # Send
        self._bytes = 0
        self._send_count = 0
        # Recv
        self._header = ""
        self._body = ""
        self._length = 0
        self._delimiter = '\r\n\r\n'
        # Timeouts
        self._recv_to = recv_timeout
        self._conn_to = conn_timeout
        # Handler Upcalls
        self._recv_handler = lambda requestID, hdr, body: None
        self._abort_handler = lambda requestID, error, comment: None
        # Logging
        self._logger = logger
        self._log_tag = "Request [%d]" % self._request_id

    #
    # PUBLIC API
    #

    def dispatch(self, host, port, request_data):
        """Dispatch a new request."""
        if self._state != HTTPRequest.STATE_INIT:
            raise HTTPRequestError("Illegal Operation given protocol State")
        self._request_data = request_data
        self._connect_start(host, port)

    def set_response_handler(self, handler):
        """Register a response handler."""
        self._recv_handler = handler

    def set_abort_handler(self, handler):
        """Register an abort handler."""
        self._abort_handler = handler

    def close(self):
        """Cleanup the request-response protocol and close the socket."""
        if self._conn_task:
            self._conn_task.cancel()
        if self._conn_to_task:
            self._conn_to_task.cancel()
        if self._send_task:
            self._send_task.cancel()
        if self._recv_task:
            self._recv_task.cancel()
        if self._recv_to_task:
            self._recv_to_task.cancel()
        self._state = HTTPRequest.STATE_DONE
        if self._sock:
            try:
                self._sock.close()
            except socket.error:
                pass
            self._sock = None

    #
    # PRIVATE UTILITY
    #

    def _log(self, msg):
        """Logging."""
        if self._logger:
            self._logger.log(self._log_tag, msg)

    def _get_content_length(self):
        """Extract body length from HTTP header."""
        lines = self._header.split('\r\n')
        if not lines:
            return
        for line in lines[1:]:
            if len(line.strip()) > 0:
                elem_name, elem_value = line.split(":", 1)
                if elem_name.lower() == 'content-length':
                    return int(elem_value.strip())
        else:
            return 0

    def _http_header_ok(self):
        """Check that received data is a valid HTTP header."""
        if len(self._header) > 4 and self._header[:4] == "HTTP":
            return True
        else:
            return False

    def _do(self, method, args=()):
        """Shorthand for add_task."""
        return self._task_runner.add_task(method, args)

    def _do_write(self, file_descriptor, method):
        """Shorthand for add_write."""
        return self._task_runner.add_write_task(file_descriptor, method)

    def _do_read(self, file_descriptor, method):
        """Shorthand for add_read."""
        return self._task_runner.add_read_task(file_descriptor, method)

    def _do_to(self, timeout, method):
        """Shorthand for add_delay."""
        return self._task_runner.add_delay_task(timeout, method)

    #
    # PRIVATE PROTOCOL METHODS
    #

    def _connect_start(self, host, port):
        """Start non-blocking connect."""
        self._log("Connect Start")
        error = self._sock.connect_ex((host, port))
        if error != errno.EINPROGRESS:
            self._abort(error, "Non-Blocking Connect Failed")
            return
        self._state = HTTPRequest.STATE_CONNECT_STARTED
        self._conn_task = self._do_write(self._sock.fileno(),
                                         self._handle_connect_ok)
        self._conn_to_task = self._do_to(self._conn_to,
                                         self._handle_connect_to)

    def _handle_connect_ok(self):
        """
        Handler successful connect.

        In fact, certain unsuccessful connects may not be detected
        before write is attempted on the socket.
        """
        self._log("Connect OK")
        if self._state != HTTPRequest.STATE_CONNECT_STARTED:
            raise HTTPRequestError("Illegal Operation given protocol State")
        self._state = HTTPRequest.STATE_CONNECT_OK
        self._conn_task.cancel()
        self._conn_to_task.cancel()
        # Start sending the Request
        self._do(self._send)

    def _handle_connect_to(self):
        """Handle connect timeout."""
        self._log("Connect Timeout")
        if self._state != HTTPRequest.STATE_CONNECT_STARTED:
            raise HTTPRequestError("Illegal Operation given protocol State")
        self._connect_attempts += 1
        if self._connect_attempts >= self._max_connect_attempts:
            # Abort
            self._conn_task.cancel()
            self._abort(errno.ETIME, "Connect Timeout")
        else:
            # Try again
            self._conn_to_task = self._do_to(self._conn_to,
                                             self._handle_connect_to)

    def _send(self):
        """
        Start sending a request.
        Or continue sending a partially sent request.
        """
        self._send_count += 1
        first_attempt = True if self._send_count == 1 else False
        if first_attempt and self._state != HTTPRequest.STATE_CONNECT_OK:
            raise HTTPRequestError("Illegal Operation given protocol State")
        elif not first_attempt and \
                self._state != HTTPRequest.STATE_SEND_STARTED:
            raise HTTPRequestError("Illegal Operation given protocol State")
        if first_attempt:
            self._state = HTTPRequest.STATE_SEND_STARTED
            self._log("Send Started")
        else:
            self._log("Send Continue")

        # (Continue) Send
        try:
            bytes_sent = self._sock.send(self._request_data[self._bytes:])
        except socket.error as why:
            if why[0] == errno.EAGAIN:
                # Send on full buffer
                # Continue sending again once the socket becomes writeable
                self._send_continue()
                return
            else:
                # Typically EPIPE: Broken Pipe or ECONNREFUSED
                if self._send_task:
                    self._send_task.cancel()
                self._abort(why[0], "Exception on Send")
                return

        # Send Operation returned naturally
        if bytes > 0:
            # Something was sent
            self._bytes += bytes_sent
            if self._bytes >= len(self._request_data):
                # The complete message was sent
                self._state = HTTPRequest.STATE_SEND_OK
                self._task_runner.add_task(self._handle_send_ok)
                return
            else:
                # Message only partially sent
                self._send_continue()
                return
        else:
            # 0 bytes sent => error
            if self._send_task:
                self._send_task.cancel()
            msg = "Sent 0 bytes, yet fd was writeable and no exception occurred"
            self._abort(errno.EPIPE, msg)

    def _send_continue(self):
        """Register new write task after request was only partially sent."""
        # Register a new Write Task
        if not self._send_task:
            self._send_task = self._do_write(self._sock.fileno(),
                                             self._send)

    def _handle_send_ok(self):
        """Handle completely sent request."""
        self._log("Send OK")
        if self._state != HTTPRequest.STATE_SEND_OK:
            raise HTTPRequestError("Illegal Operation given protocol State")
        # Cancel Send Task
        if self._send_task:
            self._send_task.cancel()
        # Start waiting for the response
        self._recv_task = self._do_read(self._sock.fileno(), self._recv)
        # Define new Receive Timeout
        self._recv_to_task = self._do_to(self._recv_to,
                                         self._handle_recv_to)

    def _recv(self):
        """
        Start receiveing the response.
        Or continue to receive a partially received response.
        """
        self._recv_count += 1
        first_attempt = True if self._recv_count == 1 else False
        if first_attempt and self._state != HTTPRequest.STATE_SEND_OK:
            raise HTTPRequestError("Illegal Operation given protocol State")
        elif not first_attempt and \
                self._state != HTTPRequest.STATE_RECV_STARTED:
            raise HTTPRequestError("Illegal Operation given protocol State")
        if first_attempt:
            self._state = HTTPRequest.STATE_RECV_STARTED
            self._log("Recv Started")
        else:
            self._log("Recv Continue")

        # Recv a chunk
        try:
            data = self._sock.recv(1024)
        except socket.error as why:
            if why[0] == errno.EAGAIN:
                # EAGAIN: Enter/stay in writeset
                self._recv_continue()
                return
            else:
                # EPIPE: Broken Pipe.
                if self._recv_task:
                    self._recv_task.cancel()
                self._abort(why[0], "Exception on Recv")
                return

        # Recv completed naturally
        if data:
            self._response_data += data
            # Parse HTTP response
            if not self._header:
                tokens = self._response_data.split(self._delimiter, 1)
                if len(tokens) == 1:
                    # Header Not Complete
                    self._recv_continue()
                    return
                else:
                    # Header Complete
                    self._header = tokens[0]
                    if not self._http_header_ok():
                        self._abort(errno.EBADMSG, "Not HTTP Header")
                        return
                    else:
                        # Header complete and OK
                        self._length = len(self._header) + \
                            len(self._delimiter) + self._get_content_length()

            if self._header:
                # Header is received, entire body may not be received
                if len(self._response_data) < self._length:
                    # Entire body not received
                    self._recv_continue()
                else:
                    # Entire response received (may be too long)
                    if len(self._response_data) > self._length:
                        # Truncate
                        self._response_data = self._response_data[:self._length]
                    # Entire response received (correct length)
                    # Cancel Tasks
                    self._recv_task.cancel()
                    self._recv_to_task.cancel()
                    self._state = HTTPRequest.STATE_RECV_OK
                    self._do(self._handle_recv_ok)
        else:
            # Did not block, but received no data => error
            self._recv_task.cancel()
            msg = "Recv 0 bytes, yet fd was readable and no exception occurred"
            self._abort(errno.EPIPE, msg)

    def _recv_continue(self):
        """Register read task to continue to receive a
        partially received response."""
        # Make sure a ReadTask is registered.
        if not self._recv_task:
            self._recv_task = self._do_read(self._sock.fileno(),
                                            self._recv)

    def _handle_recv_to(self):
        """Handle receive timeout."""
        self._log("Receive Timeout")
        if self._state != HTTPRequest.STATE_SEND_OK:
            raise HTTPRequestError("Illegal Operation given protocol State")
        # Cancel RecvTask
        if self._recv_task:
            self._recv_task.cancel()
        self._abort(errno.ETIME, "Receive Timeout")

    def _handle_recv_ok(self):
        """Handle completely received response."""
        self._log("Receive OK")
        if self._state != HTTPRequest.STATE_RECV_OK:
            raise HTTPRequestError("Illegal Operation given protocol State")
        # Upcall
        body = self._response_data[len(self._header) + len(self._delimiter):]
        self._state = HTTPRequest.STATE_DONE
        args = (self._request_id, self._header, body)
        self._do(self._recv_handler, args)

    def _abort(self, error, comment):
        """Abort this request-response protocol."""
        fmt = "Abort [%d] %s '%s' (%s)"
        self._log(fmt % (error, errno.errorcode[error],
                 os.strerror(error), comment))
        self._state = HTTPRequest.STATE_DONE
        args = (self._request_id, error, comment)
        self._do(self._abort_handler, args)


#
# MAIN
#
if __name__ == '__main__':

    class _MockLogger:

        """Mock-up Logger."""
        def log(self, tag, msg):
            """Log to stdout."""
            print tag, msg

    LOGGER = _MockLogger()

    import Tribler.UPnP.common.taskrunner as taskrunner
    import sys

    TR = taskrunner.TaskRunner()

    HOME = "192.168.1.235"
    WORK = "193.156.106.130"

    HOST = WORK

    if len(sys.argv) > 1:
        PORT = int(sys.argv[1])
    else:
        PORT = 44444

    if len(sys.argv) > 2 and sys.argv[2] == 'home':
        HOST = HOME

    HTTP_REQUEST = "NOTIFY /path HTTP/1.1\r\nContent-length:0\r\n\r\n"

    def response_handler(rid, header, body):
        """Response handler."""
        print rid
        print header
        print "----------"
        print body

    def abort_handler(rid, error, comment):
        """Abort handler."""
        fmt = "Abort [%d] %s '%s' (%s) [%d]"
        print fmt % (error, errno.errorcode[error],
                     os.strerror(error), comment, rid)

    class _TestSynchHTTPClient:

        """Runnable test class for Synchronous HTTPClient."""

        def __init__(self, asynch_httpclient):
            self._synch_httpclient = SynchHTTPClient(asynch_httpclient)

        def run(self):
            """Run the blocking connect-request-response protocol."""
            status, reply = self._synch_httpclient.request(HOST,
                                                           PORT, HTTP_REQUEST)
            if status == SynchHTTPClient.OK:
                header, body = reply
                print header
                print body
            elif status == SynchHTTPClient.FAIL:
                error, msg = reply
                print error, msg

    # Test Asynch HTTP Client
    ASYNCH = AsynchHTTPClient(TR, logger=LOGGER)
    RID = ASYNCH.get_request_id()
    ASYNCH.request(RID, HOST, PORT,
                   HTTP_REQUEST, abort_handler, response_handler)

    # Test Synch HTTP Client
    import threading
    SYNCH = _TestSynchHTTPClient(ASYNCH)
    THREAD = threading.Thread(target=SYNCH.run)
    THREAD.start()

    try:
        TR.run_forever()
    except KeyboardInterrupt:
        pass
