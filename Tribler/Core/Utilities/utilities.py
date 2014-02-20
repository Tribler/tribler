# Written by Jie Yang
# see LICENSE.txt for license information

import socket
from time import time, strftime, gmtime
from base64 import encodestring, decodestring, b32decode
from Tribler.Core.Utilities.Crypto import sha
import sys
import os
import copy
from types import StringType, LongType, IntType, ListType, DictType
import urlparse
from traceback import print_exc
from urlparse import urlsplit, parse_qsl
import binascii
import logging

logger = logging.getLogger(__name__)

STRICT_CHECK = True

infohash_len = 20


def bin2str(bin):
    # Full BASE64-encoded
    return encodestring(bin).replace("\n", "")


def str2bin(str):
    return decodestring(str)


def validName(name):
    if not isinstance(name, str) and len(name) == 0:
        raise RuntimeError("invalid name: " + name)
    return True


def validPort(port):
    port = int(port)
    if port < 0 or port > 65535:
        raise RuntimeError("invalid Port: " + str(port))
    return True


def validIP(ip):
    try:
        try:
            # Is IPv4 addr?
            socket.inet_aton(ip)
            return True
        except socket.error:
            # Is hostname / IPv6?
            socket.getaddrinfo(ip, None)
            return True
    except:
        print_exc()
    raise RuntimeError("invalid IP address: " + ip)


def validPermid(permid):
    if not isinstance(permid, str):
        raise RuntimeError("invalid permid: " + permid)
    # Arno,2010-02-17: permid is ASN.1 encoded data that is NOT fixed length
    return True


def validInfohash(infohash):
    if not isinstance(infohash, str):
        raise RuntimeError("invalid infohash " + infohash)
    if STRICT_CHECK and len(infohash) != infohash_len:
        raise RuntimeError("invalid length infohash " + infohash)
    return True


def isValidPermid(permid):
    try:
        return validPermid(permid)
    except:
        return False


def isValidInfohash(infohash):
    try:
        return validInfohash(infohash)
    except:
        return False


def isValidPort(port):
    try:
        return validPort(port)
    except:
        return False


def isValidIP(ip):
    try:
        return validIP(ip)
    except:
        return False


def isValidName(name):
    try:
        return validPort(name)
    except:
        return False

def isInteger(str_integer):
    try:
        int(str_integer)
        return True
    except:
        return False

