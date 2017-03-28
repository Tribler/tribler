"""
Supported boosting sources.

Author(s): Egbert Bouman, Mihai Capota, Elric Milon, Ardhi Putra
"""
import glob
import logging
import os
import re
import urllib
from binascii import hexlify, unhexlify
from hashlib import sha1

import feedparser
import libtorrent as lt
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.defer import CancelledError
from twisted.internet.task import LoopingCall
from twisted.web.client import Agent, readBody, getPage
from twisted.web.error import Error
from twisted.web.http_headers import Headers

from Tribler.Core.CreditMining.credit_mining_util import ent2chr
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import NTFY_INSERT, NTFY_TORRENTS, NTFY_UPDATE
from Tribler.Core.version import version_id
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.channel.community import ChannelCommunity
from Tribler.dispersy.exception import CommunityNotFoundException
from Tribler.dispersy.taskmanager import TaskManager


class BoostingSource(TaskManager):
    """
    Base class for boosting source. For now, it can be RSS, directory, and channel
    """

    def __init__(self, session, source, boost_settings, torrent_insert_cb):
        super(BoostingSource, self).__init__()
        self.session = session
        self.channelcast_db = session.lm.channelcast_db

        self.torrents = {}
        self.source = source
        self.interval = boost_settings.source_interval
        self.max_torrents = boost_settings.max_torrents_per_source
        self.torrent_insert_callback = torrent_insert_cb
        self.archive = False

        self.enabled = True

        self.av_uprate = 0
        self.av_dwnrate = 0
        self.storage_used = 0
        self.ready = False

        self.min_connection = boost_settings.min_connection_start
        self.min_channels = boost_settings.min_channels_start

        self._logger = logging.getLogger(BoostingSource.__name__)

        self.boosting_manager = self.session.lm.boosting_manager

    def start(self):
        """
        Start operating mining for this source
        """
        d = self._load_if_ready(self.source)
        self.register_task(str(self.source) + "_load", d, value=self.source)
        self._logger.debug("Start mining on %s", self.source)

    def kill_tasks(self):
        """
        kill tasks on this source
        """
        self.ready = False
        self.cancel_all_pending_tasks()

    def _load_if_ready(self, source):
        """
        load source if and only if the overall system is ready.

        This is useful so we don't burden the application during the startup
        """
        def check_system(defer_param=None):
            """
            function that check the system whether it's ready or not

            it depends on #connection and #channel
            """
            if defer_param is None:
                defer_param = defer.Deferred()

            nr_channels = self.channelcast_db.getNrChannels()
            nr_connections = 0

            for community in self.session.lm.dispersy.get_communities():
                from Tribler.community.search.community import SearchCommunity
                if isinstance(community, SearchCommunity):
                    nr_connections = community.get_nr_connections()

            if nr_channels > self.min_channels and nr_connections > self.min_connection:
                defer_param.callback(source)
            else:
                self.register_task(str(self.source)+"_check_sys", reactor.callLater(10, check_system, defer_param))

            return defer_param

        defer_check = check_system()
        defer_check.addCallbacks(self._load, self._on_err)
        return defer_check

    def _load(self, source):
        pass

    def _update(self):
        pass

    def get_source_text(self):
        """
        returning 'raw' source. May be overriden
        """
        return self.source

    def _on_err(self, err_msg):
        self._logger.error(err_msg)


