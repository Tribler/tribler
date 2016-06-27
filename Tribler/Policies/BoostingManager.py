# -*- coding: utf-8 -*-
# Written by Egbert Bouman, Mihai Capotă, Elric Milon
# pylint: disable=too-few-public-methods, too-many-instance-attributes
# pylint: disable=too-many-arguments, too-many-branches
"""Manage boosting of swarms"""

import ConfigParser
import HTMLParser
import glob
import json
import logging
import os
import random
import time
import urllib
from binascii import hexlify, unhexlify
from collections import defaultdict
from hashlib import sha1

import libtorrent as lt

from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentDownloadImpl
from Tribler.Core.TorrentChecker import torrent_checker
from Tribler.Core.TorrentChecker.session import MAX_TRACKER_MULTI_SCRAPE
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities import utilities
from Tribler.Core.exceptions import TriblerException
from Tribler.Core.simpledefs import DLSTATUS_SEEDING, NTFY_INSERT, NTFY_SCRAPE, NTFY_TORRENTS, NTFY_UPDATE
from Tribler.Core.version import version_id
from Tribler.Main.Utility.GuiDBTuples import Torrent
from Tribler.Main.Utility.GuiDBHandler import startWorker
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.SearchGridManager import ChannelManager
from Tribler.Utilities.scraper import scrape_tcp, scrape_udp
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.channel.community import ChannelCommunity
from Tribler.dispersy.util import call_on_reactor_thread

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s.%(msecs).03dZ-%(levelname)s-%(message)s",
    datefmt="%Y%m%dT%H%M%S")
formatter.converter = time.gmtime
handler = logging.FileHandler("boosting.log", mode="w")
handler.setFormatter(formatter)
logger.addHandler(handler)

# logging.getLogger(TimedTaskQueue.__name__+"BoostingManager").setLevel(
#            logging.DEBUG)

number_types = (int, long, float)

# CONFIG_FILE = "boosting.ini"

from Tribler.Core.Utilities.install_dir import determine_install_dir
TRIBLER_ROOT = determine_install_dir()
CONFIG_FILE = os.path.join(TRIBLER_ROOT, "boosting.ini")

def lev(a, b):
    "Calculates the Levenshtein distance between a and b."
    n, m = len(a), len(b)
    if n > m:
        # Make sure n <= m, to use O(min(n,m)) space
        a, b = b, a
        n, m = m, n

    current = range(n + 1)
    for i in range(1, m + 1):
        previous, current = current, [i] + [0] * n
        for j in range(1, n + 1):
            add, delete = previous[j] + 1, current[j - 1] + 1
            change = previous[j - 1]
            if a[j - 1] != b[i - 1]:
                change = change + 1
            current[j] = min(add, delete, change)

    return current[n]


class BoostingPolicy(object):

    def __init__(self, session):
        self.session = session
        self.key = lambda x: None
        # function that checks if key can be applied to torrent
        self.key_check = lambda x: None
        self.reverse = None

    def apply(self, torrents, max_active):
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

        # if both results are empty for some reason (e.g, key_check too restrictive)
        # or torrent started less than half available torrent (try to keep boosting alive)
        # if it's already random, just let it be
        if not isinstance(self, RandomPolicy) and ((not torrents_start and not torrents_stop) or
                (len(torrents_start) < len(torrents)/2 and len(torrents_start) < max_active/2)):
            logger.error("Start and stop torrent list are empty. Fallback to Random")
            # fallback to random policy
            rp = RandomPolicy(self.session)
            torrents_start, torrents_stop = rp.apply(torrents, max_active)

        return torrents_start, torrents_stop


class RandomPolicy(BoostingPolicy):

    def __init__(self, session):
        BoostingPolicy.__init__(self, session)
        self.key = lambda v: random.random()
        self.key_check = lambda v: True
        self.reverse = False


class CreationDatePolicy(BoostingPolicy):

    def __init__(self, session):
        BoostingPolicy.__init__(self, session)
        self.key = lambda v: v['creation_date']
        self.key_check = lambda v: v['creation_date'] > 0
        self.reverse = True


class SeederRatioPolicy(BoostingPolicy):

    def __init__(self, session):
        BoostingPolicy.__init__(self, session)
        self.key = lambda v: v['num_seeders'] / float(v['num_seeders'] +
                                                      v['num_leechers'])
        self.key_check = lambda v: isinstance(v['num_seeders'], number_types) and isinstance(v['num_leechers'], number_types) and v['num_seeders'] + v['num_leechers'] > 0
        self.reverse = False


