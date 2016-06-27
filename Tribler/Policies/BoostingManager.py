# -*- coding: utf-8 -*-
# Written by Egbert Bouman, Mihai Capotă, Elric Milon, and Ardhi Putra Pratama H
"""Manage boosting of swarms"""
import ConfigParser
import json
import logging
import os
import random
from binascii import hexlify, unhexlify

import libtorrent as lt

from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
from Tribler.Core.Utilities import utilities
from Tribler.Core.Utilities.install_dir import determine_install_dir
from Tribler.Core.simpledefs import DLSTATUS_SEEDING, NTFY_TORRENTS, NTFY_UPDATE, NTFY_CHANNELCAST
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Policies.BoostingSource import ChannelSource
from Tribler.Policies.BoostingSource import DirectorySource
from Tribler.Policies.BoostingSource import RSSFeedSource
from Tribler.dispersy.taskmanager import TaskManager

NUMBER_TYPES = (int, long, float)

# CONFIG_FILE = "boosting.ini"
TRIBLER_ROOT = determine_install_dir()
CONFIG_FILE = os.path.join(TRIBLER_ROOT, "boosting.ini")


def levenshtein_dist(t1_fname, t2_fname):
    """
    Calculates the Levenshtein distance between a and b.
    """
    len_t1_fname, len_t2_fname = len(t1_fname), len(t2_fname)
    if len_t1_fname > len_t2_fname:
        # Make sure len_t1_fname <= len_t2_fname, to use O(min(len_t1_fname,len_t2_fname)) space
        t1_fname, t2_fname = t2_fname, t1_fname
        len_t1_fname, len_t2_fname = len_t2_fname, len_t1_fname

    current = range(len_t1_fname + 1)
    for i in range(1, len_t2_fname + 1):
        previous, current = current, [i] + [0] * len_t1_fname
        for j in range(1, len_t1_fname + 1):
            add, delete = previous[j] + 1, current[j - 1] + 1
            change = previous[j - 1]
            if t1_fname[j - 1] != t2_fname[i - 1]:
                change += 1
            current[j] = min(add, delete, change)

    return current[len_t1_fname]

def source_to_string(source_obj):
    return hexlify(source_obj) if len(source_obj) == 20 and not (source_obj.startswith('http://')
                                                                 or source_obj.startswith('https://')) else source_obj

def string_to_source(source_str):
    return source_str.decode('hex') \
        if len(source_str) == 40 and not (os.path.isdir(source_str) or source_str.startswith('http://')) else source_str

class BoostingPolicy(object):
    """
    Base class for determining what swarm selection policy will be applied
    """

    def __init__(self, session):
        self.session = session
        self.key = lambda x: None
        # function that checks if key can be applied to torrent
        self.key_check = lambda x: False
        self.reverse = None

        self._logger = logging.getLogger(self.__class__.__name__)

    def apply(self, torrents, max_active, force=False):
        """
        apply the policy to the torrents stored
        """
        sorted_torrents = sorted([torrent for torrent in torrents.itervalues()
                                  if self.key_check(torrent)],
                                 key=self.key, reverse=self.reverse)

        torrents_start = []
        for torrent in sorted_torrents[:max_active]:
            if not self.session.get_download(torrent["metainfo"].get_infohash()):
                torrents_start.append(torrent)
        torrents_stop = []
        for torrent in sorted_torrents[max_active:]:
            if self.session.get_download(torrent["metainfo"].get_infohash()):
                torrents_stop.append(torrent)

        if force:
            return torrents_start, torrents_stop

        # if both results are empty for some reason (e.g, key_check too restrictive)
        # or torrent started less than half available torrent (try to keep boosting alive)
        # if it's already random, just let it be
        if not isinstance(self, RandomPolicy) and ((not torrents_start and not torrents_stop) or
                                                   (len(torrents_start) < len(torrents) / 2 and len(
                                                       torrents_start) < max_active / 2)):
            self._logger.error("Start and stop torrent list are empty. Fallback to Random")
            # fallback to random policy
            torrents_start, torrents_stop = RandomPolicy(self.session).apply(torrents, max_active)

        return torrents_start, torrents_stop


