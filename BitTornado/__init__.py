product_name = 'ABC'
version_short = 'ABC-3.1.0'

version = version_short + ' (' + product_name + ' - BitTornado 0.3.13'
report_email = version_short+'@degreez.net'

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
    
mapbase64 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-'

_idprefix = version_short[0]
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
