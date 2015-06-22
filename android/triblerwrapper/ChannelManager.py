# coding: utf-8
# Written by Wendo Sabée
# Manages local and remote channel searches

import threading
import binascii
from time import time

# Init logger
import logging
_logger = logging.getLogger(__name__)

# Tribler defs
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_MYPREFERENCES, \
    NTFY_VOTECAST, NTFY_CHANNELCAST, NTFY_METADATA, \
    DLSTATUS_METADATA, DLSTATUS_WAITING4HASHCHECK, SIGNAL_ALLCHANNEL_COMMUNITY, SIGNAL_ON_SEARCH_RESULTS

# DB Tuples
from Tribler.Main.Utility.GuiDBTuples import Channel, RemoteChannel, ChannelTorrent, RemoteChannelTorrent

# Tribler communities
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.Core.Utilities.search_utils import split_into_keywords

from BaseManager import BaseManager

class ChannelManager(BaseManager):
    # Code to make this a singleton
    _dispersy = None
    _remote_lock = None

    _torrent_db = None
    _channelcast_db = None
    _votecast_db = None

    _keywords = []
    _results = []
    _result_cids = []

    def init(self):
        """
        Load database handles and Dispersy.
        :return: Nothing.
        """
        self._remote_lock = threading.Lock()

        if not self._connected:
            self._connected = True
            self._torrent_db = self._session.open_dbhandler(NTFY_TORRENTS)
            self._channelcast_db = self._session.open_dbhandler(NTFY_CHANNELCAST)
            self._votecast_db = self._session.open_dbhandler(NTFY_VOTECAST)

            self._dispersy = self._session.lm.dispersy
        else:
            raise RuntimeError('ChannelManager already connected')

    def get_local(self, filter):
        """
        Search the local channel database for channels by keyword.
        :param filter: (Optional) keyword filter.
        :return: List of channels in dictionary format.
        """
        begintime = time()

        try:
            self._set_keywords(filter)
        except:
            return False

        hits = self._channelcast_db.searchChannels(self._keywords)

        _, channels = self._createChannels(hits)

        _logger.error("@@@ Found %s local channels in %ss" % (len(channels), time() - begintime))

        return self._prepare_channels(channels)

    def _prepare_channels(self, chs):
        """
        Convert a list of Channel objects to a list of Channel dictionaries.
        :param chs: List of Channel objects.
        :return: List of Channel dictionaries.
        """
        return [self._prepare_channel(ch) for ch in chs]

    def _prepare_channel(self, ch):
        """
        Convert a Channel object to a Channel dictionary.
        :param ch: Channel object.
        :return: Channel dictionary.
        """
        assert isinstance(ch, Channel)

        return {'id': ch.id,
                'dispersy_cid': binascii.hexlify(ch.dispersy_cid).upper() if ch.dispersy_cid else False,
                'name': ch.name,
                'description': ch.description,
                'nr_torrent': ch.nr_torrents,
                'nr_favorites': ch.nr_favorites or 0,
                'nr_spam': ch.nr_spam or 0,
                'my_vote': ch.my_vote,
                'modified': ch.modified,
                'my_channel': ch.my_channel,
                #'torrents': None,
                #'populair_torrents': None,
                }

    def search_remote(self, keywords):
        """
        Search for channels with our Dispersy peers.
        :param keywords: Keyword to search for.
        :return: Number of searches launched, or False on failure.
        """
        try:
            self._set_keywords(keywords)
        except:
            return False

        nr_requests_made = 0

        if self._dispersy:
            for community in self._dispersy.get_communities():
                if isinstance(community, AllChannelCommunity):
                    self._session.add_observer(self._search_remote_callback, SIGNAL_ALLCHANNEL_COMMUNITY, [SIGNAL_ON_SEARCH_RESULTS])
                    nr_requests_made = community.create_channelsearch(self._keywords)
                    if not nr_requests_made:
                        _logger.info("Could not send search in AllChannelCommunity, no verified candidates found")
                    break

            else:
                _logger.info("Could not send search in AllChannelCommunity, community not found")

        else:
            _logger.info("Could not send search in AllChannelCommunity, Dispersy not found")

        return nr_requests_made

    def _search_remote_callback(self, subject, change_type, object_id, results):
        """
        Callback that is called by Dispersy on incoming search results.
        :param results: Dictionary with keywords and list of torrent results.
        :return: Nothing.
        """
        kws = results['keywords']
        answers = results['torrents']
        _logger.error("@@@@@@@@@ DISPERY CALLBACK!")
        _logger.error("@@@@@ CALL BACK DATA: %s\n%s" % (kws, answers))

        # Ignore searches we don't want (anymore)
        if not self._keywords == kws:
            _logger.error("Disregard search results for %s" % kws)
            return

        try:
            self._remote_lock.acquire()

            _, channels = self.get_channels_by_cid(answers.keys())
            for channel in channels:
                self._add_remote_result(channel)
        finally:
            self._remote_lock.release()

    def _add_remote_result(self, channel):
        """
        Add a result to the local result list, ignoring any duplicates.
        WARNING: Only call when a lock is already acquired.
        :param channel: Channel to add to the list.
        :return: Boolean indicating success.
        """
        # TODO: RLocks instead of normal locks.

        if channel.dispersy_cid in self._result_cids:
            _logger.error("Channel duplicate: %s [%s]" % (channel.name, binascii.hexlify(channel.dispersy_cid)))
            return False

        self._results.append(channel)
        self._result_cids.append(channel.dispersy_cid)

        _logger.error("Channel added: %s [%s]" % (channel.name, binascii.hexlify(channel.dispersy_cid)))
        return True

    def get_remote_results(self):
        """
        Return any results that were found during the last remote search.
        :return: List of Channel dictionaries.
        """
        begintime = time()

        ret = self._prepare_channels(self._results)
        _logger.error("@@@ Found %s remote channels in %ss" % (len(ret), time() - begintime))
        return ret

        """
        TODO: Refactor this code to attach torrents to found channels

        try:
            self._remote_lock.acquire()

            if len(self._channel_results) <= 0:
                return False

            for remoteItem, permid in self._channel_results:

                channel = None
                if not isinstance(remoteItem, Channel):
                    channel_id, _, infohash, torrent_name, timestamp = remoteItem

                    if channel_id not in self._channel_results:
                        channel = self.get_channel(channel_id)
                    else:
                        channel = self._channel_results[channel_id]

                    torrent = channel.getTorrent(infohash)
                    if not torrent:
                        torrent = RemoteChannelTorrent(torrent_id=None, infohash=infohash, name=torrent_name, channel=channel, query_permids=set())
                        channel.addTorrent(torrent)

                    if not torrent.query_permids:
                        torrent.query_permids = set()
                    torrent.query_permids.add(permid)

                    channel.nr_torrents += 1
                    channel.modified = max(channel.modified, timestamp)
                else:
                    channel = remoteItem

                if channel and not channel.id in self._channel_results:
                    self._channel_results[channel.id] = channel
                    hitsUpdated = True # TODO: USE THIS SOMEHOW LATER
        finally:
            self._remote_lock.release()

        _logger.debug("#### HITS ARE UPDATED? %s" % hitsUpdated)

        _logger.debug("ChannelManager: getChannelHits took %s", time() - begintime)

        ret = self._prepare_channels(self._channel_results)
        print ret
        return ret
        """

    def get_remote_results_count(self):
        """
        Get the amount of current remote results.
        :return: Integer indicating the number of results.
        """
        return len(self._results)

    def subscribe(self):
        """
        Subcribe (of favourite) a channel, which means its contents (torrent files) will be cached locally.
        :return: Boolean indicating success.
        """
        return False

    def _set_keywords(self, keywords):
        """
        Set the keywords that a next search should use. This clears the previous keywords and results.
        :param keywords: Keyword string that should be searched for.
        :return: Boolean indicating success.
        """
        keywords = split_into_keywords(unicode(keywords))
        keywords = [keyword for keyword in keywords if len(keyword) > 1]

        if keywords == self._keywords:
            return True

        try:
            self._remote_lock.acquire()

            self._keywords = keywords
            self._results = []
            self._result_cids = []
        finally:
            self._remote_lock.release()

        return True

    def get_channel(self, channel_id):
        """
        Get a channel by id.
        :param channel_id: Channel id.
        :return: A Channel object.
        """
        channel = self._channelcast_db.getChannel(channel_id)
        return self._get_channel(channel)

    def _get_channel(self, channel):
        """
        get_channel helper function that converts a channel list to a Channel object
        :param channel: channel properties list
        :return: Channel object
        """
        if channel:
            channel = self._createChannel(channel)

            # check if we need to convert our vote
            if channel.isDispersy() and channel.my_vote != 0:
                dispersy_id = self._votecast_db.getDispersyId(channel.id, None) or ''
                if dispersy_id <= 0:
                    timestamp = self._votecast_db.getTimestamp(channel.id, None)
                    # TODO: self.do_vote(channel.id, channel.my_vote, timestamp)

        return channel

    def get_channels_by_cid(self, channel_cids):
        """
        Get a channel object by its CID.
        :param channel_cids: Channel CID.
        :return: Channel object.
        """
        channels = self._channelcast_db.getChannelsByCID(channel_cids)
        return self._createChannels(channels)

    def _createChannel(self, hit):
        """
        Create a Channel object from a remote search hit.
        :param hit: Remote search hit.
        :return: Channel object.
        """
        return Channel(*hit)

    def _createChannels(self, hits):
        """
        Create a Channel objects from a list of remote search hits
        :param hits: List of remote search hits.
        :return: List of Channel objects.
        """
        channels = []
        for hit in hits:
            channel = Channel(*hit)
            channels.append(channel)

        return len(channels), channels
