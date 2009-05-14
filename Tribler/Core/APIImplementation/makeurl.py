# Written by Arno Bakker
# see LICENSE.txt for license information
#
# TODO: 
# * Test suite
#
# ISSUE: what if trackers have query parts? Is that officially/practically allowed?


import sys
import urlparse
import urllib  
from types import IntType, LongType
from struct import pack, unpack
from base64 import b64encode, b64decode

from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.Crypto import sha


DEBUG = False


def metainfo2p2purl(metainfo):
    """ metainfo must be a Merkle torrent or a live torrent with an
    'encoding' field set. """
    
    info = metainfo['info']
    
    bitrate = None
    if 'azureus_properties' in metainfo:
        azprops = metainfo['azureus_properties']
        if 'Content' in azprops:
            content = metainfo['azureus_properties']['Content']
            if 'Speed Bps' in content:
                bitrate = content['Speed Bps']
                                                
    urldict = {}

    urldict['s'] = p2purl_encode_nnumber(info['piece length'])
    urldict['n'] = p2purl_encode_name2url(info['name'],metainfo['encoding'])
    if info.has_key('length'):
        urldict['l'] = p2purl_encode_nnumber(info['length'])
    else:
        raise ValueError("Multi-file torrents currently not supported")
        #list = []
        #for filedict in info['files']:
        #    newdict = {}
        #    newdict['p'] = list_filename_escape(filedict['path'])
        #    newdict['l'] = p2purl_encode_nnumber(filedict['length'])
        #    list.append(newdict)
        #urldict['f'] = '' # TODO bencode(list)
    if info.has_key('root hash'):
        urldict['r'] = b64urlencode(info['root hash'])
    elif info.has_key('live'):
        urldict['k'] = b64urlencode(info['live']['pubkey'])
        urldict['a'] = info['live']['authmethod']
    else:
        return None
        
    if bitrate is not None:
        urldict['b'] = p2purl_encode_nnumber(bitrate)
        
    query = ''
    for k in ['n','r','k','l','s','a','b']:
        if k in urldict:
            if query != "":
                query += '&'
            v = urldict[k]
            if k == 'n': 
                s = v
            else:
                s = k+"="+v
            query += s
        
    sidx = metainfo['announce'].find(":")
    hierpart = metainfo['announce'][sidx+1:]
    url = P2PURL_SCHEME+':'+hierpart+"?"+query
    return url



def p2purl2metainfo(url):
    """ Returns (metainfo,swarmid) """
    
    print >>sys.stderr,"p2purl2metainfo: URL",url
    # Python's urlparse only supports a defined set of schemes, if not
    # recognized, everything becomes path. Handy.
    
    colidx = url.find(":")
    scheme = url[0:colidx]
    qidx = url.find("?")
    if qidx == -1:
        # Compact form, no authority part and path rootless
        authority = None
        path = None
        query = url[colidx+1:]
        fragment = None
    else:
        # Long form, with authority
        authoritypath = url[colidx+3:qidx]
        pidx = authoritypath.find("/")
        authority = authoritypath[0:pidx]
        path = authoritypath[pidx:]
        fidx = url.find("#")
        if fidx == -1:
            # No fragment
            query = url[qidx+1:]
            fragment = None
        else:
            query = url[qidx+1:fidx]
            fragment = url[fidx:]
    
    if scheme != P2PURL_SCHEME:
        raise ValueError("Unknown scheme "+P2PURL_SCHEME)

    metainfo = {}
    if authority and path:
        metainfo['announce'] = 'http://'+authority+path
    reqinfo = p2purl_parse_query(query)
    metainfo.update(reqinfo)
    
    if 'live' in metainfo['info']:
        swarmid = pubkey2swarmid(metainfo['info']['live'])
    else:
        swarmid = metainfo['info']['root hash']

    if DEBUG:
        print >>sys.stderr,"p2purl2metainfo: parsed",`metainfo.keys()`

    
    return (metainfo,swarmid)

def p2purl_parse_query(query):
    print >>sys.stderr,"p2purl_parse_query: query",query
    
    reqinfo = {}
    reqinfo['info'] = {}
    
    kvs = query.split('&')
    for kv in kvs:
        if '=' not in kv:
            # Must be name
            reqinfo['info']['name'] = p2purl_decode_name2utf8(kv)
            reqinfo['encoding'] = 'UTF-8'
            continue
        
        k,v = kv.split('=')
        
        if k =='k' or k == 'a' and not ('live' in reqinfo['info']):
            reqinfo['info']['live'] = {}
        
        if k == 'n':
            reqinfo['info']['name'] = p2purl_decode_name2utf8(v)
            reqinfo['encoding'] = 'UTF-8'
        elif k == 'r':
            reqinfo['info']['root hash'] = p2purl_decode_base64url(v)
        elif k == 'k':
            reqinfo['info']['live']['pubkey'] = p2purl_decode_base64url(v)
            # reqinfo['info']['live']['authmethod'] = pubkey2authmethod(reqinfo['info']['live']['pubkey'])
        elif k == 'l':
            reqinfo['info']['length'] = p2purl_decode_nnumber(v)
        elif k == 's':
            reqinfo['info']['piece length'] = p2purl_decode_nnumber(v)
        elif k == 'a':
            reqinfo['info']['live']['authmethod'] = v
        elif k == 'b':
            bitrate = p2purl_decode_nnumber(v)
            reqinfo['azureus_properties'] = {}
            reqinfo['azureus_properties']['Content'] = {}
            reqinfo['azureus_properties']['Content']['Speed Bps'] = bitrate
            
    return reqinfo
            

def pubkey2swarmid(livedict):
    """ Calculate SHA1 of pubkey (or cert). 
    Make X.509 Subject Key Identifier compatible? """
    
    print >>sys.stderr,"pubkey2swarmid:",livedict.keys()
    
    return sha(livedict['pubkey']).digest()


def p2purl_decode_name2utf8(v):
    """ URL decode name to UTF-8 encoding """
    return urllib.unquote(v)

def p2purl_encode_name2url(name,encoding):
    """ Encode name in specified encoding to URL escaped UTF-8 """
    uname = unicode(name, encoding)
    utf8name = uname.encode('utf-8')
    return urllib.quote(utf8name)



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
    format = "!"+format # network-byte order       
    return unpack(format,b)[0]

def p2purl_encode_nnumber(s):
    if type(s) == IntType:
        if s < 2 ** 16:
           format = "H"
        elif s < 2 ** 32:
           format = "l"
    else:
        format = "Q"
    format = "!"+format # network-byte order
    return b64urlencode(pack(format,s))

#
# "Modified BASE64 for URL" as informally specified in
# http://en.wikipedia.org/wiki/Base64#URL_applications
#
def b64urlencode(input):
    output = b64encode(input)
    output = output.rstrip('=')
    output = output.replace('+','-')
    output = output.replace('/','_')
    return output
    
def b64urldecode(input):
    inter = input[:]
    # readd padding.
    padlen = 4 - (len(inter) - ((len(inter) / 4) * 4))
    padstr = '=' * padlen
    inter += padstr
    inter = inter.replace('-','+')
    inter = inter.replace('_','/')
    output = b64decode(inter)
    return output