class BoostingManager(TaskManager):

    __single = None

    def __init__(self, session, utility=None, policy=SeederRatioPolicy, src_interval=20, sw_interval=20,
                 max_per_source=100, max_active=2, config_file=CONFIG_FILE):
        super(BoostingManager, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        BoostingManager.__single = self
        self.gui_util = GUIUtility.getInstance(utility)
        if not self.gui_util.registered:
            self.gui_util.register()

        self.config_file = config_file

        self._saved_attributes = ["max_torrents_per_source",
                                  "max_torrents_active", "source_interval",
                                  "swarm_interval", "share_mode_target",
                                  "tracker_interval", "logging_interval"]

        self.session = session
        self.utility = utility
        self.credit_mining_path = os.path.join(DefaultDownloadStartupConfig.getInstance().get_dest_dir(), "credit_mining")

        if not os.path.exists(self.credit_mining_path):
            os.mkdir(self.credit_mining_path)

        self.boosting_sources = {}
        self.torrents = {}
        self.policy = None
        self.share_mode_target = 2

        # change some params here, if you want
        self.max_torrents_per_source = max_per_source
        self.max_torrents_active = max_active
        self.source_interval = src_interval
        self.swarm_interval = sw_interval
        self.initial_swarm_interval = 30
        self.policy = policy(self.session)
        self.tracker_interval = 50
        self.initial_tracker_interval = 25
        self.logging_interval = 40
        self.initial_logging_interval = 20

        self.set_share_mode_params(share_mode_target=self.share_mode_target)

        if os.path.exists(config_file):
            logger.info("Config file %s", open(config_file).read())
            self.load_config()
        else:
            logger.warning("Initial config file missing")

        self.session.add_observer(self.OnTorrentNotify, NTFY_TORRENTS, [NTFY_UPDATE])


        # TODO(emilon): Refactor this to use taskmanager
        self.session.lm.threadpool.add_task(self._select_torrent, self.initial_swarm_interval)
        self.session.lm.threadpool.add_task(self.scrape_trackers,
                                            self.initial_tracker_interval)
        self.session.lm.threadpool.add_task(self.log_statistics,
                                            self.initial_logging_interval)

    def get_instance(*args, **kw):
        if BoostingManager.__single is None:
            BoostingManager(*args, **kw)
        return BoostingManager.__single
    get_instance = staticmethod(get_instance)

    def del_instance():
        BoostingManager.__single = None
    del_instance = staticmethod(del_instance)

    def shutdown(self):
        # save configuration before stopping stuffs
        self.save_config()

        for torrent in self.torrents.itervalues():
            self.stop_download(torrent)

    def get_source_object(self, sourcekey):
        return self.boosting_sources.get(sourcekey, None)

    def set_enable_mining(self, source, mining_bool=True, force_restart=False):
        """
        Dynamically enable/disable mining source.
        :param source: source, perhaps a url, byte-channelid, or directory
        :param mining_bool: enable/disable
        :param force_restart: do we really need to restart the mining?
        """

        # Flag : there are not any swarm stored for this source
        tor_not_exist = True

        for ihash, tor in self.torrents.iteritems():
            if tor['source'] == source:
                tor_not_exist = False
                self.torrents[ihash]['enabled'] = mining_bool

                # pause torrent download from disabled source
                if (not mining_bool):
                    self.stop_download(tor)

        # this only happen via new channel boosting interface. (CreditMiningPanel)
        # case : just start mining a particular source (e.g. PreviewChannel)
        if tor_not_exist and mining_bool and not (source in self.boosting_sources.keys()):
            self.add_source(source)
            self.set_archive(source, False)
            self.set_enable_mining(source, mining_bool)

        string_to_source = lambda s: s.decode('hex') if len(s) == 40 and not (os.path.isdir(s) or s.startswith('http://')) else s
        self.boosting_sources[string_to_source(source)].enabled = mining_bool

        logger.info("Set mining source %s %s", source, mining_bool)

        if force_restart:
            self._select_torrent()

    def save(self):
        if self.utility:
            try:
                source_to_string = lambda s: s.encode('hex') if len(s) == 20 and not (os.path.isdir(s) or s.startswith('http://')) else s
                self.utility.write_config(
                    'boosting_sources',
                    json.dumps([source_to_string(source) for
                                source in self.boosting_sources.keys()]),
                    flush=True)
                logger.info("Saved sources %s", self.boosting_sources.keys())
            except:
                logger.exception("Could not save state")

    def set_share_mode_params(self, share_mode_target=None, share_mode_bandwidth=None, share_mode_download=None, share_mode_seeders=None):

        # make set_settings call consistent
        settings = {}
        if share_mode_target is not None:
            settings['share_mode_target'] = share_mode_target
        if share_mode_bandwidth is not None:
            settings['share_mode_bandwidth'] = share_mode_bandwidth
        if share_mode_download is not None:
            settings['share_mode_download'] = share_mode_download
        if share_mode_seeders is not None:
            settings['share_mode_seeders'] = share_mode_seeders
        self.session.lm.ltmgr.get_session().set_settings(settings)

    def add_source(self, source):
        if source not in self.boosting_sources:
            args = (self.session, self.session.lm.threadpool, source, self.source_interval, self.max_torrents_per_source, self.on_torrent_insert)
                # pylint: disable=star-args

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
                logger.error("Cannot add unknown source %s", source)
                return

            logger.info("Added source %s", source)
        else:
            logger.info("Already have source %s", source)

    def remove_source(self, source_key):
        if source_key in self.boosting_sources:
            source = self.boosting_sources.pop(source_key)
            source.kill_tasks()
            logger.info("Removed source %s", source_key)

            rm_torrents = [torrent for _, torrent in self.torrents.items() if torrent['source'] == source_key]
            map(self.stop_download,rm_torrents)
            logger.info("Torrents download stopped")

            map(lambda x:self.torrents.pop(x["metainfo"].get_infohash(), None), rm_torrents)
            logger.info("Removing from possible swarms")

    def compare_torrents(self, t1, t2):
        """
        comparing swarms. We don't want to download same swarm with different infohash
        :return: whether those t1 and t2 similar enough
        """
        # pylint: disable=no-self-use, bad-builtin
        try:
            ff = lambda ft: ft[1] > 1024 * 1024
            files1 = filter(ff, t1['metainfo'].get_files_with_length())
            files2 = filter(ff, t2['metainfo'].get_files_with_length())

            if len(files1) == len(files2):
                for ft1 in files1:
                    for ft2 in files2:
                        if ft1[1] != ft2[1] or lev(ft1[0], ft2[0]) > 5:
                            return False
                return True
            return False
        except:
            return False

    def on_torrent_insert(self, source, infohash, torrent):
        """
        This function called when a source finally determined. Fetch some torrents from it,
        then insert it to our data
        :param source:
        :param infohash: torrent infohash
        :param torrent: torrent object (dictionary format)
        :return:
        """
        try:
            isdir = os.path.isdir(source)
        except TypeError:
            isdir = False

        if isdir or source.startswith('http://') or source.startswith('https://'):
            source_str = source
        elif len(source) == 20:
            source_str = source.encode('hex')
        else:
            source_str = 'unknown source'

        # Remember where we got this torrent from
        torrent['source'] = source_str

        boost_source = self.boosting_sources.get(source, None)
        if not boost_source:
            self._logger.info("Dropping torrent insert from removed source: %s" % repr(torrent))
            return
        elif boost_source.archive:
            torrent['preload'] = True
            torrent['prio'] = 100

        # Preload the TorrentDef.
        if not isinstance(torrent.get('metainfo', None), TorrentDef):
            torrent_data = self.session.lm.torrent_store.get(infohash)
            if torrent_data:
                torrent['metainfo'] = TorrentDef.load_from_memory(torrent_data)
            else:
                self._logger.info("Not collected yet: %s %s ", infohash, torrent['name'])
                # TODO(emilon): Handle the case where the torrent hasn't been collected. (collected from the DHT)
                # ardhi : so far, this case won't happen because torrent already defined in _update in BoostingSource
                # torrent['metainfo'] = TorrentDefNoMetainfo(infohash, torrent['name'])
                pass

        # If duplicates exist, set is_duplicate to True, except for the one with the most seeders.
        duplicates = [other for other in self.torrents.values() if self.compare_torrents(torrent, other)]
        if duplicates:
            duplicates += [torrent]
            healthiest_torrent = max([(torrent['num_seeders'], torrent) for torrent in duplicates])[1]
            for duplicate in duplicates:
                is_duplicate = healthiest_torrent != duplicate
                duplicate['is_duplicate'] = is_duplicate
                if is_duplicate and duplicate.get('download', None):
                    self.stop_download(duplicate)

        self.torrents[infohash] = torrent

    def OnTorrentNotify(self, subject, change_type, infohash):
        if infohash not in self.torrents:
            return

        logger.debug("infohash %s updated", hexlify(infohash))

        def do_gui(delayedResult):
            torrent_obj = delayedResult.get()
            infohash_str = torrent_obj.infohash_as_hex

            new_seed = torrent_obj.swarminfo[0]
            new_leecher = torrent_obj.swarminfo[1]

            if new_seed - self.torrents[torrent_obj.infohash]['num_seeders'] \
                    or new_leecher - self.torrents[torrent_obj.infohash]['num_leechers']:
                self.torrents[torrent_obj.infohash]['num_seeders'] = new_seed
                self.torrents[torrent_obj.infohash]['num_leechers'] = new_leecher
                logger.info("infohash %s changed s:%d l:%d", infohash_str, torrent_obj.swarminfo[0],torrent_obj.swarminfo[1])

        startWorker(do_gui, self.gui_util.torrentsearch_manager.getTorrentByInfohash, wargs=(infohash,))


    def scrape_trackers(self):

        for infohash, torrent in self.torrents.iteritems():
            tf = torrent['metainfo']

            # torrent handle
            lt_torrent = self.session.lm.ltmgr.get_session().find_torrent(lt.big_number(infohash))

            # check health(seeder/leecher)
            self.session.lm.torrent_checker.add_gui_request(infohash,True)

            # if lt_torrent.is_valid() \
            #         and unhexlify(str(lt_torrent.status().info_hash)) in self.torrents:
            #     status = lt_torrent.status()
            #
            #     t = self.torrents[unhexlify(str(status.info_hash))]
            #
            #     peer_list = []
            #     for i in lt_torrent.get_peer_info():
            #         peer = LibtorrentDownloadImpl.create_peerlist_data(i)
            #         peer_list.append(peer)
            #
            #     # already downloaded
            #     if 'download' in t:
            #         trackers = t['download'].network_tracker_status()
            #
            #         # find if any tracker is working
            #         trackers_available = any([trackers[i][0] for i in trackers.keys()
            #                                  if i.startswith('udp') or i.startswith('http')])
            #
            #         # we only rely on DHT
            #         if not trackers_available:
            #             #TODO(ardhi) : put some DHT scraper-like
            #             # use DHT data to translate number of seeder/leecher
            #             # t['num_seeders'], t['num_leechers'] = utilities.translate_peers_into_health(peer_list, status)
            #             pass
            #         else:
            #             # scrape again?
            #             lt_torrent.scrape_tracker()
            #
            #         t['num_seeders'], t['num_leechers'] = utilities.translate_peers_into_health(peer_list, status)

        self.session.lm.threadpool.add_task(self.scrape_trackers, self.tracker_interval)

    def set_archive(self, source, enable):
        if source in self.boosting_sources:
            self.boosting_sources[source].archive = enable
            logger.info("Set archive mode for %s to %s", source, enable)
        else:
            logger.error("Could not set archive mode for unknown source %s", source)

    def start_download(self, torrent):
        """
        Start downloading a particular torrent and add it to download list in Tribler
        :param torrent:
        """
        def do_start():
            dscfg = DownloadStartupConfig()
            dscfg.set_dest_dir(self.credit_mining_path)
            dscfg.set_safe_seeding(False)

            # just a debug variable
            tobj = torrent

            preload = tobj.get('preload', False)
            logger.info("Starting %s preload %s has pstate %s" ,
                        hexlify(tobj["metainfo"].get_infohash()),
                         preload, True if tobj.get('pstate', None) else False)

            # not using Session.start_download because we need to specify pstate
            assert self.session.get_libtorrent()

            tobj['download'] = self.session.lm.add(tobj['metainfo'], dscfg, pstate=tobj.get('pstate', None),
                                                      hidden=True, share_mode=not preload, checkpoint_disabled=True)
            tobj['download'].set_priority(tobj.get('prio', 1))

        self.session.lm.threadpool.add_task_in_thread(do_start, 0)

    def stop_download(self, torrent):
        def do_stop():
            ihash = lt.big_number(torrent["metainfo"].get_infohash())
            logger.info("Stopping %s", str(ihash))
            download = torrent.pop('download', False)
            lt_torrent = self.session.lm.ltmgr.get_session().find_torrent(ihash)
            if download and lt_torrent.is_valid():
                logger.debug("Writing resume data")
                torrent['pstate'] = {'engineresumedata': download.write_resume_data()}
                self.session.remove_download(download)

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

        if self.policy is not None and torrents:
            # Determine which torrent to start and which to stop.
            torrents_start, torrents_stop = self.policy.apply(
                torrents, self.max_torrents_active)
            for torrent in torrents_stop:
                self.stop_download(torrent)
            for torrent in torrents_start:
                self.start_download(torrent)

            logger.info("Selecting from %s torrents %s start download", len(torrents), len(torrents_start))

        self.session.lm.threadpool.add_task(self._select_torrent, self.swarm_interval)

    def load_config(self):
        config = ConfigParser.ConfigParser()
        config.read(self.config_file)
        validate_source = lambda s: unhexlify(s) if len(s) == 40 and not s.startswith("http") else s
        for k, v in config.items(__name__):
            if k in self._saved_attributes:
                object.__setattr__(self, k, int(v))
            elif k == "policy":
                if v == "random":
                    self.policy = RandomPolicy(self.session)
                elif v == "creation":
                    self.policy = CreationDatePolicy(self.session)
                elif v == "seederratio":
                    self.policy = SeederRatioPolicy(self.session)
            elif k == "boosting_sources":
                for boosting_source in json.loads(v):
                    boosting_source = validate_source(boosting_source)
                    self.add_source(boosting_source)
            elif k == "archive_sources":
                for archive_source in json.loads(v):
                    archive_source = validate_source(archive_source)
                    self.set_archive(archive_source, True)
            elif k == "boosting_enabled":
                for boosting_source in json.loads(v):
                    boosting_source = validate_source(boosting_source)
                    if not self.boosting_sources[boosting_source]:
                        self.add_source(boosting_source)
                    self.boosting_sources[boosting_source].enabled = True
            elif k == "boosting_disabled":
                for boosting_source in json.loads(v):
                    boosting_source = validate_source(boosting_source)
                    if not self.boosting_sources[boosting_source]:
                        self.add_source(boosting_source)
                    self.boosting_sources[boosting_source].enabled = False

    def save_config(self):
        config = ConfigParser.ConfigParser()
        config.add_section(__name__)
        for k in self._saved_attributes:
            config.set(__name__, k, BoostingManager.__getattribute__(self, k))

        source_to_string = lambda s: hexlify(s) if len(s) == 20 and not (s.startswith('http://') or s.startswith('https://')) else s

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

        if isinstance(self.policy, RandomPolicy):
            policy = "random"
        elif isinstance(self.policy, CreationDatePolicy):
            policy = "creation"
        elif isinstance(self.policy, SeederRatioPolicy):
            policy = "seederratio"
        config.set(__name__, "policy", policy)
        with open(self.config_file, "w") as configf:
            config.write(configf)

    def log_statistics(self):
        """Log transfer statistics"""
        lt_torrents = self.session.lm.ltmgr.get_session().get_torrents()

        for lt_torrent in lt_torrents:
            status = lt_torrent.status()

            if unhexlify(str(status.info_hash)) in self.torrents:
                t = self.torrents[unhexlify(str(status.info_hash))]

                logger.debug("Status for %s : %s %s | ul_lim : %d, max_ul %d, maxcon %d", status.info_hash,
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
                        logger.debug("Non zero priorities for %s : %s",
                                     status.info_hash, non_zero_values)

        self.session.lm.threadpool.add_task(self.log_statistics, self.logging_interval)

    def update_torrent_stats(self, torrent_infohash_str, seeding_stats):
        if 'time_seeding' in self.torrents[torrent_infohash_str]['last_seeding_stats']:
            if seeding_stats['time_seeding'] >= self.torrents[torrent_infohash_str]['last_seeding_stats']['time_seeding']:
                self.torrents[torrent_infohash_str]['last_seeding_stats'] = seeding_stats
        else:
            self.torrents[torrent_infohash_str]['last_seeding_stats'] = seeding_stats


class BoostingSource(object):

    def __init__(self, session, tqueue, source, interval, max_torrents, callback):
        self.session = session
        self.session.lm.threadpool = tqueue
        self.channelcast_db = session.lm.channelcast_db

        self.torrents = {}
        self.source = source
        self.interval = interval
        self.max_torrents = max_torrents
        self.callback = callback
        self.archive = False

        self.enabled = True

        self.av_uprate = 0
        self.av_dwnrate = 0
        self.storage_used = 0
        self.ready = False

        self.gui_util = GUIUtility.getInstance()
        if not self.gui_util.registered:
            self.gui_util.register()

        self.boosting_manager = BoostingManager.get_instance()

    def kill_tasks(self):
        self.session.lm.threadpool.cancel_pending_task(self.source)

    def _load_if_ready(self, source):

        nr_channels = self.channelcast_db.getNrChannels()
        nr_connections = 0

        for community in self.session.lm.dispersy.get_communities():
            from Tribler.community.search.community import SearchCommunity
            if isinstance(community, SearchCommunity):
                nr_connections = community.get_nr_connections()

        # condition example
        if nr_channels > 100 and nr_connections > 5:
            fun = self._load
        else:
            fun = self._load_if_ready

        self.session.lm.threadpool.add_task(lambda src=source: fun(src), 15, task_name=str(self.source)+"_load")

    def _load(self, source):
        pass

    def _update(self):
        pass

    def getSource(self):
        return self.source


class ChannelSource(BoostingSource):

    def __init__(self, session, tqueue, dispersy_cid, interval, max_torrents, callback):
        BoostingSource.__init__(self, session, tqueue, dispersy_cid, interval, max_torrents, callback)

        self.channel_id = None

        self.channel = None
        self.community = None
        self.database_updated = True

        self.session.add_observer(self._on_database_updated, NTFY_TORRENTS, [NTFY_INSERT, NTFY_UPDATE])
        self.session.lm.threadpool.add_task(lambda cid=dispersy_cid: self._load_if_ready(cid), 0, task_name=str(self.source)+"_load")

        self.unavail_torrent = {}

    def kill_tasks(self):
        BoostingSource.kill_tasks(self)
        self.session.remove_observer(self._on_database_updated)

    def _load(self, dispersy_cid):
        dispersy = self.session.get_dispersy_instance()

        @call_on_reactor_thread
        def join_community():
            try:
                self.community = dispersy.get_community(dispersy_cid, True)
                self.session.lm.threadpool.add_task(get_channel_id, 0, task_name=str(self.source)+"_get_channel_id")

            except KeyError:

                allchannelcommunity = None
                for community in dispersy.get_communities():
                    if isinstance(community, AllChannelCommunity):
                        allchannelcommunity = community
                        break

                if allchannelcommunity:
                    # pylint: disable=protected-access
                    self.community = ChannelCommunity.init_community(dispersy, dispersy.get_member(mid=dispersy_cid), allchannelcommunity._my_member, True)
                    logger.info("Joined channel community %s",
                                dispersy_cid.encode("HEX"))
                    self.session.lm.threadpool.add_task(get_channel_id, 0, task_name=str(self.source)+"_get_channel_id")
                else:
                    logger.error("Could not find AllChannelCommunity")

        def get_channel_id():
            # pylint: disable=protected-access
            if self.community and self.community._channel_id and self.gui_util.registered:
                self.channel_id = self.community._channel_id

                self.channel = self.gui_util.channelsearch_manager.getChannel(self.channel_id)

                if not self.boosting_manager.is_pending_task_active(str(self.source)+"_update"):
                    self.boosting_manager.register_task(str(self.source)+"_update",LoopingCall(self._update)).start(self.interval, now=True)
                # self.session.lm.threadpool.add_task(self._update, 0, task_name=str(self.source)+"_update")
                logger.info("Got channel id %s", self.channel_id)
            else:
                logger.warning("Could not get channel id, retrying in 10 s")
                self.session.lm.threadpool.add_task(get_channel_id, 10, task_name=str(self.source)+"_get_channel_id")

        try:
            join_community()
            self.ready = True
        except Exception,ex:
            logger.info("Channel %s was not ready, waits for next interval (%d chn)", hexlify(self.source), len(dispersy.get_communities()))
            self.session.lm.threadpool.add_task(lambda cid=dispersy_cid: self._load_if_ready(cid), 0, task_name=str(self.source)+"_load")

    def _check_tor(self):

        def doGui(delayedResult):
            # wait here
            requesttype = delayedResult.get(timeout=70)

        def showTorrent(torrent):
            if (torrent.files):
                infohash = torrent.infohash
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

                # logger.info("Torrent %s from %s ready to start", hexlify(infohash), hexlify(self.source))

                if self.callback:
                    self.callback(self.source, infohash, self.torrents[infohash])
                self.database_updated = False

        logger.info("Unavailable #torrents : %d from %s", len(self.unavail_torrent), hexlify(self.source))

        if len(self.unavail_torrent) and self.enabled:
            for k,t in self.unavail_torrent.items():
                startWorker(doGui, self.gui_util.torrentsearch_manager.loadTorrent,
                            wargs=(t,), wkwargs={'callback': showTorrent})

        # if not self.session.lm.threadpool.is_pending_task_active(hexlify(self.source)+"_checktor"):
        #     self.session.lm.threadpool.add_task(self._check_tor, 100, task_name=hexlify(self.source)+"_checktor")

    def _update(self):
        if len(self.torrents) < self.max_torrents:

            if self.database_updated:

                CHANTOR_DB = ['ChannelTorrents.channel_id', 'Torrent.torrent_id', 'infohash', '""', 'length', 'category', 'status', 'num_seeders', 'num_leechers', 'ChannelTorrents.id', 'ChannelTorrents.dispersy_id', 'ChannelTorrents.name', 'Torrent.name', 'ChannelTorrents.description', 'ChannelTorrents.time_stamp', 'ChannelTorrents.inserted']

                try:
                    torrent_values = self.channelcast_db.getTorrentsFromChannelId(self.channel_id, True, CHANTOR_DB, self.max_torrents)

                    listtor = self.gui_util.channelsearch_manager._createTorrents(torrent_values, True,
                                                 {self.channel_id: self.channelcast_db.getChannel(self.channel_id)})[2]

                    # dict {key_infohash(binary):Torrent(object-GUIDBTuple)}
                    self.unavail_torrent.update({t.infohash:t for t in listtor if t.infohash not in self.torrents})

                    # it's highly probable the checktor function is running at this time (if it's already running)
                    # if not running, start the checker
                    if not self.boosting_manager.is_pending_task_active(hexlify(self.source)+"_checktor"):
                        self.boosting_manager.register_task(hexlify(self.source)+"_checktor",LoopingCall(self._check_tor)).start(100, now=True)

                        # self.session.lm.threadpool.add_task(self._check_tor, 0, task_name=hexlify(self.source)+"_checktor")

                except:
                    logger.info("Channel %s was not ready, waits for next interval", hexlify(self.source))

            # self.session.lm.threadpool.add_task(self._update, self.interval, task_name=str(self.source)+"_update")

    def _on_database_updated(self, subject, change_type, infohash):
        if (subject, change_type, infohash) is None:
            # Unused arguments
            pass
        self.database_updated = True

    def getSource(self):
        return self.channel.name if self.channel else None


class RSSFeedSource(BoostingSource):
    # supported list (tested) :
    # http://bt.etree.org/rss/bt_etree_org.rdf
    # http://www.mininova.org/rss.xml
    # https://kat.cr (via torcache)

    # not supported (till now)
    # https://eztv.ag/ezrss.xml (https link)

    def __init__(self, session, tqueue, rss_feed, interval, max_torrents, callback):
        BoostingSource.__init__(self, session, tqueue, rss_feed, interval, max_torrents, callback)

        self.unescape = HTMLParser.HTMLParser().unescape

        self.feed_handle = None

        self.session.lm.threadpool.add_task(lambda feed=rss_feed: self._load_if_ready(feed), 0, task_name=str(self.source)+"_load")

        self.title = ""
        self.description = ""
        self.total_torrents = 0

    def _load(self, rss_feed):
        self.feed_handle = self.session.lm.ltmgr.get_session().add_feed({'url': rss_feed, 'auto_download': False, 'auto_map_handles': False})

        def wait_for_feed():
            # Wait until the RSS feed is longer updating.
            feed_status = self.feed_handle.get_feed_status()
            if feed_status['updating']:
                self.session.lm.threadpool.add_task(wait_for_feed, 1, task_name=str(self.source)+"_wait_for_feed")
            elif len(feed_status['error']) > 0:
                logger.error("Got error for RSS feed %s : %s",
                             feed_status['url'], feed_status['error'])
                if "503" in feed_status["error"]:
                    time.sleep(5 * random.random())
                    self.feed_handle.update_feed()
                    self.session.lm.threadpool.add_task(wait_for_feed, 1, task_name=str(self.source)+"_wait_for_feed")
            else:
                # The feed is done updating. Now periodically start retrieving torrents.
                self.boosting_manager.register_task(str(self.source)+"_update",LoopingCall(self._update),
                                                    10,interval=self.interval)
                logger.info("Got RSS feed %s", feed_status['url'])

        wait_for_feed()
        self.ready = True

    def _update(self):
        if len(self.torrents) < self.max_torrents:

            feed_status = self.feed_handle.get_feed_status()

            self.title = feed_status['title']
            self.description = feed_status['description']

            torrent_keys = ['name', 'metainfo', 'creation_date', 'length', 'num_files', 'num_seeders', 'num_leechers', 'enabled', 'last_seeding_stats']

            self.total_torrents = len(feed_status['items'])

            def __cb_body(body_bin, item):
                tdef = None
                try:
                    metainfo = lt.bdecode(body_bin)
                    tdef = TorrentDef.load_from_dict(metainfo)
                    tdef.save(torrent_filename)
                except:
                    logger.error("Could not parse/save torrent, skipping %s", torrent_filename)

                if tdef:
                    # Create a torrent dict.
                    torrent_values = [item['title'], tdef, tdef.get_creation_date(), tdef.get_length(), len(tdef.get_files()), -1, -1, self.enabled, {}]
                    self.torrents[sha1(item['url']).digest()] = dict(zip(torrent_keys, torrent_values))

                    # manually generate an ID and put this into DB
                    self.session.lm.torrent_db.addOrGetTorrentID(sha1(item['url']).digest())
                    self.session.lm.torrent_db.addExternalTorrent(tdef)

                    # create Torrent object and store it
                    self.gui_util.torrentsearch_manager.loadTorrent(Torrent.fromTorrentDef(tdef))

                    # Notify the BoostingManager and provide the real infohash.
                    if self.callback:
                        self.callback(self.source, tdef.get_infohash(), self.torrents[sha1(item['url']).digest()])

            def __success_cb(response, item):
                defer = readBody(response)
                defer.addCallback(__cb_body, item)
                return defer

            for item in feed_status['items']:
                # Not all RSS feeds provide us with the infohash, so we use a fake infohash based on the URL to identify the torrents.
                infohash = sha1(item['url']).digest()
                if infohash not in self.torrents:
                    # Store the torrents as rss-infohash_as_hex.torrent.
                    torrent_filename = os.path.join(self.boosting_manager.credit_mining_path, 'rss-%s.torrent' % infohash.encode('hex'))
                    tdef = None
                    if not os.path.exists(torrent_filename):

                        #create Agent to download torrent file
                        agent = Agent(reactor)
                        ses_agent = agent.request(
                            'GET', #http://stackoverflow.com/a/845595
                            urllib.quote(item['url'],safe="%/:=&?~#+!$,;'@()*[]"),
                            Headers({'User-Agent': ['Tribler ' + version_id]}),
                            None)
                        ses_agent.addCallback(__success_cb, item)

                    else:
                        # torrent already exist in our system
                        tdef = TorrentDef.load(torrent_filename)

                        if tdef:
                            # Create a torrent dict.
                            torrent_values = [item['title'], tdef, tdef.get_creation_date(), tdef.get_length(), len(tdef.get_files()), -1, -1, self.enabled, {}]
                            self.torrents[infohash] = dict(zip(torrent_keys, torrent_values))

                            # manually generate an ID and put this into DB
                            self.session.lm.torrent_db.addOrGetTorrentID(infohash)
                            self.session.lm.torrent_db.addExternalTorrent(tdef)

                            # create Torrent object and store it
                            self.gui_util.torrentsearch_manager.loadTorrent(Torrent.fromTorrentDef(tdef))

                            # Notify the BoostingManager and provide the real infohash.
                            if self.callback:
                                self.callback(self.source, tdef.get_infohash(), self.torrents[infohash])

            # self.session.lm.threadpool.add_task(self._update, self.interval, task_name=str(self.source)+"_update")

    def kill_tasks(self):
        BoostingSource.kill_tasks(self)

        #stop updating
        self.session.lm.threadpool.cancel_pending_task(str(self.source)+"_update")


class DirectorySource(BoostingSource):

    def __init__(self, session, tqueue, directory, interval, max_torrents, callback):
        BoostingSource.__init__(self, session, tqueue, directory, interval, max_torrents, callback)
        self._load_if_ready(directory)

    def _load(self, directory):
        if os.path.isdir(directory):
            # Wait for __init__ to finish so the source is registered with the
            # BoostinManager, otherwise adding torrents won't work
            self.session.lm.threadpool.add_task(self._update, 1, task_name=str(self.source)+"_update")
            logger.info("Got directory %s", directory)
            self.ready = True
        else:
            logger.error("Could not find directory %s", directory)

    def _update(self):
        if len(self.torrents) < self.max_torrents:

            torrent_keys = ['name', 'metainfo', 'creation_date', 'length', 'num_files', 'num_seeders', 'num_leechers', 'enabled', 'last_seeding_stats']

            for torrent_filename in glob.glob(self.source + '/*.torrent'):
                if torrent_filename not in self.torrents:
                    try:
                        tdef = TorrentDef.load(torrent_filename)
                    except:
                        logger.error("Could not load torrent, skipping %s",
                                     torrent_filename)
                        continue
                    # Create a torrent dict.
                    torrent_values = [tdef.get_name_as_unicode(), tdef, tdef.get_creation_date(), tdef.get_length(), len(tdef.get_files()), -1, -1, self.enabled, {}]
                    self.torrents[torrent_filename] = dict(zip(torrent_keys, torrent_values))
                    # Notify the BoostingManager.
                    if self.callback:
                        self.callback(self.source, tdef.get_infohash(), self.torrents[torrent_filename])

            self.session.lm.threadpool.add_task(self._update, self.interval, task_name=str(self.source)+"_update")
