# Written by Pawel Garbacki
# see LICENSE.txt for license information

from BitTornado.BT1.Encrypter import Connection #, control_option_pattern
from BitTornado.BT1.Connecter import tobinary
from socket import error as socketerror
from Logger import get_logger
from time import sleep
from sys import exit, exc_info
from thread import allocate_lock
from traceback import print_exc
import socket

MAX_ROUNDS = 200

class SingleSocket:
    def __init__(self, sock, handler, ip = None):
        self.socket = sock
        self.handler = handler
        self.fileno = sock.fileno()
        self.connected = False
        self.skipped = 0
        try:
            self.ip = self.socket.getpeername()[0]
        except:
            if ip is None:
                self.ip = 'unknown'
            else:
                self.ip = ip
        
    def get_ip(self, real=False):
        if real:
            try:
                self.ip = self.socket.getpeername()[0]
            except:
                pass
        return self.ip
        
    def close(self):
        assert self.socket
        self.connected = False
        sock = self.socket
        self.socket = None
        sock.close()
        raise Exception('socket.close', 'Control connection closed unexpectedly')

    def shutdown(self, val):
        self.socket.shutdown(val)

    def write(self, s):
        assert self.socket is not None
        self.connected = True
        try:
            while len(s) > 0:
                amount = self.socket.send(s)
                if amount == 0:
                    break
                s = s[amount:]
        except socket.error, e:
            raise e
    
    def read(self):
        self.connected = True
        try:
            data = self.socket.recv(100000)
            self.handler.data_came_in(self, data)
        except socket.error, e:
            raise e

    def set_handler(self, handler):
        self.handler = handler

class Helper:
    def __init__(self, num_pieces, coordinator_ip, coordinator_port, 
            encoder = None, coordinator = None):
        print "CREATING HELPER FOR COORDINATOR",coordinator_ip,coordinator_port
        self.encoder = encoder
        self.coordinator_ip = coordinator_ip
        self.coordinator_port = coordinator_port
        self.reserved_pieces = [False] * num_pieces
        self.ignored_pieces = [False] * num_pieces
        self.coordinator_con = None
        self.coordinator_data_con = None
        self.coordinator = coordinator
        self.counter = 0
        self.completed = False
        self.distr_reserved_pieces = [False] * num_pieces
        self.marker = [True] * num_pieces
        self.round = 0

### Private methods
    def _start_connection(self, dns, socktype = socket.AF_INET, handler = None):
        if handler is None:
            handler = self
        
        sock = socket.socket(socktype, socket.SOCK_STREAM)
        sock.setblocking(1)
        try:
            sock.connect_ex(dns)
        except socket.error:
            raise
        except Exception, e:
            raise socket.error(str(e))
        s = SingleSocket(sock, handler, dns[0])
        return s

    def _connect_to_coordinator(self):
        # c instanceof SocketHandler.SingleSocket
        c = self._start_connection((self.coordinator_ip, self.coordinator_port))
        # con instanceof Encrypter.Connection
        con = Connection(self.encoder, c, None, locally_initiated = True, control_con = True) # options = control_option_pattern
        c.set_handler(con)
#        self.encoder.connections[c] = con
        while self.coordinator_con is None:
            c.read()

    def test(self):
        if self.coordinator is None:
            self._connect_to_coordinator()
        result = self.reserve_piece(10)
        print "reserve piece returned: " + str(result)
        print "Test passed"

    def _reserve_piece(self, piece):
        self.reserved_pieces[piece] = True
        self.distr_reserved_pieces[piece] = True
        self.ignored_pieces[piece] = False

    def _ignore_piece(self, piece):
        if not self.is_reserved(piece):
            self.ignored_pieces[piece] = True
            self.distr_reserved_pieces[piece] = True

    def get_coordinator_id(self):
        if self.coordinator_con is None:
            return None
        return self.coordinator_con.get_id()

### download_bt1 interface
    def set_encoder(self, encoder):
        self.encoder = encoder

### PiecePicker and Downloader interface
    def is_reserved(self, piece):
        if self.reserved_pieces[piece] or (self.coordinator is not None and self.is_complete()):
            return True
        return self.reserved_pieces[piece]

    def is_ignored(self, piece):
        if not self.ignored_pieces[piece] or (self.coordinator is not None and self.is_complete()):
            return False
        return self.ignored_pieces[piece]

    def is_complete(self):
        if self.completed:
            return True
        self.round = (self.round + 1) % MAX_ROUNDS
        if self.round != 0:
            return False
        if self.coordinator is not None:
            self.completed = (self.coordinator.reserved_pieces == self.marker)
        else:
            self.completed = (self.distr_reserved_pieces == self.marker)
        return self.completed

    def reserve_pieces(self, pieces, all_or_nothing = False):
        pieces_to_send = []
        try:
            ex = "None"
            result = []
            for piece in pieces:
                if self.is_reserved(piece):
                    result.append(piece)
                elif not self.is_ignored(piece):
                    pieces_to_send.append(piece)
            if pieces_to_send == []:
                return result
            if self.coordinator is not None:
                new_reserved_pieces = self.coordinator.reserve_pieces(None, pieces_to_send, all_or_nothing)
                for piece in new_reserved_pieces:
                    self._reserve_piece(piece)
            else:
                if self.coordinator_con is None:
                    self._connect_to_coordinator()

                self.counter += 1
                ex = "self.coordinator_con.send_reserve_pieces(pieces_to_send)"
                self.coordinator_con.send_reserve_pieces(pieces_to_send)
                while self.counter > 0:
                    ex = "self.coordinator_con.connection.connection.read() conter: " + str(self.counter)
                    self.coordinator_con.connection.connection.read()

            result = []
            for piece in pieces:
                if self.is_reserved(piece):
                    result.append(piece)
                else:
                    self._ignore_piece(piece)
        except Exception, e:
            print "EXCEPTION in " + str(ex)
            print_exc(e)
            print exc_info()
        return result

    def reserve_piece(self, piece):
        if self.coordinator is not None and self.is_complete():
            return True
        new_reserved_pieces = self.reserve_pieces([piece])
        if new_reserved_pieces == []:
            return False
        else:
            return True
       
### Connecter interface
    def pieces_reserved(self, pieces):
        try:
            for piece in pieces:
                if piece > 0:
                    self._reserve_piece(piece)
                else:
                    self._ignore_piece(-piece)
            self.counter -= 1
        except:
            print "EXCEPTION!"
