# coding=utf-8
"""
Written by Egbert Bouman, Mihai Capotă, Elric Milon, and Ardhi Putra Pratama H
Supported boosting sources
"""
import HTMLParser
import glob
import logging
import os
import random
import re
import time
import urllib
from binascii import hexlify
from hashlib import sha1

import libtorrent as lt
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import NTFY_INSERT, NTFY_TORRENTS, NTFY_UPDATE, NTFY_CHANNELCAST, NTFY_VOTECAST
from Tribler.Core.version import version_id
from Tribler.Main.Utility.GuiDBTuples import Torrent, CollectedTorrent, RemoteTorrent, NotCollectedTorrent, Channel, \
    ChannelTorrent
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.channel.community import ChannelCommunity
from Tribler.dispersy.exception import CommunityNotFoundException
from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import call_on_reactor_thread

def ent2chr(input_str):
    """
    Function to unescape literal string in XML to symbols
    source : http://www.gossamer-threads.com/lists/python/python/177423
    """
    code = input_str.group(1)
    code_int = int(code) if code.isdigit() else int(code[1:], 16)
    return chr(code_int) if code_int < 256 else '?'


class TorrentManagerCM(TaskManager):
    """
    *Temporary* class to handle load torrent.

    Adapted from TorrentManager in SearchGridManager
    """
    __single = None

    def __init__(self, session):
        super(TorrentManagerCM, self).__init__()
        TorrentManagerCM.__single = self

        self.session = session
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        self.channelcast_db = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.votecastdb = self.session.open_dbhandler(NTFY_VOTECAST)

        self.dslist = []

    # TODO(ardhi) : temporary function until GUI and core code are separated
    def load_torrent(self, torrent, callback=None):
        """
        function to load torrent dictionary to torrent object.

        From TorrentManager.loadTorrent in SearchGridManager
        """

        # session is quitting
        if not (self.session and self.session.get_torrent_store() and self.session.lm.torrent_store):
            return

        if not isinstance(torrent, CollectedTorrent):
            if torrent.torrent_id <= 0:
                torrent_id = self.torrent_db.getTorrentID(torrent.infohash)
                if torrent_id:
                    torrent.update_torrent_id(torrent_id)

            if not self.session.has_collected_torrent(torrent.infohash):
                files = []
                trackers = []

                # see if we have most info in our tables
                if isinstance(torrent, RemoteTorrent):
                    torrent_id = self.torrent_db.getTorrentID(torrent.infohash)
                else:
                    torrent_id = torrent.torrent_id

                trackers.extend(self.torrent_db.getTrackerListByTorrentID(torrent_id))

                if 'DHT' in trackers:
                    trackers.remove('DHT')
                if 'no-DHT' in trackers:
                    trackers.remove('no-DHT')

                # replacement # self.downloadTorrentfileFromPeers(torrent, None)
                if self.session.has_download(torrent.infohash):
                    return False

                if torrent.query_candidates is None or len(torrent.query_candidates) == 0:
                    self.session.download_torrentfile(torrent.infohash, None, 0)
                else:
                    for candidate in torrent.query_candidates:
                        self.session.download_torrentfile_from_peer(candidate, torrent.infohash, None, 0)

                torrent = NotCollectedTorrent(torrent, files, trackers)

            else:
                tdef = TorrentDef.load_from_memory(self.session.get_collected_torrent(torrent.infohash))

                if torrent.torrent_id <= 0:
                    del torrent.torrent_id

                torrent = CollectedTorrent(torrent, tdef)

        # replacement # self.library_manager.addDownloadState(torrent)
        for dl_state in self.dslist:
            torrent.addDs(dl_state)

        # return
        if callback is not None:
            callback(torrent)
        else:
            return torrent

    @staticmethod
    def get_instance(*args, **kw):
        """
        get single instance of TorrentManagerCM
        """
        if TorrentManagerCM.__single is None:
            TorrentManagerCM(*args, **kw)
        return TorrentManagerCM.__single

    @staticmethod
    def del_instance():
        """
        resetting, then deleting single instance
        """
        TorrentManagerCM.__single = None


