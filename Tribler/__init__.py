# Written by Jie Yang, Arno Bakker
# see LICENSE.txt for license information

## Arno: FIXME _idprefix is also defined in BitTornado.__init__ and that's the one
## actually used in connections, so make sure they are defined in one place
## (here) and correct.
##

from BitTornado.__init__ import version_id, version_short, product_name, version, report_email

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
import Category.Category as category
import guessip    

mapbase64 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-'

## Global initialization

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

class GLOBAL:
    do_cache = 1
    do_overlay = 1
    do_buddycast = 1
    do_download_help = 1
    do_superpeer = 0
    do_das_test = 0
    do_buddycast_interval = 15
    do_torrent_collecting = 1
    do_torrent_checking = 1
    overlay_log = ''
    config_dir = '.'+product_name
    max_num_torrents = 5000
    torrent_checking_period = 60
    
myinfo = {}

def load_myinfo(myinfo):    # TODO: load more personal infomation
    my_permid = str(permid._ec_keypair.pub().get_der())
    name = socket.gethostname()
    my_ip = get_my_ip(name)
    myinfo['permid'] = my_permid
    myinfo['ip'] = my_ip
    myinfo['name'] = name

def get_my_ip(name):
    ip = guessip.get_my_wan_ip()
    if ip is None:
        host = socket.gethostbyname_ex(name)
        ipaddrlist = host[2]
        for ip in ipaddrlist:
            return ip
        return '127.0.0.1'
    else:
        return ip

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
    if type(ins) != StringType:
        raise Exception, "tribler__init__: createPeerID"
    if len(ins) != 3:
        raise Exception, "tribler__init__: createPeerID"
    return _idprefix + ins + _idrandom[0]


def tribler_init(config_dir = None, install_dir = None):
    global myinfo
    if config_dir:
        GLOBAL.config_dir = config_dir
    resetPeerIDs()
    permid.init(config_dir)
    load_myinfo(myinfo)
    # roee88 says we need to revert to encoded here for the databases
    cachedb.init(config_dir.encode(sys.getfilesystemencoding()),myinfo)
    superpeer.init(install_dir)
    friends.init(config_dir)
    category.init(install_dir)

def tribler_done(config_dir = None):
    friends.done(config_dir)
    cachedb.done(config_dir)
    
