# Written by Bram Cohen
# see LICENSE.txt for license information

import sys
from types import UnicodeType, StringType, LongType, IntType, ListType, DictType
from re import compile

# reg = compile(r'^[^/\\.~][^/\\]*$')
# reg = compile(r'^[^/\\]*$')

ints = (LongType, IntType)


def check_info(info):
    if not isinstance(info, DictType):
        raise ValueError('bad metainfo - not a dictionary')

    if 'pieces' in info:
        pieces = info.get('pieces')
        if not isinstance(pieces, StringType) or len(pieces) % 20 != 0:
            raise ValueError('bad metainfo - bad pieces key')
    elif 'root hash' in info:
        # Merkle
        root_hash = info.get('root hash')
        if not isinstance(root_hash, StringType) or len(root_hash) != 20:
            raise ValueError('bad metainfo - bad root hash key')
    piecelength = info.get('piece length')
    if type(piecelength) not in ints or piecelength <= 0:
        raise ValueError('bad metainfo - illegal piece length')
    name = info.get('name')
    if StringType != type(name) != UnicodeType:
        raise ValueError('bad metainfo - bad name')
    # if not reg.match(name):
    #    raise ValueError, 'name %s disallowed for security reasons' % name
    if ('files' in info) == ('length' in info):
        raise ValueError('single/multiple file mix')
    if 'length' in info:
        length = info.get('length')
        if type(length) not in ints or length < 0:
            raise ValueError('bad metainfo - bad length')
    else:
        files = info.get('files')
        if not isinstance(files, ListType):
            raise ValueError
        for f in files:
            if not isinstance(f, DictType):
                raise ValueError('bad metainfo - bad file value')
            length = f.get('length')
            if type(length) not in ints or length < 0:
                raise ValueError('bad metainfo - bad length')
            path = f.get('path')
            if not isinstance(path, ListType) or path == []:
                raise ValueError('bad metainfo - bad path')
            for p in path:
                if StringType != type(p) != UnicodeType:
                    raise ValueError('bad metainfo - bad path dir')
                # if not reg.match(p):
                #    raise ValueError, 'path %s disallowed for security reasons' % p
        for i in xrange(len(files)):
            for j in xrange(i):
                if files[i]['path'] == files[j]['path']:
                    raise ValueError('bad metainfo - duplicate path %s' % files[j]['path'])


def check_message(message):
    if not isinstance(message, DictType):
        raise ValueError
    check_info(message.get('info'))
    if StringType != type(message.get('announce')) != UnicodeType:
        raise ValueError


def check_peers(message):
    if not isinstance(message, DictType):
        raise ValueError
    if 'failure reason' in message:
        if not isinstance(message['failure reason'], StringType):
            raise ValueError
        return
    peers = message.get('peers')
    if peers is not None:
        if isinstance(peers, ListType):
            for p in peers:
                if not isinstance(p, DictType):
                    raise ValueError
                if not isinstance(p.get('ip'), StringType):
                    raise ValueError
                port = p.get('port')
                if type(port) not in ints or p <= 0:
                    raise ValueError
                if 'peer id' in p:
                    id = p['peer id']
                    if not isinstance(id, StringType) or len(id) != 20:
                        raise ValueError
        elif not isinstance(peers, StringType) or len(peers) % 6 != 0:
            raise ValueError

    # IPv6 Tracker extension. http://www.bittorrent.org/beps/bep_0007.html
    peers6 = message.get('peers6')
    if peers6 is not None:
        if isinstance(peers6, ListType):
            for p in peers6:
                if not isinstance(p, DictType):
                    raise ValueError
                if not isinstance(p.get('ip'), StringType):
                    raise ValueError
                port = p.get('port')
                if type(port) not in ints or p <= 0:
                    raise ValueError
                if 'peer id' in p:
                    id = p['peer id']
                    if not isinstance(id, StringType) or len(id) != 20:
                        raise ValueError
        elif not isinstance(peers6, StringType) or len(peers6) % 18 != 0:
            raise ValueError

    interval = message.get('interval', 1)
    if type(interval) not in ints or interval <= 0:
        raise ValueError
    minint = message.get('min interval', 1)
    if type(minint) not in ints or minint <= 0:
        raise ValueError
    if not isinstance(message.get('tracker id', ''), StringType):
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
