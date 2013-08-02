# Written by Arno Bakker
# see LICENSE.txt for license information
#
# TODO:
# * Test suite
# * Tracker support: how do they determine which files to seed.
#
# * Reverse support for URL-compat: URLs that do use infohash.
#   - Make sure internal tracker understands URL-compat torrentfiles
#   - Make sure internal tracker understands P2P URLs
#
# ISSUE: what if trackers have query parts? Is that officially/practically allowed?


import sys
import urlparse
import urllib
import math
if sys.platform != "win32":
    import curses.ascii
from types import IntType, LongType
from struct import pack, unpack
from base64 import b64encode, b64decode
from M2Crypto import Rand  # TODO REMOVE FOR LICHT
from traceback import print_exc, print_stack

from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.Crypto import sha


DEBUG = False


def metainfo2p2purl(metainfo):
    """ metainfo must be a Merkle torrent or a live torrent with an
    'encoding' field set.
    @return URL
    """
    info = metainfo['info']

    bitrate = None
    if 'azureus_properties' in metainfo:
        azprops = metainfo['azureus_properties']
        if 'Content' in azprops:
            content = metainfo['azureus_properties']['Content']
            if 'Speed Bps' in content:
                bitrate = content['Speed Bps']

    if 'encoding' not in metainfo:
        encoding = 'utf-8'
    else:
        encoding = metainfo['encoding']

    urldict = {}

    urldict['s'] = p2purl_encode_piecelength(info['piece length'])
    # Warning: mbcs encodings sometimes don't work well under python!
    urldict['n'] = p2purl_encode_name2url(info['name'], encoding)

    if 'length' in info:
        urldict['l'] = p2purl_encode_nnumber(info['length'])
    else:
        raise ValueError("Multi-file torrents currently not supported")
        # list = []
        # for filedict in info['files']:
        #    newdict = {}
        #    newdict['p'] = list_filename_escape(filedict['path'])
        #    newdict['l'] = p2purl_encode_nnumber(filedict['length'])
        #    list.append(newdict)
        # urldict['f'] = '' # TODO bencode(list)
    if 'root hash' in info:
        urldict['r'] = b64urlencode(info['root hash'])
    elif 'live' in info:
        urldict['k'] = b64urlencode(info['live']['pubkey'])
        urldict['a'] = info['live']['authmethod']
    else:
        raise ValueError("url-compat and Merkle torrent must be on to create URL")

    if bitrate is not None:
        urldict['b'] = p2purl_encode_nnumber(bitrate)

    query = ''
    for k in ['n', 'r', 'k', 'l', 's', 'a', 'b']:
        if k in urldict:
            if query != "":
                query += '&'
            v = urldict[k]
            if k == 'n':
                s = v
            else:
                s = k + "=" +v
            query += s

    sidx = metainfo['announce'].find(":")
    hierpart = metainfo['announce'][sidx + 1:]
    url = P2PURL_SCHEME + ':' +hierpart+"?"+query
    return url


def p2purl2metainfo(url):
    """ Returns (metainfo,swarmid) """

    if DEBUG:
        print >>sys.stderr, "p2purl2metainfo: URL", url

    # Python's urlparse only supports a defined set of schemes, if not
    # recognized, everything becomes path. Handy.
    colidx = url.find(":")
    scheme = url[0:colidx]
    qidx = url.find("?")

    if scheme != P2PURL_SCHEME:
        raise ValueError("Unknown scheme " + P2PURL_SCHEME)

    if qidx == -1:
        if url[2:].find('/') > -1:
            raise ValueError("Malformed compact form URL")
        # Compact form, no authority part and path rootless
        authority = None
        path = None
        query = url[colidx + 1:]
        fragment = None
    else:
        # Long form, with authority
        authoritypath = url[colidx + 3:qidx]
        pidx = authoritypath.find("/")
        authority = authoritypath[0:pidx]
        path = authoritypath[pidx:]
        fidx = url.find("#")
        if fidx == -1:
            # No fragment
            query = url[qidx + 1:]
            fragment = None
        else:
            query = url[qidx + 1:fidx]
            fragment = url[fidx:]

        # Check port no.
        csbidx = authority.find("]")
        if authority.startswith("[") and csbidx != -1:
            # Literal IPv6 address
            if csbidx == len(authority) - 1:
                port = None
            else:
                port = authority[csbidx + 1:]
        else:
            cidx = authority.find(":")
            if cidx != -1:
                port = authority[cidx + 1:]
            else:
                port = None
        if port is not None and not port.isdigit():
            raise ValueError("Port not int")

    metainfo = {}
    if authority and path:
        metainfo['announce'] = 'http://' + authority +path
        # Check for malformedness
        result = urlparse.urlparse(metainfo['announce'])
        if result[0] != "http":
            raise ValueError("Malformed tracker URL")

    reqinfo = p2purl_parse_query(query)
    metainfo.update(reqinfo)

    swarmid = metainfo2swarmid(metainfo)

    if DEBUG:
        print >>sys.stderr, "p2purl2metainfo: parsed", repr(metainfo)

    return (metainfo, swarmid)


def metainfo2swarmid(metainfo):
    if 'live' in metainfo['info']:
        swarmid = pubkey2swarmid(metainfo['info']['live'])
    else:
        swarmid = metainfo['info']['root hash']
    return swarmid


