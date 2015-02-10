# Written by Bram Cohen
# see LICENSE.txt for license information

import socket
import errno
import logging
import sys
from time import sleep
from random import shuffle, randrange
from traceback import print_exc
try:
    from select import poll, POLLIN, POLLOUT, POLLERR, POLLHUP
    timemult = 1000
except ImportError:
    from selectpoll import poll, POLLIN, POLLOUT, POLLERR, POLLHUP
    timemult = 1

from Tribler.Core.Utilities.clock import clock

try:
    True
except:
    True = 1
    False = 0

all = POLLIN | POLLOUT

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035    # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK


class InterruptSocketHandler(object):

    @staticmethod
    def data_came_in(interrupt_socket, data):
        pass


class InterruptSocket(object):

    """
    When we need the poll to return before the timeout expires, we
    will send some data to the InterruptSocket and discard the data.
    """

    def __init__(self, socket_handler):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.socket_handler = socket_handler
        self.handler = InterruptSocketHandler

        self.ip = "127.0.0.1"
        self.port = None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.interrupt_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.socket.bind((self.ip, 0))
        self.port = self.socket.getsockname()[1]
        self._logger.debug("Bound InterruptSocket on port %s", self.port)

        # start listening to the InterruptSocket
        self.socket_handler.single_sockets[self.socket.fileno()] = self
        self.socket_handler.poll.register(self.socket, POLLIN)

    def interrupt(self):
        self.interrupt_socket.sendto("+", (self.ip, self.port))

    def get_ip(self):
        return self.ip

    def get_port(self):
        return self.port


class UdpSocket(object):

    """ Class to hold socket and handler for a UDP socket. """

    def __init__(self, socket, handler):
        self.socket = socket
        self.handler = handler


class SingleSocket(object):

    """
    There are two places to create SingleSocket:
    incoming connection -- SocketHandler.handle_events
    outgoing connection -- SocketHandler.start_connection_raw
    """

    def __init__(self, socket_handler, sock, handler, ip=None):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.socket_handler = socket_handler
        self.socket = sock
        self.handler = handler
        self.buffer = []
        self.last_hit = clock()
        self.fileno = sock.fileno()
        self.connected = False
        self.skipped = 0
#        self.check = StreamCheck()
        self.myip = None
        self.myport = -1
        self.ip = None
        self.port = -1
        try:
            myname = self.socket.getsockname()
            self.myip = myname[0]
            self.myport = myname[1]
            peername = self.socket.getpeername()
            self.ip = peername[0]
            self.port = peername[1]
        except:
            # print_exc()
            if ip is None:
                self.ip = 'unknown'
            else:
                self.ip = ip

    def get_ip(self, real=False):
        if real:
            try:
                peername = self.socket.getpeername()
                self.ip = peername[0]
                self.port = peername[1]
            except:
                # print_exc()
                pass
        return self.ip

    def get_port(self, real=False):
        if real:
            self.get_ip(True)
        return self.port

    def get_myip(self, real=False):
        if real:
            try:
                myname = self.socket.getsockname()
                self.myip = myname[0]
                self.myport = myname[1]
            except:
                print_exc()
                pass
        return self.myip

    def get_myport(self, real=False):
        if real:
            self.get_myip(True)
        return self.myport

    def close(self):
        '''
        for x in xrange(5,0,-1):
            try:
                f = inspect.currentframe(x).f_code
                print (f.co_filename,f.co_firstlineno,f.co_name)
                del f
            except:
                pass
        print ''
        '''
        assert self.socket
        self.connected = False
        sock = self.socket
        self.socket = None
        self.buffer = []
        del self.socket_handler.single_sockets[self.fileno]

        try:
            self.socket_handler.poll.unregister(sock)
        except Exception as e:
            self._logger.error("SocketHandler: close: sock is %s", sock)
            print_exc()
        sock.close()

    def shutdown(self, val):
        self.socket.shutdown(val)

    def is_flushed(self):
        return not self.buffer

    def write(self, s):
#        self.check.write(s)
        # Arno: fishy concurrency problem, sometimes self.socket is None
        if self.socket is None:
            return
        # assert self.socket is not None
        self.buffer.append(s)
        if len(self.buffer) == 1:
            self.try_write()

    def try_write(self):

        if self.connected:
            dead = False
            try:
                while self.buffer:
                    buf = self.buffer[0]
                    amount = self.socket.send(buf)
                    if amount == 0:
                        self.skipped += 1
                        break
                    self.skipped = 0
                    if amount != len(buf):
                        self.buffer[0] = buf[amount:]
                        break
                    del self.buffer[0]
            except socket.error as e:
                blocked = False
                try:
                    blocked = (e[0] == SOCKET_BLOCK_ERRORCODE)
                    dead = not blocked
                except:
                    dead = True
                if not blocked:
                    self.skipped += 1
            if self.skipped >= 5:
                dead = True
            if dead:
                self.socket_handler.dead_from_write.append(self)
                return
        if self.buffer:
            self.socket_handler.poll.register(self.socket, all)
        else:
            self.socket_handler.poll.register(self.socket, POLLIN)

    def set_handler(self, handler):    # can be: NewSocketHandler, Encoder, En_Connection
        self.handler = handler


