"""
Different utility methods

Author(s): Jie Yang
"""
from base64 import b32decode
from types import StringType, LongType, IntType, ListType, DictType
import urlparse
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


def validate_torrent_nodes(metainfo):
    """
    Validate the list of nodes in the metainfo if such list exists.

    First it is checked whether metainfo contains a list of nodes.
    After this, for each node in the list, the following is checked:
        - Whether the node is a pair of length two
        - Whether the first element is of type String
        - Whether the second element is a tuple consisting of an Int and a Long

    :param metainfo: the metainfo for which the nodes have to be validated
    :return: Returns the nodes of the metainfo or None if they don't exist
    :raise ValueError: if one of the described checks do not succeed
    """
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
        return nodes
    return None


def validate_init_peers(metainfo):
    """
    Validate the list of initial peers in the metainfo if such list exists.

    First it is checked whether metainfo contains a list of nodes.
    After this, for each initial peer in the list, the following is checked:
        - Whether the peer is a tuple of two elements
        - Whether the address host is a String
        - Whether the address port is an Integer

    If there is a peer which does not pass the above tests, the peer is removed from the list

    :param metainfo: the metainfo for which the nodes have to be validated
    :return: a list containing the valid initial peers
    :raise ValueError: if the initial peers element of metainfo is not a list
    """
    valid_initial_peers = []
    if "initial peers" in metainfo:
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
    return valid_initial_peers


def validate_url_list(metainfo):
    """
    Validate the list of URLs in the metainfo if such list exists and remove wrong URLs.

    First checks whether a URL-list exists, after which it is checked whether the metainfo
    would be able to use HTTP seeding. This is not the case if there are multiple files specified.

    A warning is logged if:
        -   There are multiple files specified (HTTP seeding will be disabled)
        -   The URL list is not a list nor a String
        -   There is an invalid URL

    Each URL is validated seperately.

    :param metainfo: the metainfo for which the URLs have to be validated
    :return: a list containing the valid URLs or None if there is a thrown warning, for the cases specified above.
    """
    if 'url-list' in metainfo:
        url_list = metainfo['url-list']
        if 'info' in metainfo and 'files' in metainfo['info']:         # Only single-file mode allowed for http seeding
            logger.warn("Warning: Only single-file mode supported with HTTP seeding. HTTP seeding disabled")
            return None
        elif not isinstance(metainfo['url-list'], ListType):
            if isinstance(metainfo['url-list'], StringType):
                url_list = [metainfo['url-list']]
            else:
                logger.warn("Warning: url-list is not of type list/string. HTTP seeding disabled")
                return None
        for url in url_list:
            if not is_valid_url(url):
                logger.warn("Warning: url-list url is not valid: %s HTTP seeding disabled", repr(url))
                return None
        return url_list
    return None


def validate_http_seeds(metainfo):
    """
    Validate the list of HTTP Seeds in the metainfo if such list exists.

    First checks whether a HTTP Seed list exists.

    A warning is logged if:
        -   The HTTP seeds is not of the type list
        -   One of the HTTP seeds is not a valid URL.

    Each HTTP seed is validated seperately.

    :param metainfo: the metainfo for which the HTTP seeds have to be validated
    :return: a list containing the valid HTTP seeds or None if there is a logged warning, for the cases specified above
    """
    if 'httpseeds' in metainfo:
        http_seeds = []
        if not isinstance(metainfo['httpseeds'], ListType):
            logger.warn("Warning: httpseeds is not of type list. HTTP seeding disabled")
            return None
        else:
            for url in metainfo['httpseeds']:
                if not is_valid_url(url):
                    logger.warn("Warning: httpseeds url is not valid: %s HTTP seeding disabled", repr(url))
                else:
                    http_seeds.append(url)
        return http_seeds
    return None


def validate_files(info):
    """
    Validate the information on files from the torrent info within the metainfo.

    The following information is validated:
        -   Whether there is both a length and files key
        -   Whether the length value is an integer if one exists
        -   Whether the files value is a List if one exists

    For each file (when specified) is validated:
        -   Whether the file has both a path and length key
        -   Whether the path value is of type List
        -   Whether all specified paths are of type String
        -   Whether the length value is of type Long or Integer
    :param info: The torrent information taken from metainfo from which the file info has to be checked.
    :return: None
    :raise ValueError: if one of the above validations do not succeed
    """
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
            if not(all(key in file for key in filekeys)):
                raise ValueError('info files missing path or length key')

            p = file['path']
            if not isinstance(p, ListType):
                raise ValueError('info files path is not list, but ' + repr(type(p)))

            if not(all(isinstance(dirP, StringType) for dirP in p)):
                raise ValueError('info files path is not string')

            l = file['length']
            if not isinstance(l, IntType) and not isinstance(l, LongType):
                raise ValueError('info files length is not int, but ' + repr(type(l)))
    return None


