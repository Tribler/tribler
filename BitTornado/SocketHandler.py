# Written by Bram Cohen
# see LICENSE.txt for license information

import socket
from errno import EWOULDBLOCK
try:
    from select import poll, POLLIN, POLLOUT, POLLERR, POLLHUP
    timemult = 1000
except ImportError:
    from selectpoll import poll, POLLIN, POLLOUT, POLLERR, POLLHUP
    timemult = 1
from time import sleep
from clock import clock
import sys
from random import shuffle, randrange
from natpunch import UPnP_open_port, UPnP_close_port

# 2fastbt_
from Tribler.toofastbt.Logger import get_logger
# _2fastbt

# from BT1.StreamCheck import StreamCheck
# import inspect
try:
    True
except:
    True = 1
    False = 0

DEBUG = False
FIREWALL = False

all = POLLIN | POLLOUT

UPnP_ERROR = "unable to forward port via UPnP"

class SingleSocket:
    """ 
    There are two places to create SingleSocket:
    incoming connection -- SocketHandler.handle_events
    outgoing connection -- SocketHandler.start_connection_raw
    """
    
    def __init__(self, socket_handler, sock, handler, ip = None):
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
            (self.myip,self.myport) = self.socket.getsockname()
            (self.ip,self.port) = self.socket.getpeername()
        except:
            if ip is None:
                self.ip = 'unknown'
            else:
                self.ip = ip
        
    def get_ip(self, real=False):
        if real:
            try:
                (self.ip,self.port) = self.socket.getpeername()
            except:
                pass
        return self.ip
    
    def get_port(self, real=False):
        if real:
            self.get_ip(True)
        return self.port

    def get_myip(self, real=False):
        if real:
            try:
                (self.myip,self.myport) = self.socket.getsockname()
            except:
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
        self.socket_handler.poll.unregister(sock)
        sock.close()

    def shutdown(self, val):
        self.socket.shutdown(val)

    def is_flushed(self):
        return not self.buffer

    def write(self, s):
#        self.check.write(s)
        assert self.socket is not None
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
            except socket.error, e:
                try:
                    dead = e[0] != EWOULDBLOCK
                except:
                    dead = True
                self.skipped += 1
            if self.skipped >= 3:
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


