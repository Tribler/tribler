# Written by Bram Cohen
# see LICENSE.txt for license information

from types import StringType, LongType, IntType, ListType, DictType
from re import compile

reg = compile(r'^[^/\\.~][^/\\]*$')

ints = (LongType, IntType)

def check_info(info):
    if type(info) != DictType:
        raise ValueError, 'bad metainfo - not a dictionary'
    pieces = info.get('pieces')
    if type(pieces) != StringType or len(pieces) % 20 != 0:
        raise ValueError, 'bad metainfo - bad pieces key'
    piecelength = info.get('piece length')
    if type(piecelength) not in ints or piecelength <= 0:
        raise ValueError, 'bad metainfo - illegal piece length'
    name = info.get('name')
    if type(name) != StringType:
        raise ValueError, 'bad metainfo - bad name'
    if not reg.match(name):
        raise ValueError, 'name %s disallowed for security reasons' % name
    if info.has_key('files') == info.has_key('length'):
        raise ValueError, 'single/multiple file mix'
    if info.has_key('length'):
        length = info.get('length')
        if type(length) not in ints or length < 0:
            raise ValueError, 'bad metainfo - bad length'
    else:
        files = info.get('files')
        if type(files) != ListType:
            raise ValueError
        for f in files:
            if type(f) != DictType:
                raise ValueError, 'bad metainfo - bad file value'
            length = f.get('length')
            if type(length) not in ints or length < 0:
                raise ValueError, 'bad metainfo - bad length'
            path = f.get('path')
            if type(path) != ListType or path == []:
                raise ValueError, 'bad metainfo - bad path'
            for p in path:
                if type(p) != StringType:
                    raise ValueError, 'bad metainfo - bad path dir'
                if not reg.match(p):
                    raise ValueError, 'path %s disallowed for security reasons' % p
        for i in xrange(len(files)):
            for j in xrange(i):
                if files[i]['path'] == files[j]['path']:
                    raise ValueError, 'bad metainfo - duplicate path'

def check_message(message):
    if type(message) != DictType:
        raise ValueError
    check_info(message.get('info'))
    if type(message.get('announce')) != StringType:
        raise ValueError

def check_peers(message):
    if type(message) != DictType:
        raise ValueError
    if message.has_key('failure reason'):
        if type(message['failure reason']) != StringType:
            raise ValueError
        return
    peers = message.get('peers')
    if type(peers) == ListType:
        for p in peers:
            if type(p) != DictType:
                raise ValueError
            if type(p.get('ip')) != StringType:
                raise ValueError
            port = p.get('port')
            if type(port) not in ints or p <= 0:
                raise ValueError
            if p.has_key('peer id'):
                id = p['peer id']
                if type(id) != StringType or len(id) != 20:
                    raise ValueError
    elif type(peers) != StringType or len(peers) % 6 != 0:
        raise ValueError
    interval = message.get('interval', 1)
    if type(interval) not in ints or interval <= 0:
        raise ValueError
    minint = message.get('min interval', 1)
    if type(minint) not in ints or minint <= 0:
        raise ValueError
    if type(message.get('tracker id', '')) != StringType:
        raise ValueError
    npeers = message.get('num peers', 0)
    if type(npeers) not in ints or npeers < 0:
        raise ValueError
    dpeers = message.get('done peers', 0)
    if type(dpeers) not in ints or dpeers < 0:
        raise ValueError
    last = message.get('last', 0)
    if type(last) not in ints or last < 0:
        raise ValueError