class SocketHandler(object):

    def __init__(self, timeout, ipv6_enable, readsize=100000):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.timeout = timeout
        self.ipv6_enable = ipv6_enable
        self.readsize = readsize
        self.poll = poll()
        # {socket: SingleSocket}
        self.single_sockets = {}
        self.dead_from_write = []
        self.max_connects = 1000
        self.servers = {}
        self.interfaces = []
        self.btengine_said_reachable = False
        self.interrupt_socket = None
        self.udp_sockets = {}

        self.port = None
        self.handler = None

    def scan_for_timeouts(self):
        t = clock() - self.timeout
        tokill = []
        for s in self.single_sockets.values():
            # Only SingleSockets can be closed because of timeouts
            if isinstance(s, SingleSocket) and s.last_hit < t:
                tokill.append(s)
        for k in tokill:
            if k.socket is not None:
                self._logger.debug("SocketHandler: scan_timeout closing connection %s", k.get_ip())
                self._close_socket(k)

    def bind(self, port, bind=[], reuse=False, ipv6_socket_style=1, handler=None):
        port = int(port)
        addrinfos = []
        # if bind != [] bind to all specified addresses (can be IPs or hostnames)
        # else bind to default ipv6 and ipv4 address
        if bind:
            if self.ipv6_enable:
                socktype = socket.AF_UNSPEC
            else:
                socktype = socket.AF_INET
            for addr in bind:
                if sys.version_info < (2, 2):
                    addrinfos.append((socket.AF_INET, None, None, None, (addr, port)))
                else:
                    addrinfos.extend(socket.getaddrinfo(addr, port, socktype, socket.SOCK_STREAM))
        else:
            if self.ipv6_enable:
                addrinfos.append([socket.AF_INET6, None, None, None, ('', port)])
            if not addrinfos or ipv6_socket_style != 0:
                addrinfos.append([socket.AF_INET, None, None, None, ('', port)])
        for addrinfo in addrinfos:
            try:
                server = socket.socket(addrinfo[0], socket.SOCK_STREAM)
                if reuse:
                    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.setblocking(0)
                self._logger.debug("SocketHandler: Try to bind socket on %s ...", addrinfo[4])
                server.bind(addrinfo[4])
                self.servers[server.fileno()] = (server, handler)
                if bind:
                    self.interfaces.append(server.getsockname()[0])
                self._logger.debug("SocketHandler: OK")
                server.listen(64)
                self.poll.register(server, POLLIN)
            except socket.error as e:
                for server, _ in self.servers.values():
                    try:
                        server.close()
                    except:
                        pass
                if self.ipv6_enable and ipv6_socket_style == 0 and self.servers:
                    raise socket.error('blocked port (may require ipv6_binds_v4 to be set)')
                raise socket.error(str(e))
        if not self.servers:
            raise socket.error('unable to open server port')
        self.port = port

    def find_and_bind(self, first_try, minport, maxport, bind='', reuse=False, ipv6_socket_style=1,
                      randomizer=False, handler=None):
        e = 'maxport less than minport - no ports to check'
        if maxport - minport < 50 or not randomizer:
            portrange = range(minport, maxport + 1)
            if randomizer:
                shuffle(portrange)
                portrange = portrange[:20]  # check a maximum of 20 ports
        else:
            portrange = []
            while len(portrange) < 20:
                listen_port = randrange(minport, maxport + 1)
                if not listen_port in portrange:
                    portrange.append(listen_port)
        if first_try != 0:    # try 22 first, because TU only opens port 22 for SSH...
            try:
                self.bind(first_try, bind, reuse=reuse, ipv6_socket_style=ipv6_socket_style, handler=handler)
                return first_try
            except socket.error as e:
                pass
        for listen_port in portrange:
            try:
                self.bind(listen_port, bind, reuse=reuse, ipv6_socket_style=ipv6_socket_style, handler=handler)
                return listen_port
            except socket.error as e:
                raise
        raise socket.error(str(e))

    def set_handler(self, handler):
        self.handler = handler

    def start_connection_raw(self, dns, socktype=socket.AF_INET, handler=None):
        # handler = Encoder, self.handler = Multihandler
        if handler is None:
            handler = self.handler
        sock = socket.socket(socktype, socket.SOCK_STREAM)
        sock.setblocking(0)
        try:
            self._logger.debug("SocketHandler: Initiate connection to %s with socket #%s", dns, sock.fileno())
            # Arno,2007-01-23: http://docs.python.org/lib/socket-objects.html
            # says that connect_ex returns an error code (and can still throw
            # exceptions). The original code never checked the return code.
            #
            err = sock.connect_ex(dns)
            if err == 0:
                msg = 'No error'
            else:
                msg = errno.errorcode[err]
            self._logger.debug("SocketHandler: connect_ex on socket #%s returned %s %s", sock.fileno(), err, msg)
            if err != 0:
                if sys.platform == 'win32' and err == 10035:
                    # Arno, 2007-02-23: win32 always returns WSAEWOULDBLOCK, whether
                    # the connect is to a live peer or not. Win32's version
                    # of EINPROGRESS
                    pass
                elif err == errno.EINPROGRESS:  # or err == errno.EALREADY or err == errno.EWOULDBLOCK:
                    # [Stevens98] says that UNICES return EINPROGRESS when the connect
                    # does not immediately succeed, which is almost always the case.
                    pass
                else:
                    raise socket.error((err, errno.errorcode[err]))
        except socket.error as e:
            self._logger.debug("SocketHandler: SocketError in connect_ex %s", e)
            raise
        except Exception as e:
            self._logger.debug("SocketHandler: Exception in connect_ex %s", e)
            raise socket.error(str(e))

        s = SingleSocket(self, sock, handler, dns[0])    # create socket to connect the peers obtained from tracker
        self.single_sockets[sock.fileno()] = s
        self.poll.register(sock, POLLIN)
        return s

    def start_connection(self, dns, handler=None, randomize=False):
        if handler is None:
            handler = self.handler
        if sys.version_info < (2, 2):
            s = self.start_connection_raw(dns, socket.AF_INET, handler)
        else:
