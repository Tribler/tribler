# Written by Arno Bakker, Bram Cohen
# see LICENSE.txt for license information

__fool_epydoc = 481
"""
uTorrent Peer Exchange (PEX) Support:
-------------------------------------
As documented in
    https://trac.transmissionbt.com/browser/trunk/extras/extended-messaging.txt
    BitTorrent-5.0.8/BitTorrent/Connector.py
    (link no longer available) http://transmission.m0k.org/trac/browser/trunk/misc/utorrent.txt

The PEX message payload is a bencoded dict with three keys:
 'added': the set of peers met since the last PEX
 'added.f': a flag for every peer, apparently with the following values:
    \x00: unknown, assuming default
    \x01: Prefers encryption (as suggested by LH-ABC-3.2.0/BitTorrent/BT1/Connector.py)
    \x02: Is seeder (as suggested by BitTorrent-5.0.8/BitTorrent/Connector.py)
  OR-ing them together is allowed as I've seen \x03 values.
 'dropped': the set of peers dropped since last PEX

03/09/09 Boudewijn: Added a 'is same kind of peer as me' bit to the
'added.f' value. When a Tribler peer send this bit as True this means
'is also a Tribler peer'.
    \x04: is same kind of peer

The mechanism is insecure because there is no way to know if the peer addresses
are really of some peers that are running BitTorrent, or just DoS victims.
For peer addresses that come from trackers we at least know that the peer host
ran BitTorrent and was downloading this swarm (assuming the tracker is trustworthy).

"""
import sys
import logging
from types import DictType, StringType
from Tribler.Core.Utilities.bencode import bencode

EXTEND_MSG_UTORRENT_PEX_ID = chr(1)  # Can be any value, the name 'ut_pex' is standardized
EXTEND_MSG_UTORRENT_PEX = 'ut_pex'  # note case sensitive

logger = logging.getLogger(__name__)


def create_ut_pex(addedconns, droppedconns, thisconn):
    # print >>sys.stderr,"ut_pex: create_ut_pex:",addedconns,droppedconns,thisconn

    # Niels: Force max 50 added/dropped connections
    # "Some clients may choose to enforce these limits and drop connections which don't obey these limits."
    # http://wiki.theory.org/BitTorrentPeerExchangeConventions
    addedconns = addedconns[:50]
    droppedconns = droppedconns[:50]

    d = {}
    compactedpeerstr = compact_connections(addedconns, thisconn)
    d['added'] = compactedpeerstr
    flags = ''
    for i in range(len(addedconns)):
        conn = addedconns[i]
        if conn == thisconn:
            continue
        flag = 0
        if conn.get_extend_encryption():
            flag |= 1
        if conn.download is not None and conn.download.peer_is_complete():
            flag |= 2
        if conn.is_tribler_peer():
            flag |= 4

        # print >>sys.stderr,"ut_pex: create_ut_pex: add flag",`flag`
        flags += chr(flag)
    d['added.f'] = flags
    compactedpeerstr = compact_connections(droppedconns)
    d['dropped'] = compactedpeerstr
    return bencode(d)


def check_ut_pex(d):
    if not isinstance(d, DictType):
        raise ValueError('ut_pex: not a dict')

    # 'same' peers are peers that indicate (with a bit) that the peer
    # in apeers is the same client type as itself. So if the sender of
    # the pex message is a Tribler peer the same_apeers will also be
    # tribler peers
    same_apeers = []

    apeers = check_ut_pex_peerlist(d, 'added')
    dpeers = check_ut_pex_peerlist(d, 'dropped')
    if 'added.f' in d:
        addedf = d['added.f']
        if not isinstance(addedf, StringType):
            raise ValueError('ut_pex: added.f: not string')
        if len(addedf) != len(apeers) and not len(addedf) == 0:
            # KTorrent sends an empty added.f, be nice
            raise ValueError('ut_pex: added.f: more flags than peers')

        # we need all flags to be integers
        addedf = map(ord, addedf)

        # filter out all 'same' peers. the loop runs in reverse order
        # so the indexes don't change as we pop them from the apeers
        # list
        for i in range(min(len(apeers), len(addedf)) - 1, -1, -1):
            if addedf[i] & 4:
                same_apeers.append(apeers.pop(i))

                # for completeness we should also pop the item from
                # addedf even though we don't use it anymore
                addedf.pop(i)

    # Arno, 2008-09-12: Be liberal in what we receive
    # else:
        # raise ValueError('ut_pex: added.f: missing')

    logger.debug("ut_pex: Got %s" % repr(apeers))

    return (same_apeers, apeers, dpeers)


def check_ut_pex_peerlist(d, name):
    if name not in d:
        # Arno, 2008-09-12: Be liberal in what we receive, some clients
        # leave out 'dropped' key
        # raise ValueError('ut_pex:'+name+': missing')
        return []
    peerlist = d[name]
    if not isinstance(peerlist, StringType):
        raise ValueError('ut_pex:' + name + ': not string')
    if len(peerlist) % 6 != 0:
        raise ValueError('ut_pex:' + name + ': not multiple of 6 bytes')
    peers = decompact_connections(peerlist)
    for ip, port in peers:
        if ip == '127.0.0.1':
            raise ValueError('ut_pex:' + name + ': address is localhost')
    return peers


def ut_pex_get_conns_diff(currconns, prevconns):
    addedconns = []
    droppedconns = []
    for conn in currconns:
        if not (conn in prevconns):
            # new conn
            addedconns.append(conn)
    for conn in prevconns:
        if not (conn in currconns):
            # old conn, was dropped
            droppedconns.append(conn)
    return (addedconns, droppedconns)


def compact_connections(conns, thisconn=None):
    """ See BitTornado/BT1/track.py """
    compactpeers = []
    for conn in conns:
        if conn == thisconn:
            continue
        ip = conn.get_ip()
        port = conn.get_extend_listenport()
        if port is None:
            raise ValueError("ut_pex: compact: listen port unknown?!")
        else:
            compactpeer = compact_peer_info(ip, port)
            compactpeers.append(compactpeer)

    # Create compact representation of peers
    compactpeerstr = ''.join(compactpeers)
    return compactpeerstr


def compact_peer_info(ip, port):
    try:
        s = (''.join([chr(int(i)) for i in ip.split('.')])
             + chr((port & 0xFF00) >> 8) + chr(port & 0xFF))
        if len(s) != 6:
            raise ValueError
    except:
        s = ''  # not a valid IP, must be a domain name
    return s


def decompact_connections(p):
    """ See BitTornado/BT1/Rerequester.py """
    peers = []
    for x in xrange(0, len(p), 6):
        ip = '.'.join([str(ord(i)) for i in p[x:x + 4]])
        port = (ord(p[x + 4]) << 8) | ord(p[x + 5])
        peers.append((ip, port))
    return peers