def validTorrentFile(metainfo):
    # Jie: is this function too strict? Many torrents could not be downloaded
    if not isinstance(metainfo, DictType):
        raise ValueError('metainfo not dict')

    if 'info' not in metainfo:
        raise ValueError('metainfo misses key info')

    if 'announce' in metainfo and not isValidURL(metainfo['announce']):
        # Niels: Some .torrent files have a dht:// url in the announce field.
        if not metainfo['announce'].startswith('dht:'):
            raise ValueError('announce URL bad')

    # http://www.bittorrent.org/DHT_protocol.html says both announce and nodes
    # are not allowed, but some torrents (Azureus?) apparently violate this.

    # if 'announce' in metainfo and 'nodes' in metainfo:
    #    raise ValueError('both announce and nodes present')

    if 'nodes' in metainfo:
        nodes = metainfo['nodes']
        if not isinstance(nodes, ListType):
            raise ValueError('nodes not list, but ' + repr(type(nodes)))
        for pair in nodes:
            if not isinstance(pair, ListType) and len(pair) != 2:
                raise ValueError('node not 2-item list, but ' + repr(type(pair)))
            host, port = pair
            if not isinstance(host, StringType):
                raise ValueError('node host not string, but ' + repr(type(host)))
            if not isinstance(port, IntType):
                raise ValueError('node port not int, but ' + repr(type(port)))

    if not ('announce' in metainfo or 'nodes' in metainfo):
        # Niels: 07/06/2012, disabling this check, modifying metainfo to allow for ill-formatted torrents
        metainfo['nodes'] = []
        # raise ValueError('announce and nodes missing')

    # 04/05/10 boudewijn: with the introduction of magnet links we
    # also allow for peer addresses to be (temporarily) stored in the
    # metadata.  Typically these addresses are recently gathered.
    if "initial peers" in metainfo:
        if not isinstance(metainfo["initial peers"], list):
            raise ValueError("initial peers not list, but %s" % type(metainfo["initial peers"]))
        for address in metainfo["initial peers"]:
            if not (isinstance(address, tuple) and len(address) == 2):
                raise ValueError("address not 2-item tuple, but %s" % type(address))
            if not isinstance(address[0], str):
                raise ValueError("address host not string, but %s" % type(address[0]))
            if not isinstance(address[1], int):
                raise ValueError("address port not int, but %s" % type(address[1]))

    info = metainfo['info']
    if not isinstance(info, DictType):
        raise ValueError('info not dict')

    if 'root hash' in info:
        infokeys = ['name', 'piece length', 'root hash']
    elif 'live' in info:
        infokeys = ['name', 'piece length', 'live']
    else:
        infokeys = ['name', 'piece length', 'pieces']
    for key in infokeys:
        if key not in info:
            raise ValueError('info misses key ' + key)
    name = info['name']
    if not isinstance(name, StringType):
        raise ValueError('info name is not string but ' + repr(type(name)))
    pl = info['piece length']
    if not isinstance(pl, IntType) and not isinstance(pl, LongType):
        raise ValueError('info piece size is not int, but ' + repr(type(pl)))
    if 'root hash' in info:
        rh = info['root hash']
        if not isinstance(rh, StringType) or len(rh) != 20:
            raise ValueError('info roothash is not 20-byte string')
    elif 'live' in info:
        live = info['live']
        if not isinstance(live, DictType):
            raise ValueError('info live is not a dict')
        else:
            if 'authmethod' not in live:
                raise ValueError('info live misses key' + 'authmethod')
    else:
        p = info['pieces']
        if not isinstance(p, StringType) or len(p) % 20 != 0:
            raise ValueError('info pieces is not multiple of 20 bytes')

    if 'length' in info:
        # single-file torrent
        if 'files' in info:
            raise ValueError('info may not contain both files and length key')

        l = info['length']
        if not isinstance(l, IntType) and not isinstance(l, LongType):
            raise ValueError('info length is not int, but ' + repr(type(l)))
    else:
        # multi-file torrent
        if 'length' in info:
            raise ValueError('info may not contain both files and length key')

        files = info['files']
        if not isinstance(files, ListType):
            raise ValueError('info files not list, but ' + repr(type(files)))

        filekeys = ['path', 'length']
        for file in files:
            for key in filekeys:
                if key not in file:
                    raise ValueError('info files missing path or length key')

            p = file['path']
            if not isinstance(p, ListType):
                raise ValueError('info files path is not list, but ' + repr(type(p)))
            for dir in p:
                if not isinstance(dir, StringType):
                    raise ValueError('info files path is not string, but ' + repr(type(dir)))

            l = file['length']
            if not isinstance(l, IntType) and not isinstance(l, LongType):
                raise ValueError('info files length is not int, but ' + repr(type(l)))

    # common additional fields
    if 'announce-list' in metainfo:
        al = metainfo['announce-list']
        if not isinstance(al, ListType):
            raise ValueError('announce-list is not list, but ' + repr(type(al)))
        for tier in al:
            if not isinstance(tier, ListType):
                raise ValueError('announce-list tier is not list ' + repr(tier))
        # Jie: this limitation is not necessary
#            for url in tier:
#                if not isValidURL(url):
#                    raise ValueError('announce-list url is not valid '+`url`)

    if 'azureus_properties' in metainfo:
        azprop = metainfo['azureus_properties']
        if not isinstance(azprop, DictType):
            raise ValueError('azureus_properties is not dict, but ' + repr(type(azprop)))
        if 'Content' in azprop:
            content = azprop['Content']
            if not isinstance(content, DictType):
                raise ValueError('azureus_properties content is not dict, but ' + repr(type(content)))
            if 'thumbnail' in content:
                thumb = content['thumbnail']
                if not isinstance(content, StringType):
                    raise ValueError('azureus_properties content thumbnail is not string')

    # Perform check on httpseeds/url-list fields
    if 'url-list' in metainfo:
        if 'files' in metainfo['info']:
            # Only single-file mode allowed for http seeding
            del metainfo['url-list']
            logger.warn("Warning: Only single-file mode supported with HTTP seeding. HTTP seeding disabled")
        elif not isinstance(metainfo['url-list'], ListType):
            del metainfo['url-list']
            logger.warn("Warning: url-list is not of type list. HTTP seeding disabled")
        else:
            for url in metainfo['url-list']:
                if not isValidURL(url):
                    del metainfo['url-list']
                    logger.warn("Warning: url-list url is not valid: %s HTTP seeding disabled", repr(url))
                    break

    if 'httpseeds' in metainfo:
        if not isinstance(metainfo['httpseeds'], ListType):
            del metainfo['httpseeds']
            logger.warn("Warning: httpseeds is not of type list. HTTP seeding disabled")
        else:
            for url in metainfo['httpseeds']:
                if not isValidURL(url):
                    del metainfo['httpseeds']
                    logger.warn("Warning: httpseeds url is not valid: %s HTTP seeding disabled", repr(url))
                    break


