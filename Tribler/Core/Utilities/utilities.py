"""
Different utility methods

Author(s): Jie Yang
"""
from base64 import b32decode
from types import StringType, LongType, IntType, ListType, DictType
import urlparse
from traceback import print_exc
from urlparse import urlsplit, parse_qsl
import binascii
import logging
from libtorrent import bencode, bdecode

from twisted.internet import reactor
from twisted.web import http
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers

from Tribler.Core.version import version_id
from Tribler.Core.exceptions import HttpError

logger = logging.getLogger(__name__)


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
            if not isinstance(port, (IntType, LongType)):
                raise ValueError('node port not int, but ' + repr(type(port)))

    if not ('announce' in metainfo or 'nodes' in metainfo):
        # Niels: 07/06/2012, disabling this check, modifying metainfo to allow for ill-formatted torrents
        metainfo['nodes'] = []
        # raise ValueError('announce and nodes missing')

    # 04/05/10 boudewijn: with the introduction of magnet links we
    # also allow for peer addresses to be (temporarily) stored in the
    # metadata.  Typically these addresses are recently gathered.
    if "initial peers" in metainfo:
        valid_initial_peers = []

        if not isinstance(metainfo["initial peers"], list):
            raise ValueError("initial peers not list, but %s" % type(metainfo["initial peers"]))
        for address in metainfo["initial peers"]:
            if not (isinstance(address, tuple) and len(address) == 2):
                logger.info("address not 2-item tuple, but %s", type(address))
            elif not isinstance(address[0], str):
                logger.info("address host not string, but %s", type(address[0]))
            elif not isinstance(address[1], int):
                logger.info("address port not int, but %s", type(address[1]))
            else:
                valid_initial_peers.append(address)

        metainfo['initial peers'] = valid_initial_peers

    info = metainfo['info']
    if not isinstance(info, DictType):
        raise ValueError('info not dict')

    if 'root hash' in info:
        infokeys = ['name', 'piece length', 'root hash']
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

    # Perform check on httpseeds/url-list fields
    if 'url-list' in metainfo:
        if 'files' in metainfo['info']:
            # Only single-file mode allowed for http seeding
            del metainfo['url-list']
            logger.warn("Warning: Only single-file mode supported with HTTP seeding. HTTP seeding disabled")
        elif not isinstance(metainfo['url-list'], ListType):
            if isinstance(metainfo['url-list'], StringType):
                metainfo['url-list'] = [metainfo['url-list']]
            else:
                del metainfo['url-list']
                logger.warn("Warning: url-list is not of type list/string. HTTP seeding disabled")
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
    except ValueError:
        logger.exception("Could not check torrent file: a ValueError was thrown")
        return False


def isValidURL(url):
    if url.lower().startswith('udp'):    # exception for udp
        url = url.lower().replace('udp', 'http', 1)
    r = urlparse.urlsplit(url)

    if r[0] == '' or r[1] == '':
        return False
    return True


def http_get(uri):

    def _on_response(response):
        if response.code == http.OK:
            return readBody(response)
        raise HttpError(response)

    agent = Agent(reactor)
    deferred = agent.request(
        'GET',
        uri,
        Headers({'User-Agent': ['Tribler ' + version_id]}),
        None)
    deferred.addCallback(_on_response)
    return deferred


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
                dn = value.decode() if not isinstance(value, unicode) else value

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


def fix_torrent(file_path):
    """
    Reads and checks if a torrent file is valid and tries to overwrite the torrent file with a non-sloppy version.
    :param file_path: The torrent file path.
    :return: True if the torrent file is now overwritten with valid information, otherwise False.
    """
    f = open(file_path, 'rb')
    bdata = f.read()
    f.close()

    # Check if correct bdata
    fixed_data = bdecode(bdata)
    if fixed_data is not None:
        fixed_data = bencode(fixed_data)

    return fixed_data


def translate_peers_into_health(peer_info_dicts):
    """
    peer_info_dicts is a peer_info dictionary from LibTorrentDownloadImpl.create_peerlist_data
    purpose : where we want to measure a swarm's health but no tracker can be contacted
    """
    upload_only = 0
    finished = 0
    unfinished_able_dl = 0
    interest_in_us = 0

    # collecting some statistics
    for p_info in peer_info_dicts:
        upload_only_b = False

        if p_info['upload_only']:
            upload_only += 1
            upload_only_b = True
        if p_info['uinterested']:
            interest_in_us += 1
        if p_info['completed'] == 1:
            finished += 1
        else:
            unfinished_able_dl += 1 if upload_only_b else 0

    # seeders potentials:
    # 1. it's only want uploading right now (upload only)
    # 2. it's finished (we don't know whether it want to upload or not)
    # leecher potentials:
    # 1. it's interested in our piece
    # 2. it's unfinished but it's not 'upload only' (it can't leech for some reason)
    # 3. it's unfinished (less restrictive)

    # make sure to change those description when changing the algorithm

    num_seeders = max(upload_only, finished)
    num_leech = max(interest_in_us, min(unfinished_able_dl, len(peer_info_dicts) - finished))
    return num_seeders, num_leech

