# Written by Jie Yang, Arno Bakker
# see LICENSE.txt for license information

## Arno: FIXME _idprefix is also defined in BitTornado.__init__ and that's the one
## actually used in connections, so make sure they are defined in one place
## (here) and correct.
##

from BitTornado.__init__ import resetPeerIDs

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
from NATFirewall.guessip import get_my_wan_ip

## Global initialization

## Moved to BitTornado/download_bt1.py where all config is done
# class GLOBAL:

def load_myinfo():    # TODO: load more personal infomation
    myinfo = {}
    my_permid = str(permid._ec_keypair.pub().get_der())
    name = socket.gethostname()
    my_ip = get_my_ip(name)
    myinfo['permid'] = my_permid
    myinfo['ip'] = my_ip
    myinfo['name'] = name
    return myinfo

def get_my_ip(name):
    ip = get_my_wan_ip()
    if ip is None:
        host = socket.gethostbyname_ex(name)
        ipaddrlist = host[2]
        for ip in ipaddrlist:
            return ip
        return '127.0.0.1'
    else:
        return ip

def tribler_init(config_dir = None, install_dir = None, db_exception_handler = None):
    resetPeerIDs()
    permid.init(config_dir)
    myinfo = load_myinfo()
    # roee88 says we need to revert to encoded here for the databases
    cachedb.init(config_dir.encode(sys.getfilesystemencoding()),myinfo,db_exception_handler = db_exception_handler)
    superpeer.init(install_dir)
    friends.init(config_dir)
    category.init(install_dir, config_dir)
    print 'Reading configuration from: ', repr(config_dir)

def tribler_done(config_dir = None):
    friends.done(config_dir)
    cachedb.done(config_dir)
    
