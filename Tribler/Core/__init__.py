# Written by Arno Bakker
# see LICENSE.txt for license information
from threading import RLock

# Written by BitTornado authors and Arno Bakker
# see LICENSE.txt for license information

# Arno: FIXME _idprefix is also defined in .__init__ and that's the one
# actually used in connections, so make sure they are defined in one place
# (here) and correct.
#

from Tribler.__init__ import LIBRARYNAME

if LIBRARYNAME == "Tribler":
    version_id = '6.2.0-rc1'
    product_name = 'Tribler'
    version_short = 'Tribler-' + version_id
    report_email = 'tribler@tribler.org'
    # Arno: looking at Azureus BTPeerIDByteDecoder this letter is free
    # 'T' is BitTornado, 'A' is ABC, 'TR' is Transmission
    TRIBLER_PEERID_LETTER = 'R'
else:
    version_id = '3.2.0'  # aka M32
    product_name = 'NextShare'
    version_short = 'NextShare-' + version_id
    report_email = 'support@p2p-next.org'
    # Arno: looking at Azureus BTPeerIDByteDecoder this letter is free
    # 'T' is BitTornado, 'A' is ABC, 'TR' is Transmission
    TRIBLER_PEERID_LETTER = 'N'


version = version_short + ' (' + product_name + ')'
_idprefix = TRIBLER_PEERID_LETTER


from types import StringType
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

# for subver in version_short[2:].split('.'):
for subver in version_short.split('-')[1].split('.'):
    try:
        subver = int(subver)
    except:
        subver = 0
    _idprefix += mapbase64[subver]
_idprefix += ('-' * (6 - len(_idprefix)))
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
            # r = random.randint(0,sys.maxint)
            r = random.randint(0, 255)
            x += chr(r)
        x = x[:20]

    s = ''
    for i in x:
        s += mapbase64[ord(i) & 0x3F]
    _idrandom[0] = s[:11]  # peer id = iprefix (6) + ins (3) + random


def createPeerID(ins='---'):
    assert isinstance(ins, StringType)
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
    return [client, version]


def warnDisperyThread(func):
    def invoke_func(*args, **kwargs):
        from threading import currentThread
        from traceback import print_stack

        if currentThread().getName() == 'Dispersy':
            import inspect
            caller = inspect.stack()[1]
            callerstr = "%s %s:%s" % (caller[3], caller[1], caller[2])

            from time import time
            import sys
            print >> sys.stderr, long(time()), "CANNOT BE ON DISPERSYTHREAD %s %s:%s called by %s" % (func.__name__, func.func_code.co_filename, func.func_code.co_firstlineno, callerstr)
            print_stack()

        return func(*args, **kwargs)

    invoke_func.__name__ = func.__name__
    return invoke_func


class NoDispersyRLock():

    def __init__(self):
        self.lock = RLock()
        self.__enter__ = self.lock.__enter__
        self.__exit__ = self.lock.__exit__

    @warnDisperyThread
    def acquire(self, blocking=1):
        return self.lock.acquire(blocking)

    @warnDisperyThread
    def release(self):
        return self.lock.release()