class ChannelSource(BoostingSource):
    """
    Credit mining source from a channel.
    """
    def __init__(self, session, dispersy_cid, boost_settings, torrent_insert_cb):
        BoostingSource.__init__(self, session, dispersy_cid, boost_settings, torrent_insert_cb)

        self.channel_id = None

        self.channel_dict = None
        self.community = None
        self.database_updated = True

        self.check_torrent_interval = 10
        self.dispersy_cid = dispersy_cid

        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        self.session.add_observer(self._on_database_updated, NTFY_TORRENTS, [NTFY_INSERT, NTFY_UPDATE])

        self.unavail_torrent = {}
        self.loaded_torrent = {}

    def kill_tasks(self):
        BoostingSource.kill_tasks(self)

        self.session.remove_observer(self._on_database_updated)

    def _load(self, dispersy_cid):
        dispersy = self.session.get_dispersy_instance()

        def join_community():
            """
            find the community/channel id, then join
            """
            try:
                self.community = dispersy.get_community(dispersy_cid, True)
                self.register_task(str(self.source) + "_get_id", reactor.callLater(1, get_channel_id))

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
                    self.register_task(str(self.source) + "_get_id", reactor.callLater(1, get_channel_id))
                else:
                    self._logger.error("Could not find AllChannelCommunity")

        def get_channel_id():
            """
            find channel id by looking at the network
            """
            if self.community and self.community._channel_id:
                self.channel_id = self.community._channel_id

                self.channel_dict = self.channelcast_db.getChannel(self.channel_id)
                task_call = self.register_task(str(self.source) + "_update",
                                               LoopingCall(self._update)).start(self.interval, now=True)
                if task_call:
                    self._logger.debug("Registering update call")

                self._logger.info("Got channel id %s", self.channel_id)

                self.ready = True
            else:
                self._logger.warning("Could not get channel id, retrying in 10 s")
                self.register_task(str(self.source) + "_get_id", reactor.callLater(10, get_channel_id))

        self.register_task(str(self.source) + "_join_comm", reactor.callLater(1, join_community))

    def _check_tor(self):
        """
        periodically check torrents in channel. Will return the torrent data if finished.
        """
        def showtorrent(torrent):
            """
            assembly torrent data, call the callback
            """
            infohash = torrent.infohash
            if torrent.get_files() and infohash in self.unavail_torrent:
                if len(self.torrents) >= self.max_torrents:
                    self._logger.debug("Max torrents in source reached. Not adding %s", torrent.infohash)
                    del self.unavail_torrent[torrent.infohash]
                    return

                self._logger.debug("[ChannelSource] Got torrent %s", hexlify(infohash))
                self.torrents[infohash] = {}
                self.torrents[infohash]['name'] = torrent.get_name()
                self.torrents[infohash]['metainfo'] = torrent
                self.torrents[infohash]['creation_date'] = torrent.get_creation_date()
                self.torrents[infohash]['length'] = torrent.get_length()
                self.torrents[infohash]['num_files'] = len(torrent.get_files())
                #TODO(ardhi) get seeder/leecher from db
                self.torrents[infohash]['num_seeders'] = 0
                self.torrents[infohash]['num_leechers'] = 0
                self.torrents[infohash]['enabled'] = self.enabled

                # seeding stats from DownloadState
                self.torrents[infohash]['last_seeding_stats'] = {}

                del self.unavail_torrent[infohash]

                if self.torrent_insert_callback:
                    self.torrent_insert_callback(self.source, infohash, self.torrents[infohash])
                self.database_updated = False

        if len(self.unavail_torrent) and self.enabled:
            self._logger.debug("Unavailable #torrents : %d from %s", len(self.unavail_torrent), hexlify(self.source))
            for torrent in self.unavail_torrent.values():
                self._load_torrent(torrent[2]).addCallback(showtorrent)

    def _update(self):
        if len(self.torrents) < self.max_torrents and self.database_updated:
            CHANTOR_DB = ['ChannelTorrents.channel_id', 'Torrent.torrent_id', 'infohash', '""', 'length',
                          'category', 'status', 'num_seeders', 'num_leechers', 'ChannelTorrents.id',
                          'ChannelTorrents.dispersy_id', 'ChannelTorrents.name', 'Torrent.name',
                          'ChannelTorrents.description', 'ChannelTorrents.time_stamp', 'ChannelTorrents.inserted']

            torrent_values = self.channelcast_db.getTorrentsFromChannelId(self.channel_id, True, CHANTOR_DB,
                                                                          self.max_torrents)

            # dict {key_infohash(binary):Torrent(tuples)}
            self.unavail_torrent.update({t[2]: t for t in torrent_values if t[2] not in self.torrents})

            # Start the torrent channel checker in the first run
            if not self.is_pending_task_active(hexlify(self.source) + "_checktor"):
                task_call = self.register_task(hexlify(self.source) + "_checktor", LoopingCall(self._check_tor))
                self._logger.debug("Registering check torrent function")
                task_call.start(self.check_torrent_interval, now=True)

    def _on_database_updated(self, dummy_subject, dummy_change_type, dummy_infohash):
        self.database_updated = True

    def get_source_text(self):
        return str(self.channel_dict[2]) if self.channel_dict else None

    def _load_torrent(self, infohash):
        """
        function to download a torrent by infohash and call a callback afterwards
        with TorrentDef object as parameter.
        """

        def add_to_loaded(infohash_str):
            """
            function to add loaded infohash to memory
            """
            self.loaded_torrent[unhexlify(infohash_str)].callback(
                TorrentDef.load_from_memory(self.session.get_collected_torrent(unhexlify(infohash_str))))

        if infohash not in self.loaded_torrent:
            self.loaded_torrent[infohash] = defer.Deferred()

            if not self.session.has_collected_torrent(infohash):
                if self.session.has_download(infohash):
                    return
                self.session.download_torrentfile(infohash, add_to_loaded, 0)

        deferred_load = self.loaded_torrent[infohash]

        return deferred_load


