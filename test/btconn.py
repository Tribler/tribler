# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information

import socket
from binascii import b2a_hex
from struct import pack,unpack
from StringIO import StringIO

DEBUG=False

current_version = 2
lowest_version = 2

protocol_name = "BitTorrent protocol"
# Enable Tribler extensions:
# Left-most bit = Azureus Enhanced Messaging Protocol (AEMP)
# Left+42 bit = Tribler Simple Merkle Hashes extension
# Left+43 bit = Tribler Overlay swarm extension
# Right-most bit = BitTorrent DHT extension
option_pattern = '\x00\x00\x00\x00\x00\x30\x00\x00'
overlay_infohash = '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

def toint(s):
    return long(b2a_hex(s), 16)

def tobinary(i):
    return (chr(i >> 24) + chr((i >> 16) & 0xFF) + 
        chr((i >> 8) & 0xFF) + chr(i & 0xFF))

class BTConnection:
    def __init__(self,hostname,port,opensock=None):
        self.hisport = port
        self.buffer = StringIO()
        self.myport = 481
        self.myid = "".zfill(20)
        self.myid = self.myid[:16] + pack('H', lowest_version) + pack('H', current_version)
        self.myid = self.myid[:14] + pack('H', self.myport) + self.myid[16:]
        self.hisid = None

        if opensock:
            self.s = opensock
        else:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.connect((hostname, port))
        handshake = chr(len(protocol_name))
        handshake += protocol_name
        handshake += option_pattern
        handshake += overlay_infohash
        handshake += self.myid
        self.s.send(handshake)

    def get_my_id(self):
        return self.myid
        
    def get_his_id(self):
        return self.hisid

    def read_handshake(self):
        data = self._readn(68)
        assert(data[0] == chr(len(protocol_name)))
        assert(data[1:20] == protocol_name)
        assert(data[20:28] == option_pattern)
        assert(data[28:48] == overlay_infohash)
        self.hisid = data[48:68]
        hisport = unpack('H', self.hisid[14:16])[0]
        assert(hisport == self.hisport)
        low_ver = unpack('H', self.hisid[16:18])[0]
        assert(low_ver == lowest_version)
        cur_ver = unpack('H', self.hisid[18:20])[0]
        assert(cur_ver == current_version)

    def read_handshake_medium_rare(self):
        data = self._readn(68)
        assert(data[0] == chr(len(protocol_name)))
        assert(data[1:20] == protocol_name)
        assert(data[20:28] == option_pattern)
        assert(data[28:48] == overlay_infohash)
        self.hisid = data[48:68]
        # don't check encoded fields

    def close(self):
        self.s.close()

    def send(self,data):
        """ send length-prefixed message """
        self.s.send(tobinary(len(data)))
        self.s.send(data)

    def recv(self):
        """ received length-prefixed message """
        size_data = self._readn(4)
        size = toint(size_data)
        if DEBUG:
            print "btconn: waiting for message size",size
        return self._readn(size)

    def _readn(self,n):
        """ read n bytes from socket stream """
        nwant = n
        while True:
            data = self.s.recv(nwant)
            if DEBUG:
                print "btconn: _readn got",len(data),"bytes"
            if len(data) == 0:
                raise Exception('arno says connection closed')
            nwant -= len(data)
            self.buffer.write(data)
            if nwant == 0:
                break
        self.buffer.seek(0)
        data = self.buffer.read(n)
        self.buffer.seek(0)
        return data
