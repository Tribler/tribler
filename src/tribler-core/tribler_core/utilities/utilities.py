"""
This module mainly provides validation and correction for urls. This class
provides a method for HTTP GET requests as well as a function to translate peers into health.
Author(s): Jie Yang
"""
import binascii
import logging
import re
from base64 import b32decode
from urllib.parse import parse_qsl, urlsplit

from tribler_core.utilities.libtorrent_helper import libtorrent as lt

logger = logging.getLogger(__name__)


def is_valid_url(url):
    """
    Checks whether the given URL is a valid URL.

    Both UDP and HTTP URLs will be validated correctly.

    :param url: an object representing the URL
    :return: Boolean specifying whether the URL is valid
    """
    if ' ' in url.strip():
        return
    if url.lower().startswith('udp'):
        url = url.lower().replace('udp', 'http', 1)
    split_url = urlsplit(url)

    return not(split_url[0] == '' or split_url[1] == '')


def parse_magnetlink(url):
    """
    Parses the magnet link provided by the given URL.

    The output of this file consists of:
        -   dn: The display name of the magnet link
        -   xt: The URI containing the file hash of the magnet link
        -   trs: The list of Tracker URLs
    :param url: the URL at which the magnet link can be found
    :return: (dn, xt, trs) tuple, which will be left (None, None, []) if the
    given URL does not lead to a magnet link
    """
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
                # convert to Unicode
                dn = value.decode('utf-8') if not isinstance(value, str) else value

            elif key == "xt" and value.startswith("urn:btih:"):
                # vliegendhart: Adding support for base32 in magnet links (BEP 0009)
                encoded_infohash = value[9:49]
                if len(encoded_infohash) == 32:
                    xt = b32decode(encoded_infohash.upper())
                else:
                    xt = binascii.unhexlify(encoded_infohash)

            elif key == "tr":
                trs.append(value)

        logger.debug("parse_magnetlink() NAME: %s", dn)
        logger.debug("parse_magnetlink() HASH: %s", xt)
        logger.debug("parse_magnetlink() TRACS: %s", trs)

    return dn, xt, trs


def translate_peers_into_health(peer_info_dicts):
    """
    peer_info_dicts is a peer_info dictionary from Download.create_peerlist_data.
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


def unichar_string(text):
    """ Unicode character interpretation of text for Python 2.7 """
    return ''.join(chr(ord(t)) for t in text)


def is_simple_match_query(query):
    """
    Check if the query is a simple match query with AND operators only.
    Supports unicode characters.
    """
    pattern = re.compile(r"\"[\\\w]+\"\*", flags=re.UNICODE)
    splits = pattern.split(query)
    for connector in splits:
        if connector and connector != " AND ":
            return False
    return True


def has_bep33_support():
    """
    Return whether our libtorrent version has support for BEP33 (DHT health lookups).
    Also see https://github.com/devos50/libtorrent/tree/bep33_support
    """
    return 'dht_pkt_alert' in dir(lt)


def is_infohash(infohash):
    return infohash and len(infohash) == 40 and is_hex_string(infohash)


def is_channel_public_key(key):
    return key and len(key) == 128 and is_hex_string(key)


def is_hex_string(text):
    try:
        int(text, 16)
        return True
    except ValueError:
        return False


def bdecode_compat(packet_buffer):
    """
    Utility method to make libtorrent bdecode() with Python3 in the existing Tribler codebase.
    We should change this when Libtorrent wrapper is refactored.
    """
    try:
        return lt.bdecode(packet_buffer)
    except RuntimeError:
        return None