class SocketHandler:
    def __init__(self, timeout, ipv6_enable, readsize = 100000):
        self.timeout = timeout
        self.ipv6_enable = ipv6_enable
        self.readsize = readsize
        self.poll = poll()
        # {socket: SingleSocket}
        self.single_sockets = {}
        self.dead_from_write = []
        self.max_connects = 1000
        self.port_forwarded = None
        self.servers = {}

    def scan_for_timeouts(self):
        t = clock() - self.timeout
        tokill = []
        for s in self.single_sockets.values():
            if s.last_hit < t:
                tokill.append(s)
        for k in tokill:
            if k.socket is not None:
                self._close_socket(k)

    def bind(self, port, bind = '', reuse = False, ipv6_socket_style = 1, upnp = 0):
        port = int(port)
        addrinfos = []
        self.servers = {}
        self.interfaces = []
        # if bind != "" thread it as a comma seperated list and bind to all
        # addresses (can be ips or hostnames) else bind to default ipv6 and
        # ipv4 address
        if bind:
            if self.ipv6_enable:
                socktype = socket.AF_UNSPEC
            else:
                socktype = socket.AF_INET
            bind = bind.split(',')
            for addr in bind:
                if sys.version_info < (2, 2):
                    addrinfos.append((socket.AF_INET, None, None, None, (addr, port)))
                else:
                    addrinfos.extend(socket.getaddrinfo(addr, port,
                                               socktype, socket.SOCK_STREAM))
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
                if DEBUG:
                    print "Try to bind socket on", addrinfo[4], "..."
                server.bind(addrinfo[4])
                self.servers[server.fileno()] = server
                if bind:
                    self.interfaces.append(server.getsockname()[0])
                if DEBUG:
                    print "OK"
                server.listen(64)
                self.poll.register(server, POLLIN)
            except socket.error, e:
                for server in self.servers.values():
                    try:
                        server.close()
                    except:
                        pass
                if self.ipv6_enable and ipv6_socket_style == 0 and self.servers:
                    raise socket.error('blocked port (may require ipv6_binds_v4 to be set)')
                raise socket.error(str(e))
        if not self.servers:
            raise socket.error('unable to open server port')
        if upnp:
            if not UPnP_open_port(port):
                for server in self.servers.values():
                    try:
                        server.close()
                    except:
                        pass
                    self.servers = None
                    self.interfaces = None
                raise socket.error(UPnP_ERROR)
            self.port_forwarded = port
        self.port = port

    def find_and_bind(self, minport, maxport, bind = '', reuse = False,
                      ipv6_socket_style = 1, upnp = 0, randomizer = False):
        e = 'maxport less than minport - no ports to check'
        if maxport-minport < 50 or not randomizer:
            portrange = range(minport, maxport+1)
            if randomizer:
                shuffle(portrange)
                portrange = portrange[:20]  # check a maximum of 20 ports
        else:
            portrange = []
            while len(portrange) < 20:
                listen_port = randrange(minport, maxport+1)
                if not listen_port in portrange:
                    portrange.append(listen_port)
        if DEBUG and FIREWALL:    # try 22 first, because TU only opens port 22 for SSH...
            try:
                first_port = 22
                self.bind(first_port, bind,
                               ipv6_socket_style = ipv6_socket_style, upnp = upnp)
                return first_port
            except socket.error, e:
                pass
        for listen_port in portrange:
            try:
                self.bind(listen_port, bind,
                               ipv6_socket_style = ipv6_socket_style, upnp = upnp)
                return listen_port
            except socket.error, e:
                pass
        raise socket.error(str(e))


    def set_handler(self, handler):
        self.handler = handler


    def start_connection_raw(self, dns, socktype = socket.AF_INET, handler = None):
        # handler = Encoder, self.handler = Multihandler
        if handler is None:
            handler = self.handler
        sock = socket.socket(socktype, socket.SOCK_STREAM)
        sock.setblocking(0)
        try:
            sock.connect_ex(dns)
        except socket.error, e:
            if DEBUG:
                print "SocketHandler: SocketError in connect_ex",str(e)
            raise
        except Exception, e:
            if DEBUG:
                print "SocketHandler: Exception in connect_ex",str(e)      
            raise socket.error(str(e))
        self.poll.register(sock, POLLIN)
        s = SingleSocket(self, sock, handler, dns[0])    # create socket to connect the peers obtained from tracker
        self.single_sockets[sock.fileno()] = s
        if DEBUG:
            print "SocketHandler: Created Socket"
        return s


    def start_connection(self, dns, handler = None, randomize = False):
        if handler is None:
            handler = self.handler
        if sys.version_info < (2, 2):
            s = self.start_connection_raw(dns, socket.AF_INET, handler)
        else:
            if self.ipv6_enable:
                socktype = socket.AF_UNSPEC
            else:
                socktype = socket.AF_INET
            try:
                addrinfos = socket.getaddrinfo(dns[0], int(dns[1]),
                                               socktype, socket.SOCK_STREAM)
            except socket.error, e:
                raise
            except Exception, e:
                raise socket.error(str(e))
            if randomize:
                shuffle(addrinfos)
            for addrinfo in addrinfos:
                try:
                    s = self.start_connection_raw(addrinfo[4], addrinfo[0], handler)
                    break
                except:
                    pass
            else:
                raise socket.error('unable to connect')
        return s


    def _sleep(self):
        sleep(1)
        
    def handle_events(self, events):
        for sock, event in events:
            s = self.servers.get(sock)    # socket.socket
            if s:
                if event & (POLLHUP | POLLERR) != 0:
                    if DEBUG:
                        print "SocketHandler: Got event, close server socket"
                    self.poll.unregister(s)
                    s.close()
                    del self.servers[sock]
                elif len(self.single_sockets) < self.max_connects:
                    try:
                        newsock, addr = s.accept()
                        if DEBUG:
                            print "Got connection from",newsock.getpeername()
                        newsock.setblocking(0)
                        nss = SingleSocket(self, newsock, self.handler)    # create socket for incoming peers and tracker
                        self.single_sockets[newsock.fileno()] = nss
                        self.poll.register(newsock, POLLIN)
                        self.handler.external_connection_made(nss)
                    except socket.error,e:
                        if DEBUG:
                            print "SocketHandler: SocketError while accepting new connection",str(e)
                        self._sleep()
# 2fastbt_
                else:
                    get_logger().log(3, "sockethandler.sockethandler too many connects")
# _2fastbt
            else:
                s = self.single_sockets.get(sock)
                if not s:
                    continue
                s.connected = True
                if (event & (POLLHUP | POLLERR)):
                    if DEBUG:
                        print "SocketHandler: Got event, connect socket got error"
                    self._close_socket(s)
                    continue
                if (event & POLLIN):
                    try:
                        s.last_hit = clock()
                        data = s.socket.recv(100000)
                        if not data:
                            self._close_socket(s)
                        else:
                            # btlaunchmany: NewSocketHandler, btdownloadheadless: Encrypter.Connection
                            s.handler.data_came_in(s, data)
                    except socket.error, e:
                        if DEBUG:
                            print "SocketHandler: Socket error",str(e)
                        code, msg = e
                        if code != EWOULDBLOCK:
                            self._close_socket(s)
                            continue
                if (event & POLLOUT) and s.socket and not s.is_flushed():
                    s.try_write()
                    if s.is_flushed():
                        s.handler.connection_flushed(s)

    def close_dead(self):
        while self.dead_from_write:
            old = self.dead_from_write
            self.dead_from_write = []
            for s in old:
                if s.socket:
                    self._close_socket(s)

    def _close_socket(self, s):
        s.close()
        s.handler.connection_lost(s)

    def do_poll(self, t):
        r = self.poll.poll(t*timemult)
        if r is None:
            connects = len(self.single_sockets)
            to_close = int(connects*0.05)+1 # close 5% of sockets
            self.max_connects = connects-to_close
            closelist = self.single_sockets.values()
            shuffle(closelist)
            closelist = closelist[:to_close]
            for sock in closelist:
                self._close_socket(sock)
            return []
        return r     

    def get_stats(self):
        return { 'interfaces': self.interfaces, 
                 'port': self.port, 
                 'upnp': self.port_forwarded is not None }


    def shutdown(self):
        for ss in self.single_sockets.values():
            try:
                ss.close()
            except:
                pass
        for server in self.servers.values():
            try:
                server.close()
            except:
                pass
        if self.port_forwarded is not None:
            UPnP_close_port(self.port_forwarded)

