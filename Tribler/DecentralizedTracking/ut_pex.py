# Written by Arno Bakker, Bram Cohen
# see LICENSE.txt for license information
"""
uTorrent Peer Exchange (PEX) Support:
-------------------------------------
As documented in
    http://transmission.m0k.org/trac/browser/trunk/misc/utorrent.txt
    BitTorrent-5.0.8/BitTorrent/Connector.py
    
The PEX message payload is a bencoded dict with three keys:
 'added': the set of peers met since the last PEX
 'added.f': a flag for every peer, apparently with the following values:
    \x00: unknown
    \x01: Prefers encryption (as suggested by LH-ABC-3.2.0/BitTorrent/BT1/Connector.py)
    \x02: Is seeder (as suggested by BitTorrent-5.0.8/BitTorrent/Connector.py)
  OR-ing them together is allowed as I've seen 0x03 values.
 'dropped': the set of peers dropped since last PEX

The mechanism is insecure because there is no way to know if the peer addresses
are really of some peers that are running BitTorrent, or just DoS victims.
For peer addresses that come from trackers we at least know that the peer host
ran BitTorrent and was downloading this swarm (assuming the tracker is trustworthy).

"""
from BitTornado.BT1.track import compact_peer_info

EXTEND_MSG_UTORRENT_PEX_ID = chr(1) # Can be any value, the name 'ut_pex' is standardized
EXTEND_MSG_UTORRENT_PEX = 'ut_pex' # note case sensitive


def create_ut_pex(addedconns,droppedconns):
    d = {}
    (newadded,compactedpeerstr) = self.compact_connections(addedconns)
    d['added'] = compactedpeerstr
    flags = '\x00' * len(newadded)
    for i in range(len(newadded)):
        conn = newadded[i]
        if conn.get_extend_encryption():
            flags[i] = chr(ord(flags[i]) | 1)
        if conn.download is not None and conn.download.peer_is_complete():
            flags[i] = chr(ord(flags[i]) | 2)
    (newremoved,compactedpeerstr) = self.compact_connections(droppedconns)
    d['dropped'] = compactedpeerstr
    return d

def check_ut_pex(d):
    if type(d) != DictType:
        raise ValueError('ut_pex: not a dict')
    check_ut_pex_peerlist(d,'added')
    check_ut_pex_peerlist(d,'dropped')
    if 'added.f' not in d:
        raise ValueError('ut_pex: added.f: missing')
    addedf = d['added.f']
    if len(addedf) != len(d['added']):
        raise ValueError('ut_pex: added.f: more flags than peers')
    
def check_ut_pex_peerlist(d,name):
    if name not in d:
        raise ValueError('ut_pex:'+name+': missing')
    peerlist = d[name]
    if type(peerlist) != StringType:
        raise ValueError('ut_pex:'+name+': not string')
    if len(peerlist) % 6 != 0:
        raise ValueError('ut_pex:'+name+': not multiple of 6 bytes')
    


def compact_connections(conns):
    """ See BitTornado/BT1/track.py """
    compactpeers = []
    deletedconns = []
    for conn in conns:
        ip = conn.get_ip()
        port = conn.get_extend_listenport()
        if port is None:
            # peer didn't send it in EXTEND message
            deletedconns.append(conn)
        else:
            compactpeer = compact_peer_info(ip,port)
            compactpeers.append(compactpeer)
    # Remove connections for which we had incomplete info
    newconns = conns[:]
    for conn in deletedconns:
        del newconns[conn]
        
    # Create compact representation of peers
    compactpeerstr = ''.join(compactpeers)
    return (newconns,compactpeerstr)


def decompact_connections(p):
    """ See BitTornado/BT1/Rerequester.py """
    peers = []
    for x in xrange(0, len(p), 6):
        ip = '.'.join([str(ord(i)) for i in p[x:x+4]])
        port = (ord(p[x+4]) << 8) | ord(p[x+5])
        peers.append((ip, port))
    return peers
