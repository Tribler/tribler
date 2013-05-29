# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
This module implements a base SSDP Deamon,
part of the UPnP architecture.
"""
import socket
import struct
import ssdpmessage

_MCAST_HOST = '239.255.255.250'
_MCAST_PORT = 1900
_MCAST_TTL = 4
_LOG_TAG = "SSDP"

#
# SSDP DAEMON
#


class SSDPDaemon:

    """
    This implements the base SSDP deamon, part of the UPnP architecture.

    This class is implemented in a non-blocking, event-based manner.
    Execution is outsourced to the given task_runner.
    """

    def __init__(self, task_runner, logger=None):

        # TaskRunner
        self.task_runner = task_runner

        # Logger
        self._logger = logger
        self._log_tag = _LOG_TAG

        # Socket (unicast send/recv + multicast send)
        self._sock = socket.socket(socket.AF_INET,
                                   socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET,
                              socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.SOL_SOCKET,
                              socket.SO_BROADCAST, 1)
        self._sock.bind(('', 0))

        # Socket Multicast Recv
        self._mcast_recv_sock = socket.socket(socket.AF_INET,
                                              socket.SOCK_DGRAM,
                                              socket.IPPROTO_UDP)

        self._mcast_recv_sock.setsockopt(socket.SOL_SOCKET,
                                         socket.SO_REUSEADDR, 1)
        try:
            self._mcast_recv_sock.setsockopt(socket.SOL_SOCKET,
                                             socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass  # Some systems don't support SO_REUSEPORT

        mreq = struct.pack("4sl", socket.inet_aton(_MCAST_HOST),
                           socket.INADDR_ANY)
        self._mcast_recv_sock.setsockopt(socket.IPPROTO_IP,
                                         socket.IP_ADD_MEMBERSHIP, mreq)
        self._mcast_recv_sock.setsockopt(socket.IPPROTO_IP,
                                         socket.IP_MULTICAST_TTL, _MCAST_TTL)
        self._mcast_recv_sock.setsockopt(socket.SOL_IP,
                                         socket.IP_MULTICAST_TTL, _MCAST_TTL)
        self._mcast_recv_sock.setsockopt(socket.SOL_IP,
                                         socket.IP_MULTICAST_LOOP, True)

        self._mcast_recv_sock.bind(('', _MCAST_PORT))

        # Host & Port
        self._host = socket.gethostbyname(socket.gethostname())
        self._port = self._sock.getsockname()[1]

        # Register Tasks for Execution
        self._rd_task_1 = self.task_runner.add_read_task(self._sock.fileno(),
                                                         self._handle_unicast)
        self._rd_task_2 = self.task_runner.add_read_task(
            self._mcast_recv_sock.fileno(),
            self._handle_multicast)

    #
    # PUBLIC PROTOCOL OPERATIONS
    #

    def startup(self):
        """Startup"""
        fmt = "START Port %d and Port %d (Recv Local Multicast)"
        self.log(fmt % (self._port, _MCAST_PORT))

    def log(self, msg):
        """Logger object."""
        if self._logger:
            self._logger.log(self._log_tag, msg)

    def multicast(self, msg):
        """Multicast a SSDP message."""
        if self._sock != None:
            self.log("MULTICAST %s" % msg.type)
            self._sock.sendto(msg.dumps(), (_MCAST_HOST, _MCAST_PORT))

    def unicast(self, msg, sock_addr):
        """Unicast a SSDP message."""
        if self._sock != None:
            self.log("UNICAST %s to %s" % (msg.type, str(sock_addr)))
            self._sock.sendto(msg.dumps(), sock_addr)

    def get_sock(self):
        """Return unicast receive socket."""
        return self._sock

    def get_mcast_sock(self):
        """Return multicast receive socket."""
        return self._mcast_recv_sock

    def get_port(self):
        """Return SSDP port."""
        return self._port

    def is_closed(self):
        """Returns true if SSDPDaemon has been closed."""
        return True if self._sock == None else False

    def close(self):
        """Close the SSDP deamon."""
        self._rd_task_1.cancel()
        self._rd_task_2.cancel()
        if self._mcast_recv_sock:
            self._mcast_recv_sock.close()
            self._mcast_recv_sock = None
        if self._sock:
            self._sock.close()
            self._sock = None
        self.log("CLOSE")

    #
    # MESSAGE HANDLERS
    #

    def _handle_multicast(self):
        """Handles the receipt of a multicast SSDP message."""
        res = self._mcast_recv_sock.recvfrom(1500)
        if res:
            data, sock_addr = res
            # Ignore Multicast Messages from Self
            if sock_addr != (self._host, self._port):
                self._handle_message(data, sock_addr)

    def _handle_unicast(self):
        """Handles the receipt of a unicast SSDP message."""
        res = self._sock.recvfrom(1500)
        if res:
            data, sock_addr = res
            self._handle_message(data, sock_addr)

    def _handle_message(self, data, sock_addr):
        """Handles the receipt of both multicast and unicast SSDP
        messages."""
        try:
            msg = ssdpmessage.message_loader(data)
        except Exception as error:
            print "Exception Handle Message %s\n%s\n" % (error, data)
            raise

        # Handle Message
        if isinstance(msg, ssdpmessage.SearchMessage):
            self.handle_search(msg, sock_addr)
        elif isinstance(msg, ssdpmessage.AnnounceMessage):
            self.handle_announce(msg, sock_addr)
        elif isinstance(msg, ssdpmessage.UnAnnounceMessage):
            self.handle_unannounce(msg, sock_addr)
        elif isinstance(msg, ssdpmessage.ReplyMessage):
            self.handle_reply(msg, sock_addr)

    def handle_search(self, msg, sock_addr):
        """Handles the receipt of a SSDP Search message.
        To be overridden by subclass."""
        pass

    def handle_reply(self, msg, sock_addr):
        """Handles the receipt of a SSDP Reply message.
        To be overridden by subclass."""
        pass

    def handle_announce(self, msg, sock_addr):
        """Handles the receipt of a SSDP Announce message.
        To be overridden by subclass."""
        pass

    def handle_unannounce(self, msg, sock_addr):
        """Handles the receipt of a SSDP UnAnnounce message.
        To be overridden by subclass."""
        pass


#
# MAIN
#

if __name__ == '__main__':

    import Tribler.UPnP.common.taskrunner as taskrunner
    TR = taskrunner.TaskRunner()

    class _MockLogger:

        """Mock Logger object."""
        def log(self, log_tag, msg):
            """Log to std out. """
            print log_tag, msg

    DAEMON = SSDPDaemon(TR, _MockLogger())
    TR.add_task(DAEMON.startup)
    try:
        TR.run_forever()
    except KeyboardInterrupt:
        print
    TR.stop()
    DAEMON.close()
