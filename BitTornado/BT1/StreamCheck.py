# Written by Bram Cohen
# see LICENSE.txt for license information

from cStringIO import StringIO
from binascii import b2a_hex
from socket import error as socketerror
from urllib import quote
from traceback import print_exc
import Connecter
try:
    True
except:
    True = 1
    False = 0

DEBUG = False


protocol_name = 'BitTorrent protocol'
option_pattern = chr(0)*8

def toint(s):
    return long(b2a_hex(s), 16)

def tobinary(i):
    return (chr(i >> 24) + chr((i >> 16) & 0xFF) + 
        chr((i >> 8) & 0xFF) + chr(i & 0xFF))

hexchars = '0123456789ABCDEF'
hexmap = []
for i in xrange(256):
    hexmap.append(hexchars[(i&0xF0)/16]+hexchars[i&0x0F])

def tohex(s):
    r = []
    for c in s:
        r.append(hexmap[ord(c)])
    return ''.join(r)

def make_readable(s):
    if not s:
        return ''
    if quote(s).find('%') >= 0:
        return tohex(s)
    return '"'+s+'"'
   
def toint(s):
    return long(b2a_hex(s), 16)

# header, reserved, download id, my id, [length, message]

streamno = 0


class StreamCheck:
    def __init__(self):
        global streamno
        self.no = streamno
        streamno += 1
        self.buffer = StringIO()
        self.next_len, self.next_func = 1, self.read_header_len

    def read_header_len(self, s):
        if ord(s) != len(protocol_name):
            print self.no, 'BAD HEADER LENGTH'
        return len(protocol_name), self.read_header

    def read_header(self, s):
        if s != protocol_name:
            print self.no, 'BAD HEADER'
        return 8, self.read_reserved

    def read_reserved(self, s):
        return 20, self.read_download_id

    def read_download_id(self, s):
        if DEBUG:
            print self.no, 'download ID ' + tohex(s)
        return 20, self.read_peer_id

    def read_peer_id(self, s):
        if DEBUG:
            print self.no, 'peer ID' + make_readable(s)
        return 4, self.read_len

    def read_len(self, s):
        l = toint(s)
        if l > 2 ** 23:
            print self.no, 'BAD LENGTH: '+str(l)+' ('+s+')'
        return l, self.read_message

    def read_message(self, s):
        if not s:
            return 4, self.read_len
        m = s[0]
        if ord(m) > 8:
            print self.no, 'BAD MESSAGE: '+str(ord(m))
        if m == Connecter.REQUEST:
            if len(s) != 13:
                print self.no, 'BAD REQUEST SIZE: '+str(len(s))
                return 4, self.read_len
            index = toint(s[1:5])
            begin = toint(s[5:9])
            length = toint(s[9:])
            print self.no, 'Request: '+str(index)+': '+str(begin)+'-'+str(begin)+'+'+str(length)
        elif m == Connecter.CANCEL:
            if len(s) != 13:
                print self.no, 'BAD CANCEL SIZE: '+str(len(s))
                return 4, self.read_len
            index = toint(s[1:5])
            begin = toint(s[5:9])
            length = toint(s[9:])
            print self.no, 'Cancel: '+str(index)+': '+str(begin)+'-'+str(begin)+'+'+str(length)
        elif m == Connecter.PIECE:
            index = toint(s[1:5])
            begin = toint(s[5:9])
            length = len(s)-9
            print self.no, 'Piece: '+str(index)+': '+str(begin)+'-'+str(begin)+'+'+str(length)
        else:
            print self.no, 'Message '+str(ord(m))+' (length '+str(len(s))+')'
        return 4, self.read_len

    def write(self, s):
        while True:
            i = self.next_len - self.buffer.tell()
            if i > len(s):
                self.buffer.write(s)
                return
            self.buffer.write(s[:i])
            s = s[i:]
            m = self.buffer.getvalue()
            self.buffer.reset()
            self.buffer.truncate()
            x = self.next_func(m)
            self.next_len, self.next_func = x