class RandomPolicy(BoostingPolicy):
    """
    A credit mining policy that chooses swarm randomly
    """
    def __init__(self, session):
        BoostingPolicy.__init__(self, session)
        self.key = lambda v: random.random()
        self.key_check = lambda v: True
        self.reverse = False


class CreationDatePolicy(BoostingPolicy):
    """
    A credit mining policy that chooses swarm by its creation date

    The idea is, older swarm need to be boosted.
    """
    def __init__(self, session):
        BoostingPolicy.__init__(self, session)
        self.key = lambda v: v['creation_date']
        self.key_check = lambda v: v['creation_date'] > 0
        self.reverse = True


class SeederRatioPolicy(BoostingPolicy):
    """
    Default policy. Find the most underseeded swarm to boost.
    """
    def __init__(self, session):
        BoostingPolicy.__init__(self, session)
        self.key = lambda v: v['num_seeders'] / float(v['num_seeders'] +
                                                      v['num_leechers'])
        self.key_check = lambda v: isinstance(v['num_seeders'], NUMBER_TYPES) and isinstance(
            v['num_leechers'], NUMBER_TYPES) and v['num_seeders'] + v['num_leechers'] > 0
        self.reverse = False


class BoostingSettings(object):
    """
    Class contains settings on boosting manager
    """
    def __init__(self, session, policy=SeederRatioPolicy):
        self.session = session

        self.config_file = CONFIG_FILE
        self.max_torrents_active = 30
        self.max_torrents_per_source = 100
        self.source_interval = 20
        self.swarm_interval = 20
        self.initial_swarm_interval = 30
        self.policy = policy(session)
        self.tracker_interval = 50
        self.initial_tracker_interval = 25
        self.logging_interval = 40
        self.initial_logging_interval = 20

        self.min_connection_start = 5
        self.min_channels_start = 100

        self.share_mode_target = 2
        self.credit_mining_path = os.path.join(DefaultDownloadStartupConfig.getInstance().get_dest_dir(),
                                               "credit_mining")


