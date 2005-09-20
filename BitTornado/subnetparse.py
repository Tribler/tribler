# Written by John Hoffman
# see LICENSE.txt for license information

from bisect import bisect, insort

try:
    True
except:
    True = 1
    False = 0
    bool = lambda x: not not x

hexbinmap = {
    '0': '0000',
    '1': '0001',
    '2': '0010',
    '3': '0011',
    '4': '0100',
    '5': '0101',
    '6': '0110',
    '7': '0111',
    '8': '1000',
    '9': '1001',
    'a': '1010',
    'b': '1011',
    'c': '1100',
    'd': '1101',
    'e': '1110',
    'f': '1111',
    'x': '0000',
}

chrbinmap = {}
for n in xrange(256):
    b = []
    nn = n
    for i in xrange(8):
        if nn & 0x80:
            b.append('1')
        else:
            b.append('0')
        nn <<= 1
    chrbinmap[n] = ''.join(b)


def to_bitfield_ipv4(ip):
    ip = ip.split('.')
    if len(ip) != 4:
        raise ValueError, "bad address"
    b = []
    for i in ip:
        b.append(chrbinmap[int(i)])
    return ''.join(b)

def to_bitfield_ipv6(ip):
    b = ''
    doublecolon = False

    if ip == '':
        raise ValueError, "bad address"
    if ip == '::':      # boundary handling
        ip = ''
    elif ip[:2] == '::':
        ip = ip[1:]
    elif ip[0] == ':':
        raise ValueError, "bad address"
    elif ip[-2:] == '::':
        ip = ip[:-1]
    elif ip[-1] == ':':
        raise ValueError, "bad address"
    for n in ip.split(':'):
        if n == '':     # double-colon
            if doublecolon:
                raise ValueError, "bad address"
            doublecolon = True
            b += ':'
            continue
        if n.find('.') >= 0: # IPv4
            n = to_bitfield_ipv4(n)
            b += n + '0'*(32-len(n))
            continue
        n = ('x'*(4-len(n))) + n
        for i in n:
            b += hexbinmap[i]
    if doublecolon:
        pos = b.find(':')
        b = b[:pos]+('0'*(129-len(b)))+b[pos+1:]
    if len(b) != 128:   # always check size
        raise ValueError, "bad address"
    return b

ipv4addrmask = to_bitfield_ipv6('::ffff:0:0')[:96]

class IP_List:
    def __init__(self):
        self.ipv4list = []
        self.ipv6list = []

    def __nonzero__(self):
        return bool(self.ipv4list or self.ipv6list)


    def append(self, ip, depth = 256):
        if ip.find(':') < 0:        # IPv4
            insort(self.ipv4list,to_bitfield_ipv4(ip)[:depth])
        else:
            b = to_bitfield_ipv6(ip)
            if b.startswith(ipv4addrmask):
                insort(self.ipv4list,b[96:][:depth-96])
            else:
                insort(self.ipv6list,b[:depth])


    def includes(self, ip):
        if not (self.ipv4list or self.ipv6list):
            return False
        if ip.find(':') < 0:        # IPv4
            b = to_bitfield_ipv4(ip)
        else:
            b = to_bitfield_ipv6(ip)
            if b.startswith(ipv4addrmask):
                b = b[96:]
        if len(b) > 32:
            l = self.ipv6list
        else:
            l = self.ipv4list
        for map in l[bisect(l,b)-1:]:
            if b.startswith(map):
                return True
            if map > b:
                return False
        return False


    def read_fieldlist(self, file):   # reads a list from a file in the format 'ip/len <whatever>'
        f = open(file, 'r')
        while True:
            line = f.readline()
            if not line:
                break
            line = line.strip().expandtabs()
            if not line or line[0] == '#':
                continue
            try:
                line, garbage = line.split(' ',1)
            except:
                pass
            try:
                line, garbage = line.split('#',1)
            except:
                pass
            try:
                ip, depth = line.split('/')
            except:
                ip = line
                depth = None
            try:
                if depth is not None:                
                    depth = int(depth)
                self.append(ip,depth)
            except:
                print '*** WARNING *** could not parse IP range: '+line
        f.close()


    def set_intranet_addresses(self):
        self.append('127.0.0.1',8)
        self.append('10.0.0.0',8)
        self.append('172.16.0.0',12)
        self.append('192.168.0.0',16)
        self.append('169.254.0.0',16)
        self.append('::1')
        self.append('fe80::',16)
        self.append('fec0::',16)

    def set_ipv4_addresses(self):
        self.append('::ffff:0:0',96)

def ipv6_to_ipv4(ip):
    ip = to_bitfield_ipv6(ip)
    if not ip.startswith(ipv4addrmask):
        raise ValueError, "not convertible to IPv4"
    ip = ip[-32:]
    x = ''
    for i in range(4):
        x += str(int(ip[:8],2))
        if i < 3:
            x += '.'
        ip = ip[8:]
    return x

def to_ipv4(ip):
    if is_ipv4(ip):
        _valid_ipv4(ip)
        return ip
    return ipv6_to_ipv4(ip)

def is_ipv4(ip):
    return ip.find(':') < 0

def _valid_ipv4(ip):
    ip = ip.split('.')
    if len(ip) != 4:
        raise ValueError
    for i in ip:
        chr(int(i))

def is_valid_ip(ip):
    try:
        if is_ipv4(ip):
            _valid_ipv4(ip)
            return True
        to_bitfield_ipv6(ip)
        return True
    except:
        return False