class BoostingSource(object):
    """
    Base class for boosting source. For now, it can be RSS, directory, and channel
    """

    def __init__(self, session, source, boost_settings, callback):
        self.session = session
        self.channelcast_db = session.lm.channelcast_db

        self.torrents = {}
        self.source = source
        self.interval = boost_settings.source_interval
        self.max_torrents = boost_settings.max_torrents_per_source
        self.callback = callback
        self.archive = False

        self.enabled = True

        self.av_uprate = 0
        self.av_dwnrate = 0
        self.storage_used = 0
        self.ready = False

        self.min_connection = boost_settings.min_connection_start
        self.min_channels = boost_settings.min_channels_start

        self.torrent_mgr = TorrentManagerCM.get_instance(session)

        # local import for handling circular import
        from Tribler.Policies.BoostingManager import BoostingManager
        self.boosting_manager = BoostingManager.get_instance()
        self._logger = logging.getLogger(BoostingManager.__name__)

    def kill_tasks(self):
        """
        kill tasks on this source
        """

        self.ready = False
        self.torrent_mgr.del_instance()

        self.session.lm.threadpool.cancel_pending_task(str(self.source) + "_load")

        self.session.lm.threadpool.cancel_pending_task(self.source)

    def _load_if_ready(self, source):
        """
        load source if and only if the overall system is ready.

        it depends on #connection and #channel

        Useful to not burden the apps in startup
        """

        nr_channels = self.channelcast_db.getNrChannels()
        nr_connections = 0

        for community in self.session.lm.dispersy.get_communities():
            from Tribler.community.search.community import SearchCommunity
            if isinstance(community, SearchCommunity):
                nr_connections = community.get_nr_connections()

        # condition example
        if nr_channels > self.min_channels and nr_connections > self.min_connection:
            called_func = self._load
        else:
            called_func = self._load_if_ready

        self.session.lm.threadpool.add_task(lambda src=source: called_func(src), 15, task_name=str(self.source) + "_load")

    def _load(self, source):
        pass

    def _update(self):
        pass

    def get_source_text(self):
        """
        returning 'raw' source. May be overriden
        """
        return self.source