class RSSFeedSource(BoostingSource):
    """
    Credit mining source from a RSS feed.
    """

    def __init__(self, session, rss_feed, boost_settings, torrent_insert_cb):
        BoostingSource.__init__(self, session, rss_feed, boost_settings, torrent_insert_cb)

        self.parsed_rss = None

        self.torrent_store = self.session.lm.torrent_store

        # Not all RSS feeds provide us with the infohash,
        # so we use a fake infohash based on the URL (generated by sha1) to identify the torrents.
        # keys : fake infohash, value : real infohash. Type : (length 20 string, binary)
        self.fake_infohash_id = {}

        self.title = ""
        self.description = ""
        self.total_torrents = 0

        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)

    def _on_success_rss(self, body_rss, rss_feed):
        """
        function called when RSS successfully read
        """
        self.register_task(str(self.source) + "_update", LoopingCall(self._update),
                           10, interval=self.interval)
        self.parsed_rss = feedparser.parse(body_rss)
        self._logger.info("Got RSS feed %s", rss_feed)
        self.ready = True

    def _on_error_rss(self, failure, rss_feed):
        """
        function called when RSS failed except from 503
        aborting load the source
        """
        failure.trap(CancelledError, Error)
        self._logger.error("Aborting load on : %s. Reason : %s.", rss_feed, failure.getErrorMessage())

        if "503" in failure.getErrorMessage():
            self.register_task(str(self.source)+"_load_delay", reactor.callLater(10, self._load, rss_feed))
            return

        if rss_feed in self.boosting_manager.boosting_sources:
            self.boosting_manager.set_enable_mining(rss_feed, False)

    def _load(self, rss_feed):

        defer_feed = getPage(rss_feed)
        defer_feed.addCallback(self._on_success_rss, rss_feed)
        defer_feed.addErrback(self._on_error_rss, rss_feed)

        self.register_task(str(self.source)+"_wait_feed", defer_feed)

    def _update(self):
        if len(self.torrents) >= self.max_torrents:
            return

        feed_elem = self.parsed_rss['feed']

        self.title = feed_elem['title']
        self.description = feed_elem['subtitle']

        torrent_keys = ['name', 'metainfo', 'creation_date', 'length', 'num_files', 'num_seeders', 'num_leechers',
                        'enabled', 'last_seeding_stats']

        def __cb_body(body_bin, item_torrent_entry):
            tdef = None
            metainfo = None

            # tdef.get_infohash returned binary string by length 20
            try:
                metainfo = lt.bdecode(body_bin)
                tdef = TorrentDef.load_from_dict(metainfo)
                self.session.save_collected_torrent(tdef.get_infohash(), body_bin)
            except ValueError, err:
                self._logger.error("Could not parse/save torrent, skipping %s. Reason: %s",
                                   item_torrent_entry['link'], err.message +
                                   ", metainfo is " + ("not " if metainfo else "") +"None")

            if tdef and len(self.torrents) < self.max_torrents:
                # Create a torrent dict.
                real_infohash = tdef.get_infohash()
                torrent_values = [item_torrent_entry['title'], tdef, tdef.get_creation_date(), tdef.get_length(),
                                  len(tdef.get_files()), -1, -1, self.enabled, {}]

                # store the real infohash to generated infohash
                self.torrents[real_infohash] = dict(zip(torrent_keys, torrent_values))
                self.fake_infohash_id[sha1(item_torrent_entry['id']).digest()] = real_infohash

                # manually generate an ID and put this into DB
                self.torrent_db.addOrGetTorrentID(real_infohash)
                self.torrent_db.addExternalTorrent(tdef)

                # Notify the BoostingManager and provide the real infohash.
                if self.torrent_insert_callback:
                    self.torrent_insert_callback(self.source, real_infohash, self.torrents[real_infohash])
            elif tdef:
                self._logger.debug("Max torrents in source reached. Not adding %s", tdef.get_infohash())

        def __success_cb(response, item_dict):
            return readBody(response).addCallback(__cb_body, item_dict).addErrback(self._on_err)

        regex_unescape_xml = re.compile(r"\&\#(x?[0-9a-fA-F]+);")

        for item in self.parsed_rss['entries']:
            f_links = item['links']
            for link in f_links:
                if link['type'] == u'application/x-bittorrent':
                    url = regex_unescape_xml.sub(ent2chr, str(link['href']))
                    fake_infohash = sha1(url).digest()
                    if fake_infohash not in self.fake_infohash_id.keys():
                        # create Agent to download torrent file
                        self.fake_infohash_id[fake_infohash] = None
                        agent = Agent(reactor)
                        ses_agent = agent.request(
                            'GET',  # http://stackoverflow.com/a/845595
                            urllib.quote(url, safe="%/:=&?~#+!$,;'@()*[]"),
                            Headers({'User-Agent': ['Tribler ' + version_id]}),
                            None)
                        ses_agent.addCallback(__success_cb, item).addErrback(self._on_err)