def validate_torrent_info(metainfo):
    """
    Validate the info in the metainfo if it exists.

    The following information is validated:
        -   Whether an info key exists within metainfo
        -   Whether necessary keys exist within information (name, piece length and either root hash or pieces)
        -   Whether the name value is of type String
        -   Whether the piece length value is of type Long or Integer
        -   Whether the root hash is an instance of String qnd has a length of 20 if it exists
        -   Whether the pieces value is an instance of String and it has a length of multiple of 20

    The validate_files function is used to validate more as well.

    :param metainfo: the metainfo for which the information has to be validated
    :return: info if all validations succeed
    :raise ValueError: if one of the above validations do not succeed
    """
    if 'info' not in metainfo:
        raise ValueError('metainfo misses key info')

    info = metainfo['info']
    if not isinstance(info, DictType):
        raise ValueError('info not dict')

    if not(all(x in info for x in {'name, piece length'}) and any(x in info for x in {'root hash', 'pieces'})):
        raise ValueError('info misses key')

    name = info['name']
    if not isinstance(name, StringType):
        raise ValueError('info name is not string but ' + repr(type(name)))

    pl = info['piece length']
    if not (isinstance(pl, IntType) or isinstance(pl, LongType)):
        raise ValueError('info piece size is not int, but ' + repr(type(pl)))

    if 'root hash' in info:
        rh = info['root hash']
        if not isinstance(rh, StringType) or len(rh) != 20:
            raise ValueError('info roothash is not 20-byte string')
    else:
        p = info['pieces']
        if not isinstance(p, StringType) or len(p) % 20 != 0:
            raise ValueError('info pieces is not multiple of 20 bytes')

    validate_files(info)

    return info



def create_valid_metainfo(metainfo):
    """
    Creates a valid metainfo dictionary by validating the elements and correcting when possible.

    :param metainfo: the metainfo that has to be validated
    :return: the original metainfo with corrected elements if possible
    :raise ValueError: if there is a faulty element which cannot be corrected.
    """
    metainfo_result = metainfo

    if not isinstance(metainfo, DictType):
        raise ValueError('metainfo not dict')

    # Niels: Some .torrent files have a dht:// url in the announce field.
    if 'announce' in metainfo and not (is_valid_url(metainfo['announce']) or metainfo['announce'].startswith('dht:')):
        raise ValueError('announce URL bad')

    # common additional fields
    if 'announce-list' in metainfo:
        al = metainfo['announce-list']
        if not isinstance(al, ListType):
            raise ValueError('announce-list is not list, but ' + repr(type(al)))
        if not(all(isinstance(tier, ListType) for tier in al)):
            raise ValueError('announce-list tier is not list')

    if not ('announce' in metainfo or 'nodes' in metainfo):
        # Niels: 07/06/2012, disabling this check, modifying metainfo to allow for ill-formatted torrents
        metainfo_result['nodes'] = []

    metainfo_result['nodes'] = validate_torrent_nodes(metainfo_result)
    metainfo_result['initial peers'] = validate_init_peers(metainfo)
    metainfo_result['url-list'] = validate_url_list(metainfo)
    metainfo_result['httpseeds'] = validate_http_seeds(metainfo)
    metainfo_result['info'] = validate_torrent_info(metainfo)

    return dict((k, v) for k, v in metainfo_result.iteritems() if v)


def valid_torrent_file(metainfo):
    """
    Checks whether the given metainfo is valid.


    :param metainfo: the metainfo to be validated
    :return: whether the specified metainfo is valid or not
    """
    try:
        create_valid_metainfo(metainfo)
        return True
    except ValueError:
        logger.exception("Could not check torrent file: a ValueError was thrown")
        return False


def is_valid_url(url):
    """
    Checks whether the given URL is a valid URL.

    Both UDP and HTTP URLs will be validated correctly.

    :param url: an object representing the URL
    :return: Boolean specifying whether the URL is valid
    """
    if url.lower().startswith('udp'):
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
