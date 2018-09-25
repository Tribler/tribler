"""
This file contains some utility methods that are used by the API.
"""
import math
from struct import unpack_from
from twisted.web import http

from Tribler.Core.Modules.MetadataStore.serialization import time2float
from Tribler.Core.Modules.restapi import VOTE_SUBSCRIBE
from Tribler.Core.simpledefs import NTFY_TORRENTS
import Tribler.Core.Utilities.json_util as json


def return_handled_exception(request, exception):
    """
    :param request: the request that encountered the exception
    :param exception: the handled exception
    :return: JSON dictionary describing the exception
    """
    request.setResponseCode(http.INTERNAL_SERVER_ERROR)
    return json.dumps({
        u"error": {
            u"handled": True,
            u"code": exception.__class__.__name__,
            u"message": exception.message
        }
    })


def convert_channel_metadata_to_tuple(metadata):
    """
    Convert some given channel metadata to a tuple, similar to returned channels from the database.
    :param metadata: The metadata to convert.
    :return: A tuple with information about the torrent.
    """
    votes = 1
    my_vote = 2
    spam = 0
    relevance = 0.9
    unix_timestamp = time2float(metadata.timestamp)
    return metadata.rowid, str(metadata.public_key), metadata.title, metadata.tags, int(metadata.size), votes, spam,\
           my_vote, unix_timestamp, relevance


def convert_torrent_metadata_to_tuple(metadata):
    """
    Convert some given torrent metadata to a tuple, similar to returned torrents from the database.
    :param metadata: The metadata to convert.
    :return: A tuple with information about the torrent.
    """
    seeders = 0
    leechers = 0
    last_tracker_check = 0
    category = 'unknown'
    infohash = str(metadata.infohash)
    relevance = 0.9

    return (metadata.rowid, infohash, metadata.title, int(metadata.size), category, seeders, leechers,
            last_tracker_check, None, relevance)


def convert_search_torrent_to_json(torrent):
    """
    Converts a given torrent to a JSON dictionary. Note that the torrent might be either a result from the local
    database in which case it is a tuple or a remote search result in which case it is a dictionary.
    """
    if isinstance(torrent, dict):
        return convert_remote_torrent_to_json(torrent)
    return convert_db_torrent_to_json(torrent, include_rel_score=True)


def convert_db_channel_to_json(channel, include_rel_score=False):
    """
    This method converts a channel in the database to a JSON dictionary.
    """
    res_json = {"id": channel[0], "dispersy_cid": channel[1].encode('hex'), "name": channel[2],
                "description": channel[3], "votes": channel[5], "torrents": channel[4], "spam": channel[6],
                "modified": channel[8], "subscribed": (channel[7] == VOTE_SUBSCRIBE)}

    if include_rel_score:
        res_json["relevance_score"] = channel[9]

    return res_json


def convert_db_torrent_to_json(torrent, include_rel_score=False):
    """
    This method converts a torrent in the database to a JSON dictionary.
    """
    torrent_name = torrent[2]
    if torrent_name is None or len(torrent_name.strip()) == 0:
        torrent_name = "Unnamed torrent"

    res_json = {"id": torrent[0], "infohash": torrent[1].encode('hex'), "name": torrent_name, "size": torrent[3],
                "category": torrent[4], "num_seeders": torrent[5] or 0, "num_leechers": torrent[6] or 0,
                "last_tracker_check": torrent[7] or 0}

    if include_rel_score:
        res_json["relevance_score"] = torrent[9]

    return res_json


def convert_remote_torrent_to_json(torrent):
    """
    This method converts a torrent that has been received by remote peers in the network to a JSON dictionary.
    """
    torrent_name = torrent['name']
    if torrent_name is None or len(torrent_name.strip()) == 0:
        torrent_name = "Unnamed torrent"

    return {'id': torrent['torrent_id'], "infohash": torrent['infohash'].encode('hex'), "name": torrent_name,
            'size': torrent['length'], 'category': torrent['category'], 'num_seeders': torrent['num_seeders'],
            'num_leechers': torrent['num_leechers'], 'last_tracker_check': 0}


def get_parameter(parameters, name):
    """
    Return a specific parameter with a name from a HTTP request (or None if that parameter is not available).
    """
    if name not in parameters or len(parameters[name]) == 0:
        return None
    return parameters[name][0]


def fix_unicode_dict(d):
    """
    This method removes illegal (unicode) characters recursively from a dictionary.
    This is required since Dispersy members might add invalid characters to their strings and we are unable to utf8
    encode these when sending the data over the API.
    """
    new_dict = {}

    for key, value in d.items():
        if isinstance(value, dict):
            new_dict[key] = fix_unicode_dict(value)
        elif isinstance(value, tuple):
            new_dict[key] = fix_unicode_array(list(value))
        elif isinstance(value, list):
            new_dict[key] = fix_unicode_array(value)
        elif isinstance(value, (str, unicode)):
            new_dict[key] = value.decode('utf-8', 'ignore')
        else:
            new_dict[key] = value

    return new_dict


def fix_unicode_array(arr):
    """
    Iterate over the items of the array and remove invalid unicode characters.
    """
    new_arr = []

    for ind in xrange(len(arr)):
        if isinstance(arr[ind], (str, unicode)):
            new_arr.append(arr[ind].decode('utf-8', 'ignore'))
        elif isinstance(arr[ind], dict):
            new_arr.append(fix_unicode_dict(arr[ind]))
        else:
            new_arr.append(arr[ind])

    return new_arr
