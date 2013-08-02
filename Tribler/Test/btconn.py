# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information

import socket
import sys
from binascii import b2a_hex
from struct import pack, unpack
from StringIO import StringIO

DEBUG = False

current_version = 3  # TODO: Fix this temporary hack.
lowest_version = 2

protocol_name = "BitTorrent protocol"
default_option_pattern = '\x00\x00\x00\x00\x00\x30\x00\x00'
overlay_infohash = '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'


def toint(s):
    return long(b2a_hex(s), 16)


def tobinary(i):
    return (chr(i >> 24) + chr((i >> 16) & 0xFF) +
            chr((i >> 8) & 0xFF) + chr(i & 0xFF))


class BTConnection:

    def __init__(self, hostname, port, opensock=None, user_option_pattern=None, user_infohash=None, myid=None, mylistenport=None, myoversion=None):
        assert user_option_pattern is None or isinstance(user_option_pattern, str)
        assert user_option_pattern is None or len(user_option_pattern) == 8
        assert user_infohash is None or isinstance(user_infohash, str)
        assert user_infohash is None or len(user_infohash) == 20
        assert myid is None or isinstance(myid, str)
        assert myid is None or len(myid) == 20
        self.hisport = port
        self.buffer = StringIO()
        if mylistenport is None:
            self.myport = 481
        else:
            self.myport = mylistenport
        if myid is None:
            self.myid = "".zfill(20)
            if myoversion is None:
                myoversion = current_version
            self.myid = self.myid[:16] + pack('<H', lowest_version) + pack('<H', myoversion)
            self.myid = self.myid[:14] + pack('<H', self.myport) + self.myid[16:]
        else:
            self.myid = myid
        self.hisid = None

        if opensock:
            self.s = opensock
        else:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.connect((hostname, port))
        handshake = chr(len(protocol_name))
        handshake += protocol_name
        if user_option_pattern is None:
            handshake += default_option_pattern
        else:
            handshake += user_option_pattern
        if user_infohash is None:
            self.expected_infohash = overlay_infohash
        else:
            self.expected_infohash = user_infohash
        handshake += self.expected_infohash
        handshake += self.myid
        if DEBUG:
            print >> sys.stderr, "btconn: Sending handshake len", len(handshake)
        self.s.send(handshake)

    def get_my_id(self):
        return self.myid

    def get_his_id(self):
        return self.hisid

    def get_my_fake_listen_port(self):
        return self.myport

    def read_handshake(self):
        data = self._readn(68)
        assert(data[0] == chr(len(protocol_name)))
        assert(data[1:20] == protocol_name)
        assert(data[28:48] == self.expected_infohash)

        self.hisid = data[48:68]
        hisport = unpack('<H', self.hisid[14:16])[0]
        assert(hisport == self.hisport)
        low_ver = unpack('<H', self.hisid[16:18])[0]
        assert(low_ver == lowest_version)
        cur_ver = unpack('<H', self.hisid[18:20])[0]
        # if DEBUG:
        #    print >> sys.stderr, "btconn: his cur_ver: ", cur_ver
        #    print >> sys.stderr, "btconn: my curr_ver: ", current_version
        assert(cur_ver == current_version)

    def read_handshake_medium_rare(self, close_ok=False):
        data = self._readn(68)
        if len(data) == 0:
            if close_ok:
                return
            else:
                assert(len(data) > 0)
        assert(data[0] == chr(len(protocol_name)))
        assert(data[1:20] == protocol_name)
        assert(data[28:48] == self.expected_infohash)
        self.hisid = data[48:68]
        # don't check encoded fields

    def close(self):
        self.s.close()

    def send(self, data):
        """ send length-prefixed message """
        self.s.send(tobinary(len(data)))
        self.s.send(data)

    def recv(self):
        """ received length-prefixed message """
        size_data = self._readn(4)
        if len(size_data) == 0:
            return size_data
        size = toint(size_data)
        if DEBUG and size > 10000:
            print >> sys.stderr, "btconn: waiting for message size", size
        if size == 0:
            # BT keep alive message, don't report upwards
            return self.recv()
        else:
            return self._readn(size)

    def _readn(self, n):
        """ read n bytes from socket stream """
        nwant = n
        while True:
            try:
                data = self.s.recv(nwant)
            except socket.error as e:
                if e[0] == 10035:
                    # WSAEWOULDBLOCK on Windows
                    continue
                elif e[0] == 10054:
                    # WSAECONNRESET on Windows
                    print >> sys.stderr, "btconn:", e, "converted to EOF"
                    return ''  # convert to EOF
                else:
                    raise e
            if DEBUG:
                print >> sys.stderr, "btconn: _readn got", len(data), "bytes"
            if len(data) == 0:
                # raise socket.error(ECONNRESET,'arno says connection closed')
                return data
            nwant -= len(data)
            self.buffer.write(data)
            if nwant == 0:
                break
        self.buffer.seek(0)
        data = self.buffer.read(n)
        self.buffer.seek(0)
        return data