def isValidTorrentFile(metainfo):
    try:
        validTorrentFile(metainfo)
        return True
    except:
        print_exc()
        return False


def isValidURL(url):
    if url.lower().startswith('udp'):    # exception for udp
        url = url.lower().replace('udp', 'http', 1)
    r = urlparse.urlsplit(url)
    # if DEBUG:
    #     print >>sys.stderr,"isValidURL:",r

    if r[0] == '' or r[1] == '':
        return False
    return True


def show_permid(permid):
    # Full BASE64-encoded. Must not be abbreviated in any way.
    if not permid:
        return 'None'
    return encodestring(permid).replace("\n", "")
    # Short digest
    # return sha(permid).hexdigest()


def show_permid_short(permid):
    if not permid:
        return 'None'
    s = encodestring(permid).replace("\n", "")
    return s[-10:]
    # return encodestring(sha(s).digest()).replace("\n","")


def print_dict(data, level=0):
    if isinstance(data, dict):
        for i in data:
            logger.info("  " * level + str(i) + ':')
            print_dict(data[i], level + 1)
    elif isinstance(data, list):
        if not data:
            logger.info("[]")
        for i in xrange(len(data)):
            logger.info("  " * level + '[' + str(i) + ']:')
            print_dict(data[i], level + 1)
    else:
        logger.info(repr(data))


def friendly_time(old_time):
    curr_time = time()
    try:
        old_time = int(old_time)
        assert old_time > 0
        diff = int(curr_time - old_time)
    except:
        if isinstance(old_time, str):
            return old_time
        else:
            return '?'
    if diff < 0:
        return '?'
    elif diff < 2:
        return str(diff) + " sec. ago"
    elif diff < 60:
        return str(diff) + " secs. ago"
    elif diff < 120:
        return "1 min. ago"
    elif diff < 3600:
        return str(int(diff / 60)) + " mins. ago"
    elif diff < 7200:
        return "1 hour ago"
    elif diff < 86400:
        return str(int(diff / 3600)) + " hours ago"
    elif diff < 172800:
        return "Yesterday"
    elif diff < 259200:
        return str(int(diff / 86400)) + " days ago"
    else:
        return strftime("%d-%m-%Y", gmtime(old_time))


def sort_dictlist(dict_list, key, order='increase'):

    aux = []
    for i in xrange(len(dict_list)):
        # print >>sys.stderr,"sort_dictlist",key,"in",dict_list[i].keys(),"?"
        if key in dict_list[i]:
            aux.append((dict_list[i][key], i))
    aux.sort()
    if order == 'decrease' or order == 1:    # 0 - increase, 1 - decrease
        aux.reverse()
    return [dict_list[i] for x, i in aux]


def dict_compare(a, b, keys):
    for key in keys:
        order = 'increase'
        if isinstance(key, tuple):
            skey, order = key
        else:
            skey = key

        if a.get(skey) > b.get(skey):
            if order == 'decrease' or order == 1:
                return -1
            else:
                return 1
        elif a.get(skey) < b.get(skey):
            if order == 'decrease' or order == 1:
                return 1
            else:
                return -1

    return 0


def multisort_dictlist(dict_list, keys):

    listcopy = copy.copy(dict_list)
    cmp = lambda a, b: dict_compare(a, b, keys)
    listcopy.sort(cmp=cmp)
    return listcopy