class ChannelSource(BoostingSource):
    """
    Credit mining source from a channel.
    """
    def __init__(self, session, dispersy_cid, boost_settings, callback):
        BoostingSource.__init__(self, session, dispersy_cid, boost_settings, callback)

        self.channel_id = None

        self.channel = None
        self.community = None
        self.database_updated = True

        self.check_torrent_interval = 10

        self.session.add_observer(self._on_database_updated, NTFY_TORRENTS, [NTFY_INSERT, NTFY_UPDATE])
        self.session.lm.threadpool.add_task(lambda cid=dispersy_cid: self._load_if_ready(cid), 0,
                                            task_name=str(self.source) + "_load")

        self.unavail_torrent = {}

    def kill_tasks(self):
        BoostingSource.kill_tasks(self)

        # cancel loading channel id
        self.session.lm.threadpool.cancel_pending_task(str(self.source) + "_get_channel_id")

        self.session.remove_observer(self._on_database_updated)

    def _load(self, dispersy_cid):
        dispersy = self.session.get_dispersy_instance()

        def join_community():
            """
            find the community/channel id, then join
            """
            try:
                self.community = dispersy.get_community(dispersy_cid, True)
                self.session.lm.threadpool.add_task(get_channel_id, 0, task_name=str(self.source) + "_get_channel_id")

            except CommunityNotFoundException:

                allchannelcommunity = None
                for community in dispersy.get_communities():
                    if isinstance(community, AllChannelCommunity):
                        allchannelcommunity = community
                        break

                if allchannelcommunity:
                    self.community = ChannelCommunity.init_community(dispersy, dispersy.get_member(mid=dispersy_cid),
                                                                     allchannelcommunity._my_member, self.session)
                    self._logger.info("Joined channel community %s", dispersy_cid.encode("HEX"))
                    self.session.lm.threadpool.add_task(get_channel_id, 0,
                                                        task_name=str(self.source) + "_get_channel_id")
                else:
                    self._logger.error("Could not find AllChannelCommunity")

        def get_channel_id():
            """
            find channel id by looking at the network
            """
            if self.community and self.community._channel_id: # before: and self.gui_util.registered:
                self.channel_id = self.community._channel_id

                channel_dict = self.boosting_manager.channelcast_db.getChannel(self.channel_id)
                self.channel = Channel(*channel_dict)

                if not self.boosting_manager.is_pending_task_active(str(self.source) + "_update"):
                    self._logger.debug("Registering update call")
                    self.boosting_manager.register_task(str(self.source) + "_update", LoopingCall(self._update)).start(
                        self.interval, now=True)
                # self.session.lm.threadpool.add_task(self._update, 0, task_name=str(self.source)+"_update")
                self._logger.info("Got channel id %s", self.channel_id)
            else:
                self._logger.warning("Could not get channel id, retrying in 10 s")
                self.session.lm.threadpool.add_task(get_channel_id, 10, task_name=str(self.source) + "_get_channel_id")

        try:
            join_community()
            self.ready = True
        except CommunityNotFoundException:
            self._logger.info("Channel %s was not ready, waits for next interval (%d chn)", hexlify(self.source),
                              len(dispersy.get_communities()))
            self.session.lm.threadpool.add_task(lambda cid=dispersy_cid: self._load_if_ready(cid), 0,
                                                task_name=str(self.source) + "_load")

    def _check_tor(self):
        """
        periodically check torrents in channel. Will return the torrent data if finished.
        """
        def showtorrent(torrent):
            """
            assembly torrent data, call the callback
            """
            if torrent.files:
                infohash = torrent.infohash
                self._logger.debug("[ChannelSource] Got torrent %s", hexlify(infohash))
                self.torrents[infohash] = {}
                self.torrents[infohash]['name'] = torrent.name
                self.torrents[infohash]['metainfo'] = torrent.tdef
                self.torrents[infohash]['creation_date'] = torrent.creation_date
                self.torrents[infohash]['length'] = torrent.tdef.get_length()
                self.torrents[infohash]['num_files'] = len(torrent.files)
                self.torrents[infohash]['num_seeders'] = torrent.swarminfo[0] or 0
                self.torrents[infohash]['num_leechers'] = torrent.swarminfo[1] or 0
                self.torrents[infohash]['enabled'] = self.enabled

                # seeding stats from DownloadState
                self.torrents[infohash]['last_seeding_stats'] = {}

                del self.unavail_torrent[infohash]

                if self.callback:
                    self.callback(self.source, infohash, self.torrents[infohash])
                self.database_updated = False

        self._logger.debug("Unavailable #torrents : %d from %s", len(self.unavail_torrent), hexlify(self.source))

        if len(self.unavail_torrent) and self.enabled:
            for torrent in self.unavail_torrent.values():
                self.torrent_mgr.load_torrent(torrent, showtorrent)

    def _update(self):
        if len(self.torrents) < self.max_torrents:

            if self.database_updated:
                CHANTOR_DB = ['ChannelTorrents.channel_id', 'Torrent.torrent_id', 'infohash', '""', 'length',
                              'category', 'status', 'num_seeders', 'num_leechers', 'ChannelTorrents.id',
                              'ChannelTorrents.dispersy_id', 'ChannelTorrents.name', 'Torrent.name',
                              'ChannelTorrents.description', 'ChannelTorrents.time_stamp', 'ChannelTorrents.inserted']

                torrent_values = self.channelcast_db.getTorrentsFromChannelId(self.channel_id, True, CHANTOR_DB,
                                                                              self.max_torrents)

                # TODO(ardhi) : temporary function until GUI and core code are separated
                def create_torrents(tor_values, _, channel_dict):
                    """
                    function to create torrents from channel. Adapted from
                    ChannelManager in SearchGridManager
                    """

                    #adding new channel from the one that can't be detected from torrent values
                    fetch_channels = set(hit[0] for hit in tor_values if hit[0] not in channel_dict)
                    if len(fetch_channels) > 0:
                        channels_new_dict = self.channelcast_db.getChannels(fetch_channels)
                        channels = []
                        for hit in channels_new_dict:
                            channel = Channel(*hit)
                            channels.append(channel)

                        for channel in channels:
                            channel_dict[channel.id] = channel

                    # creating torrents
                    torrents = []
                    for hit in tor_values:
                        if hit:
                            chan_torrent = ChannelTorrent(*hit[1:] + [channel_dict.get(hit[0], None), None])
                            chan_torrent.torrent_db = self.boosting_manager.torrent_db
                            chan_torrent.channelcast_db = self.channelcast_db

                            if chan_torrent.name:
                                torrents.append(chan_torrent)

                    return torrents

                listtor = create_torrents(torrent_values, True,
                                          {self.channel_id: self.channelcast_db.getChannel(self.channel_id)})
                # listtor = self.gui_util.channelsearch_manager._createTorrents(
                #     torrent_values, True, {self.channel_id: self.channelcast_db.getChannel(self.channel_id)})[2]

                # dict {key_infohash(binary):Torrent(object-GUIDBTuple)}
                self.unavail_torrent.update({t.infohash: t for t in listtor if t.infohash not in self.torrents})

                # it's highly probable the checktor function is running at this time (if it's already running)
                # if not running, start the checker
                if not self.boosting_manager.is_pending_task_active(hexlify(self.source) + "_checktor"):
                    self._logger.debug("Registering check torrent function")
                    self.boosting_manager.register_task(hexlify(self.source) + "_checktor",
                                                        LoopingCall(self._check_tor)).start(self.check_torrent_interval,
                                                                                            now=True)

    def _on_database_updated(self, subject, change_type, infohash):
        self.database_updated = True

    def get_source_text(self):
        return self.channel.name if self.channel else None