class DirectorySource(BoostingSource):
    """
    Credit mining source from a local directory

    The directory must exist.
    """

    def _load(self, directory):
        if os.path.isdir(directory):
            # Wait for __init__ to finish so the source is registered with the
            # BoostinManager, otherwise adding torrents won't work
            self.register_task(str(self.source) + "_update",
                               LoopingCall(self._update), delay=2, interval=self.interval)
            self._logger.info("Got directory %s", directory)
            self.ready = True
        else:
            self._logger.error("Could not find directory %s", directory)

    def _update(self):
        torrent_keys = ['name', 'metainfo', 'creation_date', 'length', 'num_files', 'num_seeders', 'num_leechers',
                        'enabled', 'last_seeding_stats']

        # Wait for __init__ to finish so the source is registered with the
        # BoostingManager, otherwise adding torrents won't work. Although we already include delay when call this
        if not self.ready:
            return

        for torrent_filename in glob.glob(self.source + '/*.torrent'):
            if torrent_filename not in self.torrents and len(self.torrents) < self.max_torrents:
                try:
                    tdef = TorrentDef.load(torrent_filename)
                except ValueError, verr:
                    self._logger.error("Could not load %s. Reason %s", torrent_filename, verr)
                    continue

                # Create a torrent dict.
                infohash = tdef.get_infohash()
                torrent_values = [tdef.get_name_as_unicode(), tdef, tdef.get_creation_date(), tdef.get_length(),
                                  len(tdef.get_files()), -1, -1, self.enabled, {}]
                self.torrents[infohash] = dict(zip(torrent_keys, torrent_values))
                # Notify the BoostingManager.
                if self.torrent_insert_callback:
                    self.torrent_insert_callback(self.source, tdef.get_infohash(), self.torrents[infohash])
