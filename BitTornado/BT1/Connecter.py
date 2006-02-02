# Written by Bram Cohen and Pawel Garbacki
# see LICENSE.txt for license information

import traceback,sys
from sha import sha

from BitTornado.bitfield import Bitfield
from BitTornado.clock import clock
from binascii import b2a_hex
from BitTornado.bencode import bencode,bdecode

from MessageID import *
# 2fastbt_
from Tribler.toofastbt.Logger import get_logger
from Tribler.CacheDB.CacheDBHandler import PeerDBHandler
# _2fastbt

try:
    True
except:
    True = 1
    False = 0

DEBUG = False

UNAUTH_PERMID_PERIOD = 3600

def toint(s):
    return long(b2a_hex(s), 16)

def tobinary(i):
    return (chr(i >> 24) + chr((i >> 16) & 0xFF) + 
        chr((i >> 8) & 0xFF) + chr(i & 0xFF))

def show(s):
    text = []
    for i in xrange(len(s)): 
        text.append(ord(s[i]))
    return text
    
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
        self.unauth_permid = None
        self.looked_for_permid = UNAUTH_PERMID_PERIOD-3
        self.closed = False
            
    def get_myip(self, real=False):
        return self.connection.get_myip(real)
    
    def get_myport(self, real=False):
        return self.connection.get_myport(real)
        
    def get_ip(self, real=False):
        return self.connection.get_ip(real)

    def get_port(self, real=False):
        return self.connection.get_port(real)

    #def set_permid(self, permid):
    #    self.permid = permid

    def get_unauth_permid(self):
        """ Linking this normal connection to the PermID of its peer in all
            cases is non-trivial. I currently hack this unsafe solution where
            we look at the database periodically.

            FIXME: very expensive operation in 50.000 peer DB indexed on permid
        """
        self.looked_for_permid += 1
        if self.looked_for_permid >= UNAUTH_PERMID_PERIOD:
            self.looked_for_permid = 0
            peerdb = PeerDBHandler()
            peerList = peerdb.findPeers('ip',self.connection.get_ip())
            if len(peerList) != 1:
                return # Don't know
            self.unauth_permid = peerList[0]['permid']
        return self.unauth_permid

    def get_id(self):
        return self.connection.get_id()

    def get_readable_id(self):
        return self.connection.get_readable_id()

    def close(self):
        if DEBUG:
            print 'connection closed'
        self.connection.close()
        self.closed = True
        
    def is_closed(self):
        return self.closed

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
            if (self.partial_message or self.just_unchoked is None
                or not self.upload.interested or self.download.active_requests):
                self.just_unchoked = 0
            else:
                self.just_unchoked = clock()

    def send_request(self, index, begin, length):
        self._send_message(REQUEST + tobinary(index) + 
            tobinary(begin) + tobinary(length))
        if DEBUG:
            print "sending REQUEST to",self.get_ip()
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
            # Merkle: send hashlist along with piece in HASHPIECE message
            index, begin, hashlist, piece = s
            if self.connecter.merkle_torrent:
                bhashlist = bencode(hashlist)
                self.partial_message = ''.join((
                                tobinary(1+4+4+4+len(bhashlist)+len(piece)), HASHPIECE,
                                tobinary(index), tobinary(begin), tobinary(len(bhashlist)), bhashlist, piece.tostring() ))
            else:
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
# 2fastbt_
    def __init__(self, make_upload, downloader, choker, numpieces,
            totalup, config, ratelimiter, merkle_torrent, sched = None, 
            coordinator = None, helper = None):