class RSSFeedSource(BoostingSource):
    """
    Credit mining source from a RSS feed.

    # supported list (tested) :
    # http://bt.etree.org/rss/bt_etree_org.rdf
    # http://www.mininova.org/rss.xml
    # https://kat.cr (via torcache)

    # not supported (till now)
    # https://eztv.ag/ezrss.xml (https link)
    """

    def __init__(self, session, rss_feed, boost_settings, callback):
        BoostingSource.__init__(self, session, rss_feed, boost_settings, callback)

        self.feed_handle = None

        self.session.lm.threadpool.add_task(lambda feed=rss_feed: self._load_if_ready(feed), 0,
                                            task_name=str(self.source) + "_load")

        self.title = ""
        self.description = ""
        self.total_torrents = 0

    def _load(self, rss_feed):
        self.feed_handle = self.session.lm.ltmgr.get_session().add_feed(
            {'url': rss_feed, 'auto_download': False, 'auto_map_handles': False})

        def wait_for_feed():
            """
            Wait until the RSS feed is no longer updating.
            """
            feed_status = self.feed_handle.get_feed_status()
            if feed_status['updating']:
                self.session.lm.threadpool.add_task(wait_for_feed, 1, task_name=str(self.source) + "_wait_for_feed")
            elif len(feed_status['error']) > 0:
                self._logger.error("Got error for RSS feed %s : %s", feed_status['url'], feed_status['error'])
                if "503" in feed_status["error"]:
                    def retry_task():
                        self.feed_handle.update_feed()
                        self.session.lm.threadpool.add_task(wait_for_feed, 1,
                                                            task_name=str(self.source) + "_wait_for_feed")

                    # if failed, wait for 10 second to retry
                    self.session.lm.threadpool.add_task(retry_task, 10, task_name=str(self.source) + "_wait_for_feed")
            else:
                # The feed is done updating. Now periodically start retrieving torrents.
                self.boosting_manager.register_task(str(self.source) + "_update", LoopingCall(self._update),
                                                    10, interval=self.interval)
                self._logger.info("Got RSS feed %s", feed_status['url'])
                self.ready = True

        wait_for_feed()

    def _update(self):
        if len(self.torrents) < self.max_torrents:

            feed_status = self.feed_handle.get_feed_status()

            self.title = feed_status['title']
            self.description = feed_status['description']

            torrent_keys = ['name', 'metainfo', 'creation_date', 'length', 'num_files', 'num_seeders', 'num_leechers',
                            'enabled', 'last_seeding_stats']

            self.total_torrents = len(feed_status['items'])

            def __cb_body(body_bin, item_torrent, torrent_fname):
                tdef = None
                metainfo = None
                try:
                    metainfo = lt.bdecode(body_bin)
                    tdef = TorrentDef.load_from_dict(metainfo)
                    tdef.save(torrent_fname)
                except ValueError, err:
                    self._logger.error("Could not parse/save torrent, skipping %s. Reason: %s",
                                       item_torrent['url'], err.message +
                                       ", metainfo is "+("not " if metainfo else "")+"None")
                except IOError, ioerr:
                    # can't save to disk. Ignore this swarm
                    self._logger.exception("IO error, check %s. Message : %s",
                                       self.boosting_manager.settings.credit_mining_path, ioerr.message)
                    return
                if tdef:
                    # Create a torrent dict.
                    torrent_values = [item_torrent['title'], tdef, tdef.get_creation_date(), tdef.get_length(),
                                      len(tdef.get_files()), -1, -1, self.enabled, {}]
                    self.torrents[sha1(item_torrent['url']).digest()] = dict(zip(torrent_keys, torrent_values))

                    try:
                        # manually generate an ID and put this into DB
                        self.session.lm.torrent_db.addOrGetTorrentID(sha1(item_torrent['url']).digest())
                        self.session.lm.torrent_db.addExternalTorrent(tdef)

                        # create Torrent object and store it
                        self.torrent_mgr.load_torrent(Torrent.fromTorrentDef(tdef))
                    except AttributeError, err:
                        # if we can't find torrent_db, fallback
                        self._logger.error("Can't do %s. Return gracely as failed.", err.message)
                        return
                    # self.gui_util.torrentsearch_manager.loadTorrent(Torrent.fromTorrentDef(tdef))

                    # Notify the BoostingManager and provide the real infohash.
                    if self.callback:
                        self.callback(self.source, tdef.get_infohash(), self.torrents[sha1(
                            item_torrent['url']).digest()])

            def __success_cb(response, item_dict, torrent_filename):
                return readBody(response).addCallback(__cb_body, item_dict, torrent_filename)

            regex_unescape_xml = re.compile(r"\&\#(x?[0-9a-fA-F]+);")

            for item in feed_status['items']:
                # Not all RSS feeds provide us with the infohash,
                # so we use a fake infohash based on the URL to identify the torrents.
                url = regex_unescape_xml.sub(ent2chr, item['url'])
                infohash = sha1(url).digest()
                if infohash not in self.torrents:
                    # Store the torrents as rss-infohash_as_hex.torrent.
                    torrent_filename = os.path.join(self.boosting_manager.settings.credit_mining_path,
                                                    'rss-%s.torrent' % infohash.encode('hex'))
                    tdef = None
                    if not os.path.exists(torrent_filename):

                        # create Agent to download torrent file
                        agent = Agent(reactor)
                        ses_agent = agent.request(
                            'GET',  # http://stackoverflow.com/a/845595
                            urllib.quote(url, safe="%/:=&?~#+!$,;'@()*[]"),
                            Headers({'User-Agent': ['Tribler ' + version_id]}),
                            None)
                        ses_agent.addCallback(__success_cb, item, torrent_filename)

                    else:
                        # torrent already exist in our system
                        tdef = TorrentDef.load(torrent_filename)

                        if tdef:
                            # Create a torrent dict.
                            torrent_values = [item['title'], tdef, tdef.get_creation_date(), tdef.get_length(),
                                              len(tdef.get_files()), -1, -1, self.enabled, {}]
                            self.torrents[infohash] = dict(zip(torrent_keys, torrent_values))

                            # manually generate an ID and put this into DB
                            self.session.lm.torrent_db.addOrGetTorrentID(infohash)
                            self.session.lm.torrent_db.addExternalTorrent(tdef)

                            # create Torrent object and store it
                            self.torrent_mgr.load_torrent(Torrent.fromTorrentDef(tdef))
                            # self.gui_util.torrentsearch_manager.loadTorrent(Torrent.fromTorrentDef(tdef))

                            # Notify the BoostingManager and provide the real infohash.
                            if self.callback:
                                self.callback(self.source, tdef.get_infohash(), self.torrents[infohash])

    def kill_tasks(self):
        BoostingSource.kill_tasks(self)

        self.session.lm.threadpool.cancel_pending_task(str(self.source) + "_wait_for_feed")

        # stop updating
        self.session.lm.threadpool.cancel_pending_task(str(self.source) + "_update")