def find_content_in_dictlist(dict_list, content, key='infohash'):
    title = content.get(key)
    if not title:
        logger.error('Error: content had no content_name')
        return False
    for i in xrange(len(dict_list)):
        if title == dict_list[i].get(key):
            return i
    return -1


def remove_torrent_from_list(list, content, key='infohash'):
    remove_data_from_list(list, content, key)


def remove_data_from_list(list, content, key='infohash'):
    index = find_content_in_dictlist(list, content, key)
    if index != -1:
        del list[index]


def sortList(list_to_sort, list_key, order='decrease'):
    aux = sorted(zip(list_key, list_to_sort))
    if order == 'decrease':
        aux.reverse()
    return [i for k, i in aux]


def getPlural(n):
    if n == 1:
        return ''
    else:
        return 's'


def find_prog_in_PATH(prog):
    envpath = os.path.expandvars('${PATH}')
    if sys.platform == 'win32':
        splitchar = ';'
    else:
        splitchar = ':'
    paths = envpath.split(splitchar)
    foundat = None
    for path in paths:
        fullpath = os.path.join(path, prog)
        if os.access(fullpath, os.R_OK | os.X_OK):
            foundat = fullpath
            break
    return foundat


def hostname_or_ip2ip(hostname_or_ip):
    # Arno: don't DNS resolve always, grabs lock on most systems
    ip = None
    try:
        # test that hostname_or_ip contains a xxx.xxx.xxx.xxx string
        socket.inet_aton(hostname_or_ip)
        ip = hostname_or_ip

    except:
        try:
            # dns-lookup for hostname_or_ip into an ip address
            ip = socket.gethostbyname(hostname_or_ip)
            if not hostname_or_ip.startswith("superpeer"):
                logger.info("hostname_or_ip2ip: resolved ip from hostname, an ip should have been provided %s" %\
                    repr(hostname_or_ip))

        except:
            logger.error("hostname_or_ip2ip: invalid hostname %s", hostname_or_ip)
            print_exc()

    return ip


def get_collected_torrent_filename(infohash):
    # Arno: Better would have been the infohash in hex.
    filename = sha(infohash).hexdigest() + '.torrent'    # notice: it's sha1-hash of infohash
    return filename
    # exceptions will be handled by got_metadata()


def parse_magnetlink(url):
    # url must be a magnet link
    dn = None
    xt = None
    trs = []

    logger.debug("parse_magnetlink() %s", url)

    schema, netloc, path, query, fragment = urlsplit(url)
    if schema == "magnet":
        # magnet url's do not conform to regular url syntax (they
        # do not have a netloc.)  This causes path to contain the
        # query part.
        if "?" in path:
            pre, post = path.split("?", 1)
            if query:
                query = "&".join((post, query))
            else:
                query = post

        for key, value in parse_qsl(query):
            if key == "dn":
                # convert to unicode
                dn = value.decode()

            elif key == "xt" and value.startswith("urn:btih:"):
                # vliegendhart: Adding support for base32 in magnet links (BEP 0009)
                encoded_infohash = value[9:49]
                if len(encoded_infohash) == 32:
                    xt = b32decode(encoded_infohash)
                else:
                    xt = binascii.unhexlify(encoded_infohash)

            elif key == "tr":
                trs.append(value)

        logger.debug("parse_magnetlink() NAME: %s", dn)
        logger.debug("parse_magnetlink() HASH: %s", xt)
        logger.debug("parse_magnetlink() TRACS: %s", trs)

    return (dn, xt, trs)


if __name__ == '__main__':

    torrenta = {'name': 'a', 'swarmsize': 12}
    torrentb = {'name': 'b', 'swarmsize': 24}
    torrentc = {'name': 'c', 'swarmsize': 18, 'Web2': True}
    torrentd = {'name': 'b', 'swarmsize': 36, 'Web2': True}

    torrents = [torrenta, torrentb, torrentc, torrentd]
    logger.debug(repr(multisort_dictlist(torrents, ["Web2", ("swarmsize", "decrease")])))


    # d = {'a':1,'b':[1,2,3],'c':{'c':2,'d':[3,4],'k':{'c':2,'d':[3,4]}}}
    # print_dict(d)
