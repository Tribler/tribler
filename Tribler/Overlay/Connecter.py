# Written by Bram Cohen
# see LICENSE.txt for license information

from BitTornado.bitfield import Bitfield
from BitTornado.clock import clock
from binascii import b2a_hex

try:
    True
except:
    True = 1
    False = 0

DEBUG = False

def toint(s):
    return long(b2a_hex(s), 16)

def tobinary(i):
    return (chr(i >> 24) + chr((i >> 16) & 0xFF) + 
        chr((i >> 8) & 0xFF) + chr(i & 0xFF))

CHOKE = chr(0)
UNCHOKE = chr(1)
INTERESTED = chr(2)
NOT_INTERESTED = chr(3)
# index
HAVE = chr(4)
# index, bitfield
BITFIELD = chr(5)
# index, begin, length
REQUEST = chr(6)
# index, begin, piece
PIECE = chr(7)
# index, begin, piece
CANCEL = chr(8)

class Connection:
    def __init__(self, connection, connecter):
        self.connection = connection
        self.connecter = connecter
        self.got_anything = False
        self.next_upload = None
        self.outqueue = []
        self.partial_message = None
        self.download = None
        self.upload = None
        self.send_choke_queued = False
        self.just_unchoked = None

    def get_ip(self, real=False):
        return self.connection.get_ip(real)

    def get_id(self):
        return self.connection.get_id()

    def get_readable_id(self):
        return self.connection.get_readable_id()

    def close(self):
        if DEBUG:
            print 'connection closed'
        self.connection.close()

    def is_locally_initiated(self):
        return self.connection.is_locally_initiated()

    def send_interested(self):
        self._send_message(INTERESTED)

    def send_not_interested(self):
        self._send_message(NOT_INTERESTED)

    def send_choke(self):
        if self.partial_message:
            self.send_choke_queued = True
        else:
            self._send_message(CHOKE)
            self.upload.choke_sent()
            self.just_unchoked = 0

    def send_unchoke(self):
        if self.send_choke_queued:
            self.send_choke_queued = False
            if DEBUG:
                print 'CHOKE SUPPRESSED'
        else:
            self._send_message(UNCHOKE)
            if ( self.partial_message or self.just_unchoked is None
                 or not self.upload.interested or self.download.active_requests ):
                self.just_unchoked = 0
            else:
                self.just_unchoked = clock()

    def send_request(self, index, begin, length):
        self._send_message(REQUEST + tobinary(index) + 
            tobinary(begin) + tobinary(length))
        if DEBUG:
            print 'sent request: '+str(index)+': '+str(begin)+'-'+str(begin+length)

    def send_cancel(self, index, begin, length):
        self._send_message(CANCEL + tobinary(index) + 
            tobinary(begin) + tobinary(length))
        if DEBUG:
            print 'sent cancel: '+str(index)+': '+str(begin)+'-'+str(begin+length)

    def send_bitfield(self, bitfield):
        self._send_message(BITFIELD + bitfield)

    def send_have(self, index):
        self._send_message(HAVE + tobinary(index))

    def send_keepalive(self):
        self._send_message('')

    def _send_message(self, s):
        s = tobinary(len(s))+s
        if self.partial_message:
            self.outqueue.append(s)
        else:
            self.connection.send_message_raw(s)

    def send_partial(self, bytes):
        if self.connection.closed:
            return 0
        if self.partial_message is None:
            s = self.upload.get_upload_chunk()
            if s is None:
                return 0
            index, begin, piece = s
            self.partial_message = ''.join((
                            tobinary(len(piece) + 9), PIECE, 
                            tobinary(index), tobinary(begin), piece.tostring()))
            if DEBUG:
                print 'sending chunk: '+str(index)+': '+str(begin)+'-'+str(begin+len(piece))

        if bytes < len(self.partial_message):
            self.connection.send_message_raw(self.partial_message[:bytes])
            self.partial_message = self.partial_message[bytes:]
            return bytes

        q = [self.partial_message]
        self.partial_message = None
        if self.send_choke_queued:
            self.send_choke_queued = False
            self.outqueue.append(tobinary(1)+CHOKE)
            self.upload.choke_sent()
            self.just_unchoked = 0
        q.extend(self.outqueue)
        self.outqueue = []
        q = ''.join(q)
        self.connection.send_message_raw(q)
        return len(q)

    def get_upload(self):
        return self.upload

    def get_download(self):
        return self.download

    def set_download(self, download):
        self.download = download

    def backlogged(self):
        return not self.connection.is_flushed()

    def got_request(self, i, p, l):
        self.upload.got_request(i, p, l)
        if self.just_unchoked:
            self.connecter.ratelimiter.ping(clock() - self.just_unchoked)
            self.just_unchoked = 0
    



