# Written by BitTornado authors and Arno Bakker
# see LICENSE.txt for license information

## Arno: FIXME _idprefix is also defined in BitTornado.__init__ and that's the one
## actually used in connections, so make sure they are defined in one place
## (here) and correct.
##

version_id = '5.1.2'
product_name = 'Tribler'
version_short = 'Tribler-' + version_id

version = version_short + ' (' + product_name + ')'
report_email = 'triblersoft@gmail.com'

from types import StringType
from Tribler.Core.Utilities.Crypto import sha
from time import time, clock
from string import strip
import socket
import random
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
TRIBLER_PEERID_LETTER='R'
_idprefix = TRIBLER_PEERID_LETTER

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
        # Arno: make sure there is some randomization when on win32
        random.seed()
        x = ''
        while len(x) < 20:
            #r = random.randint(0,sys.maxint)
            r = random.randint(0,255)
            x += chr(r)
        x = x[:20]

    s = ''
    for i in x:
        s += mapbase64[ord(i) & 0x3F]
    _idrandom[0] = s[:11] # peer id = iprefix (6) + ins (3) + random
        
def createPeerID(ins = '---'):
    assert type(ins) is StringType
    assert len(ins) == 3
    resetPeerIDs()
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
