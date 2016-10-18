"""
This file contains some utility methods that are used by the API.
"""
import json
from struct import unpack_from
import math

from twisted.web import http

from Tribler.Core.Modules.restapi import VOTE_SUBSCRIBE
from Tribler.Core.simpledefs import NTFY_TORRENTS
from Tribler.community.channel.community import ChannelCommunity
from Tribler.dispersy.exception import CommunityNotFoundException


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


def can_edit_channel(channel_id, channel_vote):
    """
    This method returns whether the channel can be edited or not.
    """
    from Tribler.Core.Session import Session
    if Session.get_instance().get_dispersy():
        dispersy = Session.get_instance().get_dispersy_instance()
        try:
            cmty = dispersy.get_community(channel_id)
            channel_type, is_mod = cmty.get_channel_mode()
            if is_mod or channel_vote == VOTE_SUBSCRIBE and channel_type == ChannelCommunity.CHANNEL_OPEN:
                return True
        except CommunityNotFoundException:
            return False
    return False


def convert_db_torrent_to_json(torrent, include_rel_score=False):
    """
    This method converts a torrent in the database to a JSON dictionary.
    """
    torrent_name = torrent[2] if torrent[2] is not None else "Unnamed torrent"

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
    torrent_name = torrent['name'] if torrent['name'] is not None else "Unnamed torrent"
    relevance_score = relevance_score_remote_torrent(torrent_name)

    return {'id': torrent['torrent_id'], "infohash": torrent['infohash'].encode('hex'), "name": torrent_name,
            'size': torrent['length'], 'category': torrent['category'], 'num_seeders': torrent['num_seeders'],
            'num_leechers': torrent['num_leechers'], 'last_tracker_check': 0,
            'relevance_score': relevance_score}


def get_parameter(parameters, name):
    """
    Return a specific parameter with a name from a HTTP request (or None if that parameter is not available).
    """
    if name not in parameters or len(parameters[name]) == 0:
        return None
    return parameters[name][0]


def relevance_score_remote_torrent(torrent_name):
    """
    Calculate the relevance score of a remote torrent, based on the name and the matchinfo object
    of the last torrent from the database.
    The algorithm used is the same one as in search_in_local_torrents_db in SqliteCacheDBHandler.py.
    """
    from Tribler.Core.Session import Session
    torrent_db = Session.get_instance().open_dbhandler(NTFY_TORRENTS)
    if torrent_db.latest_matchinfo_torrent is None:
        return 0.0
    matchinfo, keywords = torrent_db.latest_matchinfo_torrent

    num_phrases, num_cols, num_rows = unpack_from('III', matchinfo)
    unpack_str = 'I' * (3 * num_cols * num_phrases)
    matchinfo = unpack_from('I' * 9 + unpack_str, matchinfo)[9:]

    score = 0.0
    for phrase_ind in xrange(num_phrases):
        rows_with_term = matchinfo[3 * (phrase_ind * num_cols) + 2]
        term_freq = torrent_name.lower().count(keywords[phrase_ind])

        inv_doc_freq = math.log((num_rows - rows_with_term + 0.5) / (rows_with_term + 0.5), 2)
        right_side = ((term_freq * (1.2 + 1)) / (term_freq + 1.2))

        score += inv_doc_freq * right_side

    return score