def p2purl_parse_query(query):
    if DEBUG:
        print >>sys.stderr, "p2purl_parse_query: query", query

    gotname = False
    gotkey = False
    gotrh = False
    gotlen = False
    gotps = False
    gotam = False
    gotbps = False

    reqinfo = {}
    reqinfo['info'] = {}

    # Hmmm... could have used urlparse.parse_qs
    kvs = query.split('&')
    for kv in kvs:
        if '=' not in kv:
            # Must be name
            reqinfo['info']['name'] = p2purl_decode_name2utf8(kv)
            reqinfo['encoding'] = 'UTF-8'
            gotname = True
            continue

        k, v = kv.split('=')

        if k == 'k' or k == 'a' and not ('live' in reqinfo['info']):
            reqinfo['info']['live'] = {}

        if k == 'n':
            reqinfo['info']['name'] = p2purl_decode_name2utf8(v)
            reqinfo['encoding'] = 'UTF-8'
            gotname = True
        elif k == 'r':
            reqinfo['info']['root hash'] = p2purl_decode_base64url(v)
            gotrh = True
        elif k == 'k':
            reqinfo['info']['live']['pubkey'] = p2purl_decode_base64url(v)
            # reqinfo['info']['live']['authmethod'] = pubkey2authmethod(reqinfo['info']['live']['pubkey'])
            gotkey = True
        elif k == 'l':
            reqinfo['info']['length'] = p2purl_decode_nnumber(v)
            gotlen = True
        elif k == 's':
            reqinfo['info']['piece length'] = p2purl_decode_piecelength(v)
            gotps = True
        elif k == 'a':
            reqinfo['info']['live']['authmethod'] = v
            gotam = True
        elif k == 'b':
            bitrate = p2purl_decode_nnumber(v)
            reqinfo['azureus_properties'] = {}
            reqinfo['azureus_properties']['Content'] = {}
            reqinfo['azureus_properties']['Content']['Speed Bps'] = bitrate
            gotbps = True

    if not gotname:
        raise ValueError("Missing name field")
    if not gotrh and not gotkey:
        raise ValueError("Missing root hash or live pub key field")
    if gotrh and gotkey:
        raise ValueError("Found both root hash and live pub key field")
    if not gotlen:
        raise ValueError("Missing length field")
    if not gotps:
        raise ValueError("Missing piece size field")
    if gotkey and not gotam:
        raise ValueError("Missing live authentication method field")
    if gotrh and gotam:
        raise ValueError("Inconsistent: root hash and live authentication method field")

    if not gotbps:
        raise ValueError("Missing bitrate field")

    return reqinfo


def pubkey2swarmid(livedict):
    """ Calculate SHA1 of pubkey (or cert).
    Make X.509 Subject Key Identifier compatible?
    """
    if DEBUG:
        print >>sys.stderr, "pubkey2swarmid:", livedict.keys()

    if livedict['authmethod'] == "None":
        # No live-source auth
        return Rand.rand_bytes(20)
    else:
        return sha(livedict['pubkey']).digest()


def p2purl_decode_name2utf8(v):
    """ URL decode name to UTF-8 encoding """
    if sys.platform != "win32":
        for c in v:
            if not curses.ascii.isascii(c):
                raise ValueError("Name contains unescaped 8-bit value " + repr(c))
    return urllib.unquote_plus(v)


def p2purl_encode_name2url(name, encoding):
    """ Encode name in specified encoding to URL escaped UTF-8 """

    if encoding.lower() == 'utf-8':
        utf8name = name
    else:
        uname = unicode(name, encoding)
        utf8name = uname.encode('utf-8')
    return urllib.quote_plus(utf8name)


def p2purl_decode_base64url(v):
    return b64urldecode(v)

#
# Convert Python number to binary value of sufficient bytes,
# in network-byte order and BASE64-URL encode that binary value, or vice versa.
#


def p2purl_decode_nnumber(s):
    b = b64urldecode(s)
    if len(b) == 2:
        format = "H"
    elif len(b) == 4:
        format = "l"
    else:
        format = "Q"
    format = "!" + format  # network-byte order
    return unpack(format, b)[0]


def p2purl_encode_nnumber(s):
    if isinstance(s, IntType):
        if s < 2 ** 16:
            format = "H"
        elif s < 2 ** 32:
            format = "l"
    else:
        format = "Q"
    format = "!" + format  # network-byte order
    return b64urlencode(pack(format, s))


#
# Convert Python power-of-two piecelength to text value, or vice versa.
#
def p2purl_decode_piecelength(s):
    return int(math.pow(2.0, float(s)))


def p2purl_encode_piecelength(s):
    return str(int(math.log(float(s), 2.0)))

#
# "Modified BASE64 for URL" as informally specified in
# http://en.wikipedia.org/wiki/Base64#URL_applications
#


def b64urlencode(input):
    output = b64encode(input)
    output = output.rstrip('=')
    output = output.replace('+', '-')
    output = output.replace('/', '_')
    return output


def b64urldecode(input):
    inter = input[:]
    # readd padding.
    padlen = 4 - (len(inter) - ((len(inter) / 4) * 4))
    padstr = '=' * padlen
    inter += padstr
    inter = inter.replace('-', '+')
    inter = inter.replace('_', '/')
    output = b64decode(inter)
    return output
