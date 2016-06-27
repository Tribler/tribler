# -*- coding: utf-8 -*-
# Written by Egbert Bouman, Mihai Capotă, Elric Milon, and Ardhi Putra Pratama H
"""Manage boosting of swarms"""
import logging
import os
import shutil
from binascii import hexlify, unhexlify

import libtorrent as lt
from twisted.internet.task import LoopingCall

from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
from Tribler.Core.Utilities import utilities
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.exceptions import OperationNotPossibleAtRuntimeException
from Tribler.Core.simpledefs import DLSTATUS_SEEDING, NTFY_TORRENTS, NTFY_UPDATE, NTFY_CHANNELCAST
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Policies.BoostingPolicy import SeederRatioPolicy
from Tribler.Policies.BoostingSource import ChannelSource
from Tribler.Policies.BoostingSource import DirectorySource
from Tribler.Policies.BoostingSource import RSSFeedSource
from Tribler.Policies.credit_mining_util import source_to_string, string_to_source, compare_torrents
from Tribler.Policies.defs import SAVED_ATTR, CREDIT_MINING_FOLDER_DOWNLOAD, CONFIG_KEY_ARCHIVELIST, \
    CONFIG_KEY_SOURCELIST, CONFIG_KEY_ENABLEDLIST, CONFIG_KEY_DISABLEDLIST
from Tribler.dispersy.taskmanager import TaskManager


class BoostingSettings(object):
    """
    This class contains settings used by the boosting manager
    """
    def __init__(self, session, policy=SeederRatioPolicy, load_config=True):
        self.session = session

        # Configurable parameter (changeable in runtime -plus sources-)
        self.max_torrents_active = 20
        self.max_torrents_per_source = 10
        self.source_interval = 100
        self.swarm_interval = 100

        # Can't be changed on runtime
        self.tracker_interval = 200
        self.logging_interval = 60
        self.share_mode_target = 3
        self.policy = policy(session)

        # Non-Configurable
        self.initial_logging_interval = 20
        self.initial_tracker_interval = 25
        self.initial_swarm_interval = 30
        self.min_connection_start = 5
        self.min_channels_start = 100
        self.credit_mining_path = os.path.join(DefaultDownloadStartupConfig.getInstance().get_dest_dir(),
                                               CREDIT_MINING_FOLDER_DOWNLOAD)
        self.load_config = load_config