class DirectorySource(BoostingSource):
    """
    Credit mining source from a local directory

    The directory must be exist.
    """

    def __init__(self, session, directory, boost_settings, callback):
        BoostingSource.__init__(self, session, directory, boost_settings, callback)
        self._load(directory)

    def _load(self, directory):
        if os.path.isdir(directory):
            # Wait for __init__ to finish so the source is registered with the
            # BoostinManager, otherwise adding torrents won't work
            self.session.lm.threadpool.add_task(self._update, 1, task_name=str(self.source) + "_update")
            self._logger.info("Got directory %s", directory)
            self.ready = True
        else:
            self._logger.error("Could not find directory %s", directory)

    def _update(self):
        if len(self.torrents) < self.max_torrents:

            torrent_keys = ['name', 'metainfo', 'creation_date', 'length', 'num_files', 'num_seeders', 'num_leechers',
                            'enabled', 'last_seeding_stats']

            for torrent_filename in glob.glob(self.source + '/*.torrent'):
                if torrent_filename not in self.torrents:
                    try:
                        tdef = TorrentDef.load(torrent_filename)
                    except ValueError, verr:
                        self._logger.debug("Could not load torrent locally, skipping %s", torrent_filename)
                        self._logger.error("Could not load %s. Reason %s", torrent_filename, verr)
                        continue

                    # Create a torrent dict.
                    infohash = tdef.get_infohash()
                    torrent_values = [tdef.get_name_as_unicode(), tdef, tdef.get_creation_date(), tdef.get_length(),
                                      len(tdef.get_files()), -1, -1, self.enabled, {}]
                    self.torrents[infohash] = dict(zip(torrent_keys, torrent_values))
                    # Notify the BoostingManager.
                    if self.callback:
                        self.callback(self.source, tdef.get_infohash(), self.torrents[infohash])

            self.session.lm.threadpool.add_task(self._update, self.interval, task_name=str(self.source) + "_update")

    def kill_tasks(self):
        BoostingSource.kill_tasks(self)

        # stop updating
        self.session.lm.threadpool.cancel_pending_task(str(self.source) + "_update")
