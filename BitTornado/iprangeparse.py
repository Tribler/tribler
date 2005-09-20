# Written by John Hoffman
# see LICENSE.txt for license information

from bisect import bisect, insort

try:
    True
except:
    True = 1
    False = 0
    bool = lambda x: not not x


def to_long_ipv4(ip):
    ip = ip.split('.')
    if len(ip) != 4:
        raise ValueError, "bad address"
    b = 0L
    for n in ip:
        b *= 256
        b += int(n)
    return b


def to_long_ipv6(ip):
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

    b = []
    doublecolon = False
    for n in ip.split(':'):
        if n == '':     # double-colon
            if doublecolon:
                raise ValueError, "bad address"
            doublecolon = True
            b.append(None)
            continue
        if n.find('.') >= 0: # IPv4
            n = n.split('.')
            if len(n) != 4:
                raise ValueError, "bad address"
            for i in n:
                b.append(int(i))
            continue
        n = ('0'*(4-len(n))) + n
        b.append(int(n[:2],16))
        b.append(int(n[2:],16))
    bb = 0L
    for n in b:
        if n is None:
            for i in xrange(17-len(b)):
                bb *= 256
            continue
        bb *= 256
        bb += n
    return bb

ipv4addrmask = 65535L*256*256*256*256

class IP_List:
    def __init__(self):
        self.ipv4list = []  # starts of ranges
        self.ipv4dict = {}  # start: end of ranges
        self.ipv6list = []  # "
        self.ipv6dict = {}  # "

    def __nonzero__(self):
        return bool(self.ipv4list or self.ipv6list)


    def append(self, ip_beg, ip_end = None):
        if ip_end is None:
            ip_end = ip_beg
        else:
            assert ip_beg <= ip_end
        if ip_beg.find(':') < 0:        # IPv4
            ip_beg = to_long_ipv4(ip_beg)
            ip_end = to_long_ipv4(ip_end)
            l = self.ipv4list
            d = self.ipv4dict
        else:
            ip_beg = to_long_ipv6(ip_beg)
            ip_end = to_long_ipv6(ip_end)
            bb = ip_beg % (256*256*256*256)
            if bb == ipv4addressmask:
                ip_beg -= bb
                ip_end -= bb
                l = self.ipv4list
                d = self.ipv4dict
            else:
                l = self.ipv6list
                d = self.ipv6dict

        pos = bisect(l,ip_beg)-1
        done = pos < 0
        while not done:
            p = pos
            while p < len(l):
                range_beg = l[p]
                if range_beg > ip_end+1:
                    done = True
                    break
                range_end = d[range_beg]
                if range_end < ip_beg-1:
                    p += 1
                    if p == len(l):
                        done = True
                        break
                    continue
                # if neither of the above conditions is true, the ranges overlap
                ip_beg = min(ip_beg, range_beg)
                ip_end = max(ip_end, range_end)
                del l[p]
                del d[range_beg]
                break

        insort(l,ip_beg)
        d[ip_beg] = ip_end


    def includes(self, ip):
        if not (self.ipv4list or self.ipv6list):
            return False
        if ip.find(':') < 0:        # IPv4
            ip = to_long_ipv4(ip)
            l = self.ipv4list
            d = self.ipv4dict
        else:
            ip = to_long_ipv6(ip)
            bb = ip % (256*256*256*256)
            if bb == ipv4addressmask:
                ip -= bb
                l = self.ipv4list
                d = self.ipv4dict
            else:
                l = self.ipv6list
                d = self.ipv6dict
        for ip_beg in l[bisect(l,ip)-1:]:
            if ip == ip_beg:
                return True
            ip_end = d[ip_beg]
            if ip > ip_beg and ip <= ip_end:
                return True
        return False


    # reads a list from a file in the format 'whatever:whatever:ip-ip'
    # (not IPv6 compatible at all)
    def read_rangelist(self, file):
        f = open(file, 'r')
        while True:
            line = f.readline()
            if not line:
                break
            line = line.strip()
            if not line or line[0] == '#':
                continue
            line = line.split(':')[-1]
            try:
                ip1,ip2 = line.split('-')
            except:
                ip1 = line
                ip2 = line
            try:
                self.append(ip1.strip(),ip2.strip())
            except:
                print '*** WARNING *** could not parse IP range: '+line
        f.close()

def is_ipv4(ip):
    return ip.find(':') < 0

def is_valid_ip(ip):
    try:
        if is_ipv4(ip):
            a = ip.split('.')
            assert len(a) == 4
            for i in a:
                chr(int(i))
            return True
        to_long_ipv6(ip)
        return True
    except:
        return False
