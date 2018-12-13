from __future__ import absolute_import

from binascii import hexlify

"""
This file contains some utility methods that are used by the API.
"""

from six import string_types
from six.moves import xrange

from twisted.web import http

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.MetadataStore.serialization import time2float, CHANNEL_TORRENT, float2time
from Tribler.Core.Modules.restapi import VOTE_SUBSCRIBE

HEALTH_CHECKING = u'Checking..'
HEALTH_DEAD = u'No peers'
HEALTH_ERROR = u'Error'
HEALTH_MOOT = u'Peers found'
HEALTH_GOOD = u'Seeds found'
HEALTH_UNCHECKED = u'Unknown'

CATEGORY_OLD_CHANNEL = u'Old channel'
CATEGORY_CHANNEL = u'Channel'
CATEGORY_UNKNOWN = u'Unknown'


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
    # TODO: the values here are totally random temporary placeholders, and should be removed eventually.
    votes = 1
    my_vote = 2
    spam = 0
    relevance = 0.9
    unix_timestamp = time2float(metadata.timestamp)
    return metadata.rowid, str(metadata.public_key), metadata.title, metadata.tags, int(metadata.size), votes, spam, \
           my_vote, unix_timestamp, relevance, metadata.status, metadata.torrent_date, metadata.metadata_type


def convert_torrent_metadata_to_tuple(metadata):
    """
    Convert some given torrent metadata to a tuple, similar to returned torrents from the database.
    :param metadata: The metadata to convert.
    :return: A tuple with information about the torrent.
    """
    seeders = 0
    leechers = 0
    last_tracker_check = 0
    original_category = metadata.tags.split(' ', 1)[0] if metadata.tags else CATEGORY_UNKNOWN
    category = CATEGORY_CHANNEL if metadata._discriminator_ == CHANNEL_TORRENT else original_category
    infohash = str(metadata.infohash)
    relevance = 0.9
    subscribed = ''
    if metadata._discriminator_ == CHANNEL_TORRENT:
        subscribed = 1 if metadata.subscribed else 0
    return (metadata.rowid, infohash, metadata.title, int(metadata.size), category, seeders, leechers,
            last_tracker_check, None, relevance, metadata.status, metadata.torrent_date, metadata.metadata_type,
            hexlify(metadata.public_key), subscribed)


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
    res_json = {"id": channel[0], "dispersy_cid": hexlify(channel[1]), "name": channel[2],
                "description": channel[3], "votes": channel[5], "torrents": channel[4], "spam": channel[6],
                "modified": channel[8], "subscribed": (channel[7] == VOTE_SUBSCRIBE)}

    if include_rel_score:
        res_json["relevance_score"] = channel[9]

    return res_json


def channel_to_torrent_adapter(channel):
    return (channel[0], '', channel[2], channel[4],
            CATEGORY_OLD_CHANNEL, 0, 0,
            0,
            0,
            0,
            0,
            float2time(0),
            CHANNEL_TORRENT,
            hexlify(channel[1]),
            int(channel[7] == VOTE_SUBSCRIBE))


def convert_chant_channel_to_json(channel):
    """
    This method converts a chant channel entry to a JSON dictionary.
    """
    # TODO: this stuff is mostly placeholder, especially 'modified' field. Should be changed when Dispersy is out.
    res_json = {"id": 0, "dispersy_cid": hexlify(channel.public_key), "name": channel.title,
                "description": channel.tags, "votes": channel.votes, "torrents": channel.size, "spam": 0,
                "modified": channel.version, "subscribed": channel.subscribed}

    return res_json


def convert_db_torrent_to_json(torrent, include_rel_score=False):
    """
    This method converts a torrent in the database to a JSON dictionary.
    """
    torrent_name = torrent[2]
    if torrent_name is None or len(torrent_name.strip()) == 0:
        torrent_name = "Unnamed torrent"

    res_json = {"id": torrent[0], "infohash": hexlify(torrent[1]), "name": torrent_name, "size": torrent[3] or 0,
                "category": torrent[4] if torrent[4] else "unknown", "num_seeders": torrent[5] or 0,
                "num_leechers": torrent[6] or 0,
                "last_tracker_check": torrent[7] or 0,
                "commit_status": torrent[10] if len(torrent) >= 11 else 0,
                "date": str(time2float(torrent[11])) if len(torrent) >= 12 else 0,
                "type": str('channel' if len(torrent) >= 13 and torrent[12] == CHANNEL_TORRENT else 'torrent'),
                "public_key": str(torrent[13]) if len(torrent) >= 14 else '',
                "relevance_score": torrent[9] if include_rel_score else 0,
                "subscribed": str(torrent[14]) if len(torrent) >= 15 else '',
                "health": HEALTH_GOOD if torrent[5] else HEALTH_UNCHECKED,
                "dispersy_cid": str(torrent[13]) if len(torrent) >= 14 else '',
                "votes": 0
                }
    return res_json


def convert_remote_torrent_to_json(torrent):
    """
    This method converts a torrent that has been received by remote peers in the network to a JSON dictionary.
    """
    torrent_name = torrent['name']
    if torrent_name is None or len(torrent_name.strip()) == 0:
        torrent_name = "Unnamed torrent"

    return {'id': torrent['torrent_id'], "infohash": hexlify(torrent['infohash']), "name": torrent_name,
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
        elif isinstance(value, string_types):
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
        if isinstance(arr[ind], string_types):
            new_arr.append(arr[ind].decode('utf-8', 'ignore'))
        elif isinstance(arr[ind], dict):
            new_arr.append(fix_unicode_dict(arr[ind]))
        else:
            new_arr.append(arr[ind])

    return new_arr