class Connecter:
    def __init__(self, make_upload, downloader, choker, numpieces,
            totalup, config, ratelimiter, sched = None):
        self.downloader = downloader
        self.make_upload = make_upload
        self.choker = choker
        self.numpieces = numpieces
        self.config = config
        self.ratelimiter = ratelimiter
        self.rate_capped = False
        self.sched = sched
        self.totalup = totalup
        self.rate_capped = False
        self.connections = {}
        self.external_connection_made = 0

    def how_many_connections(self):
        return len(self.connections)

    def connection_made(self, connection):
        c = Connection(connection, self)
        self.connections[connection] = c
        c.upload = self.make_upload(c, self.ratelimiter, self.totalup)
        c.download = self.downloader.make_download(c)
        self.choker.connection_made(c)
        return c

    def connection_lost(self, connection):
        c = self.connections[connection]
        del self.connections[connection]
        if c.download:
            c.download.disconnected()
        self.choker.connection_lost(c)

    def connection_flushed(self, connection):
        conn = self.connections[connection]
        if conn.next_upload is None and (conn.partial_message is not None
               or conn.upload.buffer):
            self.ratelimiter.queue(conn)
            
    def got_piece(self, i):
        for co in self.connections.values():
            co.send_have(i)

    def got_message(self, connection, message):
        c = self.connections[connection]
        t = message[0]
        if t == BITFIELD and c.got_anything:
            connection.close()
            return
        c.got_anything = True
        if (t in [CHOKE, UNCHOKE, INTERESTED, NOT_INTERESTED] and 
                len(message) != 1):
            connection.close()
            return
        if t == CHOKE:
            c.download.got_choke()
        elif t == UNCHOKE:
            c.download.got_unchoke()
        elif t == INTERESTED:
            if not c.download.have.complete():
                c.upload.got_interested()
        elif t == NOT_INTERESTED:
            c.upload.got_not_interested()
        elif t == HAVE:
            if len(message) != 5:
                connection.close()
                return
            i = toint(message[1:])
            if i >= self.numpieces:
                connection.close()
                return
            if c.download.got_have(i):
                c.upload.got_not_interested()
        elif t == BITFIELD:
            try:
                b = Bitfield(self.numpieces, message[1:])
            except ValueError:
                connection.close()
                return
            if c.download.got_have_bitfield(b):
                c.upload.got_not_interested()
        elif t == REQUEST:
            if len(message) != 13:
                connection.close()
                return
            i = toint(message[1:5])
            if i >= self.numpieces:
                connection.close()
                return
            c.got_request(i, toint(message[5:9]), 
                toint(message[9:]))
        elif t == CANCEL:
            if len(message) != 13:
                connection.close()
                return
            i = toint(message[1:5])
            if i >= self.numpieces:
                connection.close()
                return
            c.upload.got_cancel(i, toint(message[5:9]), 
                toint(message[9:]))
        elif t == PIECE:
            if len(message) <= 9:
                connection.close()
                return
            i = toint(message[1:5])
            if i >= self.numpieces:
                connection.close()
                return
            if c.download.got_piece(i, toint(message[5:9]), message[9:]):
                self.got_piece(i)
        else:
            connection.close()