class BoostingManager(TaskManager):
    """
    Class to manage all the credit mining activities
    """

    __single = None

    def __init__(self, session, settings=None):
        super(BoostingManager, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        BoostingManager.__single = self
        self.boosting_sources = {}
        self.torrents = {}

        self.session = session
        assert self.session.get_libtorrent()

        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        self.channelcast_db = self.session.open_dbhandler(NTFY_CHANNELCAST)

        # use provided settings or a default one
        self.settings = settings or BoostingSettings(session, load_config=True)

        if self.settings.load_config:
            self._logger.info("Loading config file from session configuration")
            self.load_config()

        if not os.path.exists(self.settings.credit_mining_path):
            os.makedirs(self.settings.credit_mining_path)

        self.session.lm.ltmgr.get_session().set_settings(
            {'share_mode_target': self.settings.share_mode_target})

        self.session.add_observer(self.on_torrent_notify, NTFY_TORRENTS, [NTFY_UPDATE])

        self.register_task("CreditMining_select", LoopingCall(self._select_torrent),
                           self.settings.initial_swarm_interval, interval=self.settings.swarm_interval)

        self.register_task("CreditMining_scrape", LoopingCall(self.scrape_trackers),
                           self.settings.initial_tracker_interval, interval=self.settings.tracker_interval)

        self.register_task("CreditMining_log", LoopingCall(self.log_statistics),
                           self.settings.initial_logging_interval, interval=self.settings.logging_interval)

    @staticmethod
    def get_instance(*args, **kw):
        """
        get single instance of Boostingmanager
        """
        if BoostingManager.__single is None:
            BoostingManager(*args, **kw)
        return BoostingManager.__single

    @staticmethod
    def del_instance():
        """
        resetting, then deleting single instance
        """
        BoostingManager.__single = None

    def shutdown(self):
        """
        Shutting down boosting manager. It also stops and remove all the sources.
        """
        self.save_config()
        self._logger.info("Shutting down boostingmanager")

        for sourcekey in self.boosting_sources.keys():
            self.remove_source(sourcekey)

        self.cancel_all_pending_tasks()

        #remove credit mining data in not persistent mode
        shutil.rmtree(self.settings.credit_mining_path, ignore_errors=True)

    def get_source_object(self, sourcekey):
        return self.boosting_sources.get(sourcekey, None)

    def set_enable_mining(self, source, mining_bool=True, force_restart=False):
        """
        Dynamically enable/disable mining source.
        """
        for ihash, tor in self.torrents.iteritems():
            if tor['source'] == source_to_string(source):
                self.torrents[ihash]['enabled'] = mining_bool

                # pause torrent download from disabled source
                if not mining_bool:
                    self.stop_download(tor)

        self.boosting_sources[string_to_source(source)].enabled = mining_bool

        self._logger.info("Set mining source %s %s", source, mining_bool)

        if force_restart:
            self._select_torrent()

    def add_source(self, source):
        """
        add new source into the boosting manager
        """
        if source not in self.boosting_sources:
            args = (self.session, source, self.settings, self.on_torrent_insert)

            try:
                isdir = os.path.isdir(source)
            except TypeError:
                # this handle binary data that has null bytes '\00'
                isdir = False

            if isdir:
                self.boosting_sources[source] = DirectorySource(*args)
            elif source.startswith('http://') or source.startswith('https://'):
                self.boosting_sources[source] = RSSFeedSource(*args)
            elif len(source) == 20:
                self.boosting_sources[source] = ChannelSource(*args)
            else:
                self._logger.error("Cannot add unknown source %s", source)
                return

            self._logger.info("Added source %s", source)
        else:
            self._logger.info("Already have source %s", source)

    def remove_source(self, source_key):
        """
        remove source by stop the downloading and remove its metainfo for all its swarms
        """
        if source_key in self.boosting_sources:
            source = self.boosting_sources.pop(source_key)
            source.kill_tasks()
            self._logger.info("Removed source %s", source_key)

            rm_torrents = [torrent for _, torrent in self.torrents.items()
                           if torrent['source'] == source_to_string(source_key)]

            for torrent in rm_torrents:
                self.stop_download(torrent)
                self.torrents.pop(torrent["metainfo"].get_infohash(), None)

            self._logger.info("Torrents download stopped and removed")

    def on_torrent_insert(self, source, infohash, torrent):
        """
        This function called when a source is finally determined. Fetch some torrents from it,
        then insert it into our data
        """

        # Remember where we got this torrent from
        self._logger.debug("remember torrent %s from %s", torrent, source_to_string(source))

        torrent['source'] = source_to_string(source)

        boost_source = self.boosting_sources.get(source, None)
        if not boost_source:
            self._logger.info("Dropping torrent insert from removed source: %s", repr(torrent))
            return
        elif boost_source.archive:
            torrent['preload'] = True
            torrent['prio'] = 100

        # If duplicates exist, set is_duplicate to True, except for the one with the most seeders.
        duplicates = [other for other in self.torrents.values() if compare_torrents(torrent, other)]
        if duplicates:
            duplicates += [torrent]
            healthiest_torrent = max([(torrent['num_seeders'], torrent) for torrent in duplicates])[1]
            for duplicate in duplicates:
                is_duplicate = healthiest_torrent != duplicate
                duplicate['is_duplicate'] = is_duplicate
                if is_duplicate and duplicate.get('download', None):
                    self.stop_download(duplicate)

        self.torrents[infohash] = torrent

    def on_torrent_notify(self, subject, change_type, infohash):
        """
        Notify us when we have new seeder/leecher value in torrent from tracker
        """
        if infohash not in self.torrents:
            return

        self._logger.debug("infohash %s %s %s updated", subject, change_type, hexlify(infohash))

        tdict = self.torrent_db.getTorrent(infohash, keys=['C.torrent_id', 'infohash', 'name',
                                                           'length', 'category', 'status', 'num_seeders',
                                                           'num_leechers'])

        if tdict:
            infohash_str = hexlify(tdict['infohash'])

            new_seed = tdict['num_seeders']
            new_leecher = tdict['num_leechers']

            if new_seed - self.torrents[tdict['infohash']]['num_seeders'] \
                    or new_leecher - self.torrents[tdict['infohash']]['num_leechers']:
                self.torrents[tdict['infohash']]['num_seeders'] = new_seed
                self.torrents[tdict['infohash']]['num_leechers'] = new_leecher
                self._logger.info("infohash %s : seeder/leecher changed seed:%d leech:%d",
                                  infohash_str, new_seed, new_leecher)

    def scrape_trackers(self):
        """
        Manually scrape tracker by requesting to tracker manager
        """

        for infohash, _ in self.torrents.iteritems():
            # torrent handle
            lt_torrent = self.session.lm.ltmgr.get_session().find_torrent(lt.big_number(infohash))

            peer_list = []
            for i in lt_torrent.get_peer_info():
                peer = LibtorrentDownloadImpl.create_peerlist_data(i)
                peer_list.append(peer)

            num_seed, num_leech = utilities.translate_peers_into_health(peer_list)
            self._logger.debug("Seeder/leecher data translated from peers : seeder %s, leecher %s", num_seed, num_leech)

            # check health(seeder/leecher)
            self.session.lm.torrent_checker.add_gui_request(infohash, True)

    def set_archive(self, source, enable):
        """
        setting archive of a particular source. Affect all the torrents in this source
        """
        if source in self.boosting_sources:
            self.boosting_sources[source].archive = enable
            self._logger.info("Set archive mode for %s to %s", source, enable)
        else:
            self._logger.error("Could not set archive mode for unknown source %s", source)

    def start_download(self, torrent):
        """
        Start downloading a particular torrent and add it to download list in Tribler
        """
        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(self.settings.credit_mining_path)
        dscfg.set_safe_seeding(False)

        preload = torrent.get('preload', False)

        pstate = CallbackConfigParser()
        pstate.add_section('state')
        pstate.set('state', 'engineresumedata', torrent.get('pstate', None))

        # not using Session.start_download because we need to specify pstate
        if self.session.lm.download_exists(torrent["metainfo"].get_infohash()):
            self._logger.error("Already downloading %s. Cancel start_download",
                               hexlify(torrent["metainfo"].get_infohash()))
            return

        self._logger.info("Starting %s preload %s has pstate %s",
                          hexlify(torrent["metainfo"].get_infohash()), preload,
                          True if torrent.get('pstate', None) else False)

        torrent['download'] = self.session.lm.add(torrent['metainfo'], dscfg, pstate=pstate,
                                                  hidden=True, share_mode=not preload, checkpoint_disabled=True)
        torrent['download'].set_priority(torrent.get('prio', 1))

    def stop_download(self, torrent):
        """
        Stopping torrent that currently downloading
        """
        ihash = lt.big_number(torrent["metainfo"].get_infohash())
        self._logger.info("Stopping %s", str(ihash))
        download = torrent.pop('download', False)
        lt_torrent = self.session.lm.ltmgr.get_session().find_torrent(ihash)
        if download and lt_torrent.is_valid():
            self._logger.info("Writing resume data for %s", str(ihash))
            torrent['pstate'] = download.write_resume_data()
            self.session.remove_download(download, hidden=True)

    def _select_torrent(self):
        """
        Function to select which torrent in the torrent list will be downloaded in the
        next iteration. It depends on the source and applied policy
        """
        torrents = {}
        for infohash, torrent in self.torrents.iteritems():
            # we prioritize archive source
            if torrent.get('preload', False):
                if 'download' not in torrent:
                    self.start_download(torrent)
                elif torrent['download'].get_status() == DLSTATUS_SEEDING:
                    self.stop_download(torrent)
            elif not torrent.get('is_duplicate', False):
                if torrent.get('enabled', True):
                    torrents[infohash] = torrent

        if self.settings.policy is not None and torrents:
            # Determine which torrent to start and which to stop.
            torrents_start, torrents_stop = self.settings.policy.apply(
                torrents, self.settings.max_torrents_active)
            for torrent in torrents_stop:
                self.stop_download(torrent)
            for torrent in torrents_start:
                self.start_download(torrent)

            self._logger.info("Selecting from %s torrents %s start download", len(torrents), len(torrents_start))

    def load_config(self):
        """
        load config in file configuration and apply it to manager
        """
        validate_source = lambda s: unhexlify(s) if len(s) == 40 and not s.startswith("http") else s

        def _add_sources(values):
            """
            adding sources in configuration file
            """
            for boosting_source in values:
                boosting_source = validate_source(boosting_source)
                self.add_source(boosting_source)

        def _archive_sources(values):
            """
            setting archive to sources
            """
            for archive_source in values:
                archive_source = validate_source(archive_source)
                self.set_archive(archive_source, True)

        def _set_enable_boosting(values, enabled):
            """
            set disable/enable source
            """
            for boosting_source in values:
                boosting_source = validate_source(boosting_source)
                if boosting_source not in self.boosting_sources.keys():
                    self.add_source(boosting_source)
                self.boosting_sources[boosting_source].enabled = enabled

        switch = {
            "boosting_sources": {
                "cmd": _add_sources,
                "args": (None,)
            },
            "archive_sources": {
                "cmd": _archive_sources,
                "args": (None,)
            },
            "boosting_enabled": {
                "cmd": _set_enable_boosting,
                "args": (None, True)
            },
            "boosting_disabled": {
                "cmd": _set_enable_boosting,
                "args": (None, False)
            },
        }

        # set policy
        self.settings.policy = self.session.get_cm_policy(True)(self.session)

        dict_to_load = {}
        dict_to_load.update(self.session.get_cm_sources())
        dict_to_load.update(dict.fromkeys(SAVED_ATTR))

        for k, val in dict_to_load.items():
            try:
                if k in SAVED_ATTR:
                    # see the session configuration
                    object.__setattr__(self.settings, k,
                                       getattr(self.session, "get_cm_%s" %k)())
                else: #credit mining source handle
                    switch[k]["cmd"](*((switch[k]['args'][0] or val,) + switch[k]['args'][1:]))
            except KeyError:
                self._logger.error("Key %s can't be applied", k)

    def save_config(self):
        """
        save the environment parameters in config file
        """
        for k in SAVED_ATTR:
            try:
                setattr(self.session, "set_cm_%s" % k, getattr(self.settings, k))
            except OperationNotPossibleAtRuntimeException:
                # some of the attribute can't be changed in runtime. See lm.sessconfig_changed_callback
                self._logger.debug("Cannot set attribute %s. Not permitted in runtime", k)

        archive_sources = []
        lboosting_sources = []
        flag_enabled_sources = []
        flag_disabled_sources = []
        for boosting_source_name, boosting_source in \
                self.boosting_sources.iteritems():

            bsname = source_to_string(boosting_source_name)

            lboosting_sources.append(bsname)
            if boosting_source.enabled:
                flag_enabled_sources.append(bsname)
            else:
                flag_disabled_sources.append(bsname)

            if boosting_source.archive:
                archive_sources.append(bsname)

        self.session.set_cm_sources(lboosting_sources, CONFIG_KEY_SOURCELIST)
        self.session.set_cm_sources(flag_enabled_sources, CONFIG_KEY_ENABLEDLIST)
        self.session.set_cm_sources(flag_disabled_sources, CONFIG_KEY_DISABLEDLIST)
        self.session.set_cm_sources(archive_sources, CONFIG_KEY_ARCHIVELIST)

        self.session.save_pstate_sessconfig()

    def log_statistics(self):
        """Log transfer statistics"""
        lt_torrents = self.session.lm.ltmgr.get_session().get_torrents()

        for lt_torrent in lt_torrents:
            status = lt_torrent.status()

            if unhexlify(str(status.info_hash)) in self.torrents:
                self._logger.debug("Status for %s : %s %s | ul_lim : %d, max_ul %d, maxcon %d", status.info_hash,
                                   status.all_time_download, status.all_time_upload, lt_torrent.upload_limit(),
                                   lt_torrent.max_uploads(), lt_torrent.max_connections())

                # piece_priorities will fail in libtorrent 1.0.9
                if lt.__version__ == '1.0.9.0':
                    continue
                else:
                    non_zero_values = []
                    for piece_priority in lt_torrent.piece_priorities():
                        if piece_priority != 0:
                            non_zero_values.append(piece_priority)
                    if non_zero_values:
                        self._logger.debug("Non zero priorities for %s : %s", status.info_hash, non_zero_values)

    def update_torrent_stats(self, torrent_infohash_str, seeding_stats):
        """
        function to update swarm statistics.

        This function called when we get new Downloadstate for active torrents.
        Updated downloadstate (seeding_stats) for a particular torrent is stored here.
        """
        if 'time_seeding' in self.torrents[torrent_infohash_str]['last_seeding_stats']:
            if seeding_stats['time_seeding'] >= self.torrents[torrent_infohash_str][
                    'last_seeding_stats']['time_seeding']:
                self.torrents[torrent_infohash_str]['last_seeding_stats'] = seeding_stats
        else:
            self.torrents[torrent_infohash_str]['last_seeding_stats'] = seeding_stats