# _2fastbt
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
        self.merkle_torrent = merkle_torrent
        # 2fastbt_
        self.coordinator = coordinator
        self.helper = helper
        self.round = 0
        # _2fastbt

    def how_many_connections(self):
        return len(self.connections)

    def connection_made(self, connection):
        c = Connection(connection, self)
        self.connections[connection] = c
        #TODO: overlay swarm also needs upload and download to control transferring rate
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
        # connection: Encrypter.Connection; c: Connecter.Connection
        c = self.connections[connection]    
        t = message[0]
        if t == BITFIELD and c.got_anything:
            if DEBUG:
                print "Close on BITFIELD"
            connection.close()
            return
        c.got_anything = True
        if (t in [CHOKE, UNCHOKE, INTERESTED, NOT_INTERESTED] and 
                len(message) != 1):
            if DEBUG:
                print "Close on bad (UN)CHOKE/(NOT_)INTERESTED",t
            connection.close()
            return
        if t == CHOKE:
            if DEBUG:
                print "connecter: Got CHOKE from",connection.get_ip()
            c.download.got_choke()
        elif t == UNCHOKE:
            if DEBUG:
                print "connecter: Got UNCHOKE from",connection.get_ip()
            c.download.got_unchoke()
        elif t == INTERESTED:
            #FIXME: c.upload may be None
            c.upload.got_interested()
        elif t == NOT_INTERESTED:
            c.upload.got_not_interested()
        elif t == HAVE:
            if len(message) != 5:
                if DEBUG:
                    print "Close on bad HAVE: msg len"
                connection.close()
                return
            i = toint(message[1:])
            if i >= self.numpieces:
                if DEBUG:
                    print "Close on bad HAVE: index out of range"
                connection.close()
                return
            if DEBUG:
                print "connecter: Got HAVE(",i,") from",connection.get_ip()
            c.download.got_have(i)
        elif t == BITFIELD:
            try:
                b = Bitfield(self.numpieces, message[1:])
            except ValueError:
                if DEBUG:
                    print "Close on bad BITFIELD"
                connection.close()
                return
            #FIXME: c.download may be None
            c.download.got_have_bitfield(b)
        elif t == REQUEST:
            if len(message) != 13:
                if DEBUG:
                    print "Close on bad REQUEST: msg len"
                connection.close()
                return
            i = toint(message[1:5])
            if i >= self.numpieces:
                if DEBUG:
                    print "Close on bad REQUEST: index out of range"
                connection.close()
                return
            if DEBUG:
                print "connecter: Got REQUEST(",i,") from",connection.get_ip()
            c.got_request(i, toint(message[5:9]), toint(message[9:]))
        elif t == CANCEL:
            if len(message) != 13:
                if DEBUG:
                    print "Close on bad CANCEL: msg len"
                connection.close()
                return
            i = toint(message[1:5])
            if i >= self.numpieces:
                if DEBUG:
                    print "Close on bad CANCEL: index out of range"
                connection.close()
                return
            c.upload.got_cancel(i, toint(message[5:9]), 
                toint(message[9:]))
        elif t == PIECE:
            if len(message) <= 9:
                if DEBUG:
                    print "Close on bad PIECE: msg len"
                connection.close()
                return
            i = toint(message[1:5])
            if i >= self.numpieces:
                if DEBUG:
                    print "Close on bad PIECE: msg len"
                connection.close()
                return
            if c.download.got_piece(i, toint(message[5:9]), [], message[9:]):
                self.got_piece(i)
        elif t == HASHPIECE:
            try:
                # Merkle: Handle pieces with hashes
                if len(message) <= 13:
                    if DEBUG:
                        print "Close on bad HASHPIECE: msg len"
                    connection.close()
                    return
                i = toint(message[1:5])
                if i >= self.numpieces:
                    if DEBUG:
                        print "Close on bad HASHPIEC: index out of range"
                    connection.close()
                    return
                begin = toint(message[5:9])
                len_hashlist = toint(message[9:13])
                bhashlist = message[13:13+len_hashlist]
                hashlist = bdecode(bhashlist)
                piece = message[13+len_hashlist:]
                if c.download.got_piece(i, begin, hashlist, piece):
                    self.got_piece(i)
            except Exception,e:
                if DEBUG:
                    print "Close on bad HASHPIECE: exception",str(e)
                    traceback.print_exc(file=sys.stdout)
                connection.close()
                return
        else:
            connection.close()