class BoostingManager(TaskManager):
    """
    Class to manage all the credit mining activities
    """

    __single = None

    def __init__(self, session, settings=None):
        super(BoostingManager, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        BoostingManager.__single = self

        self._saved_attributes = ["max_torrents_per_source",
                                  "max_torrents_active", "source_interval",
                                  "swarm_interval", "share_mode_target",
                                  "tracker_interval", "logging_interval"]

        self.session = session
        assert self.session.get_libtorrent()

        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        self.channelcast_db = self.session.open_dbhandler(NTFY_CHANNELCAST)

        # use provided settings or a default one
        self.settings = settings or BoostingSettings(session)

        if not os.path.exists(self.settings.credit_mining_path):
            os.makedirs(self.settings.credit_mining_path)

        self.boosting_sources = {}
        self.torrents = {}

        local_settings = {}
        local_settings['share_mode_target'] = self.settings.share_mode_target
        self.session.lm.ltmgr.get_session().set_settings(local_settings)

        if os.path.exists(self.settings.config_file):
            self._logger.info("Config file %s", open(self.settings.config_file).read())
            self.load_config()
        else:
            self._logger.warning("Initial config file missing")

        self.session.add_observer(self.on_torrent_notify, NTFY_TORRENTS, [NTFY_UPDATE])

        # TODO(emilon): Refactor this to use taskmanager
        self.session.lm.threadpool.add_task(self._select_torrent, self.settings.initial_swarm_interval,
                                            "CreditMining_select_init")
        self.session.lm.threadpool.add_task(self.scrape_trackers,
                                            self.settings.initial_tracker_interval, "CreditMining_scrape")
        self.session.lm.threadpool.add_task(self.log_statistics,
                                            self.settings.initial_logging_interval, "CreditMining_log_init")

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
        save configuration before stopping stuffs
        """
        self.save_config()
        self._logger.info("Shutting down boostingmanager")

        for sourcekey in self.boosting_sources.keys():
            self.remove_source(sourcekey)

        if self.session.lm.threadpool.is_pending_task_active("CreditMining_select_init"):
            self.session.lm.threadpool.cancel_pending_task("CreditMining_select_init")
        if self.session.lm.threadpool.is_pending_task_active("CreditMining_scrape"):
            self.session.lm.threadpool.cancel_pending_task("CreditMining_scrape")
        if self.session.lm.threadpool.is_pending_task_active("CreditMining_log_init"):
            self.session.lm.threadpool.cancel_pending_task("CreditMining_log_init")

        self.cancel_all_pending_tasks()
        # for torrent in self.torrents.itervalues():
        #     self.stop_download(torrent)

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
        then insert it to our data
        """
        def compare_torrents(torrent_1, torrent_2):
            """
            comparing swarms. We don't want to download same swarm with different infohash
            :return: whether those t1 and t2 similar enough
            """
            files1 = [files for files in torrent_1['metainfo'].get_files_with_length() if files[1] > 1024 * 1024]
            files2 = [files for files in torrent_2['metainfo'].get_files_with_length() if files[1] > 1024 * 1024]

            if len(files1) == len(files2):
                for ft1 in files1:
                    for ft2 in files2:
                        if ft1[1] != ft2[1] or levenshtein_dist(ft1[0], ft2[0]) > 5:
                            return False
                return True
            return False

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

        self.session.lm.threadpool.add_task(self.scrape_trackers, self.settings.tracker_interval, "CreditMining_scrape")

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
        def do_start():
            """
            add the actual torrent to the manager to download it later
            :return:
            """
            dscfg = DownloadStartupConfig()
            dscfg.set_dest_dir(self.settings.credit_mining_path)
            dscfg.set_safe_seeding(False)

            preload = torrent.get('preload', False)

            # not using Session.start_download because we need to specify pstate
            if self.session.lm.download_exists(torrent["metainfo"].get_infohash()):
                self._logger.error("Already downloading %s. Cancel start_download",
                                   hexlify(torrent["metainfo"].get_infohash()))
                return

            self._logger.info("Starting %s preload %s has pstate %s",
                              hexlify(torrent["metainfo"].get_infohash()), preload,
                              True if torrent.get('pstate', None) else False)

            torrent['download'] = self.session.lm.add(torrent['metainfo'], dscfg, pstate=torrent.get('pstate', None),
                                                      hidden=True, share_mode=not preload, checkpoint_disabled=True)
            torrent['download'].set_priority(torrent.get('prio', 1))

        self.session.lm.threadpool.add_task_in_thread(do_start, 0)

    def stop_download(self, torrent):
        """
        Stopping torrent that currently downloading
        """

        def do_stop():
            """
            The actual function to stop torrent downloading
            :return:
            """
            ihash = lt.big_number(torrent["metainfo"].get_infohash())
            self._logger.info("Stopping %s", str(ihash))
            download = torrent.pop('download', False)
            lt_torrent = self.session.lm.ltmgr.get_session().find_torrent(ihash)
            if download and lt_torrent.is_valid():
                self._logger.debug("Writing resume data")
                torrent['pstate'] = {'engineresumedata': download.write_resume_data()}
                self.session.remove_download(download, hidden=True)

        self.session.lm.threadpool.add_task_in_thread(do_stop, 0)

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

        self.session.lm.threadpool.add_task(self._select_torrent, self.settings.swarm_interval)

    def load_config(self):
        """
        load config in file configuration and apply it to manager
        """
        config = ConfigParser.ConfigParser()
        config.read(self.settings.config_file)
        validate_source = lambda source_str: unhexlify(source_str) if len(source_str) == 40 and \
                                                                      not source_str.startswith("http") else source_str

        def _add_sources(value):
            """
            adding sources in configuration file
            """
            for boosting_source in json.loads(value):
                boosting_source = validate_source(boosting_source)
                self.add_source(boosting_source)

        def _archive_sources(value):
            """
            setting archive to sources
            """
            for archive_source in json.loads(value):
                archive_source = validate_source(archive_source)
                self.set_archive(archive_source, True)

        def _set_enable_boosting(value, enabled):
            """
            set disable/enable source
            """
            for boosting_source in json.loads(value):
                boosting_source = validate_source(boosting_source)
                if not self.boosting_sources[boosting_source]:
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

        switch_policy = {
            "random" : RandomPolicy,
            "creation" : CreationDatePolicy,
            "seederratio" : SeederRatioPolicy
        }

        for k, val in config.items(__name__):
            try:
                if k in self._saved_attributes:
                    object.__setattr__(self.settings, k, int(val))
                elif k == "policy":
                    self.settings.policy = switch_policy[val](self.session)
                else:
                    switch[k]["cmd"](*((switch[k]['args'][0] or val,) + switch[k]['args'][1:]))
            except KeyError:
                self._logger.error("Key %s can't be applied", k)

    def save_config(self):
        """
        save the environment parameters in config file
        """
        config = ConfigParser.ConfigParser()
        config.add_section(__name__)
        for k in self._saved_attributes:
            config.set(__name__, k, BoostingSettings.__getattribute__(self.settings, k))

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

        config.set(__name__, "boosting_sources", json.dumps(lboosting_sources))
        config.set(__name__, "boosting_enabled", json.dumps(flag_enabled_sources))
        config.set(__name__, "boosting_disabled", json.dumps(flag_disabled_sources))
        if archive_sources:
            config.set(__name__, "archive_sources", json.dumps(archive_sources))

        policy = "None"
        if isinstance(self.settings.policy, RandomPolicy):
            policy = "random"
        elif isinstance(self.settings.policy, CreationDatePolicy):
            policy = "creation"
        elif isinstance(self.settings.policy, SeederRatioPolicy):
            policy = "seederratio"
        config.set(__name__, "policy", policy)
        with open(self.settings.config_file, "w") as configf:
            config.write(configf)

    def log_statistics(self):
        """Log transfer statistics"""
        lt_torrents = self.session.lm.ltmgr.get_session().get_torrents()

        for lt_torrent in lt_torrents:
            status = lt_torrent.status()

            if unhexlify(str(status.info_hash)) in self.torrents:
                self._logger.debug("Status for %s : %s %s | ul_lim : %d, max_ul %d, maxcon %d", status.info_hash,
                                   status.all_time_download,
                                   status.all_time_upload)

                # piece_priorities will fail in libtorrent 1.0.9
                if lt.version == '1.0.9.0':
                    continue
                else:
                    non_zero_values = []
                    for piece_priority in lt_torrent.piece_priorities():
                        if piece_priority != 0:
                            non_zero_values.append(piece_priority)
                    if non_zero_values:
                        self._logger.debug("Non zero priorities for %s : %s", status.info_hash, non_zero_values)

        self.session.lm.threadpool.add_task(self.log_statistics, self.settings.logging_interval)

    def update_torrent_stats(self, torrent_infohash_str, seeding_stats):
        """
        function to update swarm statistics
        """
        if 'time_seeding' in self.torrents[torrent_infohash_str]['last_seeding_stats']:
            if seeding_stats['time_seeding'] >= self.torrents[torrent_infohash_str][
                    'last_seeding_stats']['time_seeding']:
                self.torrents[torrent_infohash_str]['last_seeding_stats'] = seeding_stats
        else:
            self.torrents[torrent_infohash_str]['last_seeding_stats'] = seeding_stats
