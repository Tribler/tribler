## Arno: FIXME _idprefix is also defined in BitTornado.__init__ and that's the one
## actually used in connections, so make sure they are defined in one place
## (here) and correct.
##

version_id = '3.5.1'
product_name = 'Tribler'
version_short = 'Tribler-' + version_id

version = version_short + ' (' + product_name + ')'
report_email = 'triblersoft@gmail.com'

from types import StringType
from sha import sha
from time import time, clock
from string import strip
import socket
try:
    from os import getpid
except ImportError:
    def getpid():
        return 1
from base64 import decodestring 
import sys
from traceback import print_exc
    
mapbase64 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-'

# Arno: looking at Azureus BTPeerIDByteDecoder this letter is free
# 'T' is BitTornado, 'A' is ABC, 'TR' is Transmission
_idprefix = 'R'
#for subver in version_short[2:].split('.'):
for subver in version_short.split('-')[1].split('.'):
    try:
        subver = int(subver)
    except:
        subver = 0
    _idprefix += mapbase64[subver]
_idprefix += ('-' * (6-len(_idprefix)))
_idrandom = [None]




def resetPeerIDs():
    try:
        f = open('/dev/urandom', 'rb')
        x = f.read(20)
        f.close()
    except:
        x = ''

    l1 = 0
    t = clock()
    while t == clock():
        l1 += 1
    l2 = 0
    t = long(time()*100)
    while t == long(time()*100):
        l2 += 1
    l3 = 0
    if l2 < 1000:
        t = long(time()*10)
        while t == long(clock()*10):
            l3 += 1
    x += ( repr(time()) + '/' + str(time()) + '/'
           + str(l1) + '/' + str(l2) + '/' + str(l3) + '/'
           + str(getpid()) )

    s = ''
    for i in sha(x).digest()[-11:]:
        s += mapbase64[ord(i) & 0x3F]
    _idrandom[0] = s
        
resetPeerIDs()

def createPeerID(ins = '---'):
    assert type(ins) is StringType
    assert len(ins) == 3
    return _idprefix + ins + _idrandom[0]

def decodePeerID(id):
    client = None
    version = None
    try:
        if id[0] == '-':
            # Azureus type ID: 
            client = id[1:3]
            encversion = id[3:7]
        else:
            # Shadow type ID:
            client = id[0]
            encversion = id[1:4] 
        version = ''
        for i in range(len(encversion)):
            for j in range(len(mapbase64)):
                if mapbase64[j] == encversion[i]:
                    if len(version) > 0:
                        version += '.'
                    version += str(j)
    except:
        print_exc(file=sys.stderr)
    return [client,version]