#            if self.ipv6_enable:
#                socktype = socket.AF_UNSPEC
#            else:
#                socktype = socket.AF_INET
            try:
                try:
                    """
                    Arno: When opening a new connection, the network thread calls the
                    getaddrinfo() function (=DNS resolve), as apparently the input
                    sometimes is a hostname. At the same time the tracker thread uses
                    this same function to resolve the tracker name to an IP address.
                    However, on Python for Windows this method has concurrency control
                    protection that allows only 1 request at a time.

                    In some cases resolving the tracker name takes a very long time,
                    meanwhile blocking the network thread!!!! And that only wanted to
                    resolve some IP address to some IP address, i.e., do nothing!!!

                    Sol: don't call getaddrinfo() is the input is an IP address, and
                    submit a bug to python that it shouldn't lock when the op is
                    a null op
                    """
                    socket.inet_aton(dns[0])  # IPVSIX: change to inet_pton()
                    addrinfos = [(socket.AF_INET, None, None, None, (dns[0], dns[1]))]
                except:
                    # print_exc()
                    try:
                        # Jie: we attempt to use this socktype to connect ipv6 addresses.
                        socktype = socket.AF_UNSPEC
                        addrinfos = socket.getaddrinfo(dns[0], int(dns[1]), socktype, socket.SOCK_STREAM)
                    except:
                        socktype = socket.AF_INET
                        addrinfos = socket.getaddrinfo(dns[0], int(dns[1]), socktype, socket.SOCK_STREAM)
            except socket.error as e:
                raise
            except Exception as e:
                raise socket.error(str(e))
            if randomize:
                shuffle(addrinfos)
            for addrinfo in addrinfos:
                try:
                    s = self.start_connection_raw(addrinfo[4], addrinfo[0], handler)
                    break
                except Exception as e:
                    print_exc()
                    pass  # FIXME Arno: ???? raise e
            else:
                raise socket.error('unable to connect')
        return s

    def _sleep(self):
        sleep(1)

    def handle_events(self, events):
        for sock, event in events:
            s, h = self.servers.get(sock, (None, None))    # socket.socket
            if s:
                if event & (POLLHUP | POLLERR) != 0:
                    self._logger.debug("SocketHandler: Got event, close server socket")
                    self.poll.unregister(s)
                    del self.servers[sock]
                else:
                    try:
                        newsock, addr = s.accept()
                        self._logger.debug("SocketHandler: Got connection from %s", newsock.getpeername())
                        if not self.btengine_said_reachable:
                            self.btengine_said_reachable = True

                        # Only use the new socket if we can spare the
                        # connections. Otherwise we will silently drop
                        # the connection.
                        if len(self.single_sockets) < self.max_connects:
                            newsock.setblocking(0)
                            # create socket for incoming peers and tracker
                            nss = SingleSocket(self, newsock, (h or self.handler))
                            self.single_sockets[newsock.fileno()] = nss
                            self.poll.register(newsock, POLLIN)
                            (h or self.handler).external_connection_made(nss)
                        else:
                            self._logger.info("SocketHandler: too many connects")
                            newsock.close()

                    except socket.error as e:
                        self._logger.debug("SocketHandler: SocketError while accepting new connection %s", e)
                        self._sleep()
                continue

            s = self.udp_sockets.get(sock)
            if s:
                packets = []
                try:
                    try:
                        while True:
                            try:
                                (data, addr) = s.socket.recvfrom(65535)
                            except socket.error, e:
                                # They both have the same value, but keep it for clarity.
                                if e.args[0] in [errno.EAGAIN, errno.EWOULDBLOCK]:
                                    break
                                else:
                                    raise

                            self._logger.debug("SocketHandler: Got UDP data %s len %s", addr, len(data))
                            packets.append((addr, data))

                    except socket.error as e:
                        self._logger.debug("SocketHandler: UDP Socket error %s", e)

                finally:
                    s.handler.data_came_in(packets)

                continue

            s = self.single_sockets.get(sock)
            if s:
                if event & (POLLHUP | POLLERR):
                    self._logger.debug("SocketHandler: Got event, connect socket got error %s", sock)
                    self._logger.debug("SocketHandler: Got event, connect socket got error %s %s", s.ip, s.port)
                    self._close_socket(s)
                    continue
                if event & POLLIN:
                    try:
                        s.last_hit = clock()
                        data = s.socket.recv(100000)
                        if not data:
                            self._logger.debug("SocketHandler: no-data closing connection %s %s",
                                               s.get_ip(), s.get_port())
                            self._close_socket(s)
                        else:
                            # btlaunchmany: NewSocketHandler, btdownloadheadless: Encrypter.Connection
                            s.handler.data_came_in(s, data)
                    except socket.error as e:
                        self._logger.debug("SocketHandler: Socket error %s", e)
                        code, msg = e
                        if code != SOCKET_BLOCK_ERRORCODE:
                            self._logger.debug("SocketHandler: closing connection because not WOULDBLOCK %s, error %s",
                                               s.get_ip(), code)
                            self._close_socket(s)
                            continue
                if (event & POLLOUT) and s.socket and not s.is_flushed():
                    s.connected = True
                    s.try_write()
                    if s.is_flushed():
                        s.handler.connection_flushed(s)
            else:
                # Arno, 2012-08-1: Extra protection.
                self._logger.info("SocketHandler: got event on unregistered sock %s", sock)
                try:
                    self.poll.unregister(sock)
                except:
                    pass

    def close_dead(self):
        while self.dead_from_write:
            old = self.dead_from_write
            self.dead_from_write = []
            for s in old:
                if s.socket:
                    self._logger.debug("SocketHandler: close_dead closing connection %s", s.get_ip())
                    self._close_socket(s)

    def _close_socket(self, s):
        self._logger.debug("SocketHandler: closing connection to %s", s.get_ip())
        s.close()
        s.handler.connection_lost(s)

    def do_poll(self, t):
        r = self.poll.poll(t * timemult)
        if r is None:
            connects = len(self.single_sockets)
            to_close = int(connects * 0.05) + 1  # close 5% of sockets
            self.max_connects = connects - to_close
            closelist = [sock for sock in self.single_sockets.values() if not isinstance(sock, InterruptSocket)]
            shuffle(closelist)
            closelist = closelist[:to_close]
            for sock in closelist:
                self._logger.debug("SocketHandler: do_poll closing connection %s", sock.get_ip())
                self._close_socket(sock)
            return []
        return r

    def get_stats(self):
        return {'interfaces': self.interfaces,
                'port': self.port}

    def shutdown(self):
        for ss in self.single_sockets.values():
            try:
                ss.close()
            except:
                pass
        for server, _ in self.servers.values():
            try:
                server.close()
            except:
                pass

    #
    # Interface for Khasmir, called from RawServer
    #
    #
    def create_udpsocket(self, port, host):
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 870400)
        server.bind((host, port))
        server.setblocking(0)
        return server

    def start_listening_udp(self, serversocket, handler):
        self.udp_sockets[serversocket.fileno()] = UdpSocket(serversocket, handler)
        self.poll.register(serversocket, POLLIN)

    def stop_listening_udp(self, serversocket):
        self.poll.unregister(serversocket)
        del self.udp_sockets[serversocket.fileno()]

    #
    # Interface for the InterruptSocket
    #
    def get_interrupt_socket(self):
        """
        Create a socket to interrupt the poll when the thread needs to
        continue without waiting for the timeout
        """
        if not self.interrupt_socket:
            self.interrupt_socket = InterruptSocket(self)
        return self.interrupt_socket
