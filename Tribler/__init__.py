product_name = 'Tribler_ABC'
version_short = 'Tribler_ABC-3.3.0'

version = version_short + ' (' + product_name + ' - BitTornado 0.3.13'
report_email = 'triblersoft@gmail.com'

from types import StringType
from sha import sha
from time import time, clock
from string import strip
import socket
import sys
try:
    from os import getpid
except ImportError:
    def getpid():
        return 1
import Overlay.permid as permid
import CacheDB.cachedb as cachedb
import CacheDB.superpeer as superpeer
from base64 import decodestring 
import CacheDB.friends as friends
    
mapbase64 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-'

## Global initialization

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


class GLOBAL:
    do_cache = 1
    do_overlay = 1
    do_buddycast = 1
    do_download_help = 1
    do_superpeer = 0
    do_das_test = 0
    do_buddycast_interval = 15
    
myinfo = {}

def is_valid_ip(ip):
    invalid_iphead = ['0.', '127.0.0.1']
    for iphead in invalid_iphead:
        if ip.startswith(iphead):
            return False
    return True

def load_myinfo(myinfo):    # TODO: load more personal infomation
    my_permid = str(permid._ec_keypair.pub().get_der())
    name = socket.gethostname()
    host = socket.gethostbyname_ex(name)
    ipaddrlist = host[2]
    valid_ip = ''
    for ip in ipaddrlist:
        if is_valid_ip(ip):
            valid_ip = ip
            break
    myinfo['permid'] = my_permid
    myinfo['ip'] = valid_ip
    myinfo['name'] = name

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

def createPeerID(ins = '---'):
    assert type(ins) is StringType
    assert len(ins) == 3
    return _idprefix + ins + _idrandom[0]


def tribler_init(config_dir = None):
    global myinfo
    resetPeerIDs()
    permid.init(config_dir)
    load_myinfo(myinfo)
    cachedb.init(config_dir,myinfo)
    superpeer.init()
    friends.init(config_dir)

def tribler_done(config_dir = None):
    friends.done(config_dir)