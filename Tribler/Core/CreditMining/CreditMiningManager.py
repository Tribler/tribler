from __future__ import absolute_import
from __future__ import division

import logging
import os
import time
from binascii import hexlify, unhexlify
from glob import glob

import psutil

from six import string_types

from twisted.internet.defer import Deferred, DeferredList, succeed
from twisted.internet.task import LoopingCall

from Tribler.Core.CreditMining.CreditMiningPolicy import InvestmentPolicy, MB
from Tribler.Core.CreditMining.CreditMiningSource import ChannelSource
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo
from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_STOPPED, \
    DLSTATUS_STOPPED_ON_ERROR, DOWNLOAD, NTFY_CREDIT_MINING, NTFY_ERROR, UPLOAD
from Tribler.pyipv8.ipv8.taskmanager import TaskManager


class CreditMiningTorrent(object):
    """
    Wrapper class for Credit Mining download
    """
    def __init__(self, infohash, name, download=None, state=None):
        self.infohash = infohash
        self.name = name
        self.download = download
        self.state = state
        self.sources = set()
        self.force_checked = False
        self.to_start = False
        self.start_time = time.time()
        self.mining_state = {}

    def get_storage(self):
        """ Returns the total and used storage of the torrent."""
        full_size = self.download.get_def().get_length()
        progress = self.download.get_state().get_progress()
        return full_size, progress * full_size


class CreditMiningSettings(object):
    """
    This class contains settings used by the credit mining manager
    """
    def __init__(self, config=None):
        self.max_torrents_active = 8
        self.max_torrents_listed = 100
        # Note: be sure to set this interval to something that gives torrents a fair chance of
        # discovering peers and uploading data
        self.auto_manage_interval = 120
        self.hops = 1
        # Maximum number of bytes of disk space that credit mining is allowed to use.
        self.max_disk_space = config.get_credit_mining_disk_space() if config else 50 * 1024 ** 3
        self.low_disk_space = 1000 * 1024 ** 2
        self.save_path = os.path.join(config.get_default_destination_dir(), 'credit_mining')


class CreditMiningManager(TaskManager):
    """
    Class to manage all the credit mining activities
    """

    def __init__(self, session, settings=None, policies=None):
        super(CreditMiningManager, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info('Starting CreditMiningManager')

        self.session = session
        self.settings = settings or CreditMiningSettings(session.config)

        self.sources = {}
        self.torrents = {}
        self.policies = []
        self.upload_mode = False

        # Our default policy [2019-01-24]: torrents are selected based on investment policy
        self.policies = policies or [InvestmentPolicy()]

        if not os.path.exists(self.settings.save_path):
            os.makedirs(self.settings.save_path)

        self.register_task('check_disk_space', LoopingCall(self.check_disk_space)).start(30, now=False)
        self.select_lc = self.register_task('select_torrents', LoopingCall(self.select_torrents))
        self.num_checkpoints = len(glob(os.path.join(self.session.get_downloads_pstate_dir(), '*.state')))

        def add_sources(_):
            for source in self.session.config.get_credit_mining_sources():
                self.add_source(source)

        self.session_ready = Deferred().addCallback(add_sources)

    def shutdown(self, remove_downloads=False):
        """
        Shutting down credit mining manager. It also stops and remove all the sources.
        """
        self._logger.info('Shutting down CreditMiningManager')

        deferreds = [self.remove_source(source) for source in self.sources.keys()] if remove_downloads else []

        self.shutdown_task_manager()

        return DeferredList(deferreds)

    def get_free_disk_space(self):
        return psutil.disk_usage(self.settings.save_path).free

    def check_mining_directory(self):
        # Check that credit mining directory exists, if not try to re-create it.
        if not os.path.exists(self.settings.save_path):
            try:
                os.makedirs(self.settings.save_path)
                error_message = u"Credit mining directory [%s]  does not exist. Tribler will re-create the " \
                                u"directory and resume again.<br/>If you wish to disable credit mining entirely, " \
                                u"please go to Settings >> ANONYMITY >> Token mining. " % \
                                self.settings.save_path.encode('utf-8')
            except OSError:
                self.shutdown()
                error_message = u"Credit mining directory [%s] was deleted or does not exist and Tribler could not " \
                                u"re-create the directory again. Credit mining will shutdown. Try restarting " \
                                u"Tribler. <br/>If you wish to disable credit mining entirely, please go to " \
                                u"Settings >> ANONYMITY >> Token mining. " % self.settings.save_path.encode('utf-8')

            gui_message = {"message": error_message}
            self.session.notifier.notify(NTFY_CREDIT_MINING, NTFY_ERROR, None, gui_message)
            return False
        return True

    def check_disk_space(self):
        if not self.check_mining_directory():
            return

        # Note that we have a resource monitor that monitors the disk where the state-directory resides.
        # However, since the credit mining directory can be on a different disk, we query the disk space ourselves.
        is_low = self.get_free_disk_space() < self.settings.low_disk_space
        if self.upload_mode != is_low:
            self._logger.info('Setting upload mode to %s', is_low)

            self.upload_mode = is_low

            def set_upload_mode(handle):
                handle.set_upload_mode(is_low)

            for download in self.session.get_downloads():
                if download.get_credit_mining():
                    download.get_handle().addCallback(set_upload_mode)

    def add_source(self, source_str):
        """
        Add new source to the credit mining manager
        """
        if source_str not in self.sources:
            num_torrents = len(self.torrents)

            if isinstance(source_str, string_types) and len(source_str) == 40:
                source = ChannelSource(self.session, source_str, self.on_torrent_insert)
            else:
                self._logger.error('Cannot add unknown source %s', source_str)
                return

            self.sources[source_str] = source
            source.start()
            self._logger.info('Added source %s', source_str)

            # If we don't have any torrents and the select LoopingCall is running, stop it.
            # It will restart immediately after we have enough torrents.
            if num_torrents == 0 and self.select_lc.running:
                self.select_lc.stop()
        else:
            self._logger.info('Already have source %s', source_str)

    def remove_source(self, source_str):
        """
        remove source by stop the downloading and remove its metainfo for all its swarms
        """
        if source_str in self.sources:
            source = self.sources.pop(source_str)
            source.stop()
            self._logger.info('Removed source %s', source_str)

            deferreds = []
            for infohash, torrent in self.torrents.items():
                if source_str in torrent.sources:
                    torrent.sources.remove(source_str)
                    if not torrent.sources:
                        del self.torrents[infohash]

                        if torrent.download:
                            deferreds.append(self.session.remove_download(torrent.download, remove_state=True,
                                                                          remove_content=True, hidden=True))
                            self._logger.info('Removing torrent %s', torrent.infohash)
            self._logger.info('Removing %s download(s)', len(deferreds))

            self.cancel_all_pending_tasks()

            return DeferredList(deferreds)

        self._logger.error('Cannot remove non-existing source %s', source_str)
        return succeed(None)

    def on_torrent_insert(self, source_str, infohash, name):
        """
        Callback function called by the source when a new torrent is discovered
        """
        self._logger.debug('Received torrent %s from %s', infohash, source_str)

        if source_str not in self.sources:
            self._logger.debug('Skipping torrent %s (unknown source %s)', infohash, source_str)
            return

        # Did we already get this torrent from another source?
        if infohash in self.torrents:
            self.torrents[infohash].sources.add(source_str)
            self._logger.debug('Skipping torrent %s (already known)', infohash)
            return

        # If a download already exists or already has a checkpoint, skip this torrent
        if self.session.get_download(unhexlify(infohash)) or \
           os.path.exists(os.path.join(self.session.get_downloads_pstate_dir(), infohash + '.state')):
            self._logger.debug('Skipping torrent %s (download already running or scheduled to run)', infohash)
            return

        if len(self.torrents) >= self.settings.max_torrents_listed:
            self._logger.debug('Skipping torrent %s (limit reached)', infohash)
            return

        self.torrents[infohash] = CreditMiningTorrent(infohash, name)
        self.torrents[infohash].sources.add(source_str)
        self._logger.info('Starting torrent %s', infohash)

        magnet = u'magnet:?xt=urn:btih:%s&dn=%s' % (infohash, name)

        dl_config = DownloadStartupConfig()
        dl_config.set_hops(self.settings.hops)
        dl_config.set_dest_dir(self.settings.save_path)
        dl_config.set_credit_mining(True)
        dl_config.set_user_stopped(True)

        self.session.lm.add(TorrentDefNoMetainfo(unhexlify(infohash), name, magnet), dl_config, hidden=True)

    def get_reserved_space_left(self):
        # Calculate number of bytes we have left for storing torrent data.
        # We could also get the size of the download directory ourselves (without libtorrent), but depending
        # on the size of the directory and the number of files in it, this could use too many resources.
        bytes_left = self.settings.max_disk_space
        for download in self.session.get_downloads():
            ds = download.get_state()
            if ds.get_status() in [DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING,
                                   DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR]:
                bytes_left -= ds.get_progress() * download.get_def().get_length()
        return bytes_left

    def schedule_new_torrents(self):
        # Storage available for mining
        bytes_left = self.get_reserved_space_left()

        # Determine which torrent to start and which to stop.
        loaded_torrents = [torrent for torrent in self.torrents.values() if torrent.download]
        policy_results = [iter(policy.sort(loaded_torrents)) for policy in self.policies]

        to_start = []
        iterations = 0
        bytes_scheduled = 0
        while iterations - len(to_start) < len(policy_results):
            if len(to_start) >= self.settings.max_torrents_active:
                break

            policy_index = len(to_start) % len(self.policies)
            policy_result = policy_results[policy_index]

            for torrent in policy_result:
                if torrent not in to_start:
                    # We add torrents such that the total bytes of all running torrents is < max_disk_space.
                    bytes_todo = self.policies[policy_index].get_reserved_bytes(torrent)
                    if bytes_left >= bytes_scheduled + bytes_todo:
                        to_start.append(torrent)
                        self.policies[policy_index].schedule(torrent, to_start=True)
                        bytes_scheduled += bytes_todo
                        break
            iterations += 1
        return to_start

    def select_torrents(self):
        """
        Function to select which torrent in the torrent list will be downloaded in the
        next iteration. It depends on the source and applied policy.
        """
        self._logger.info("select torrents")
        if self.policies and self.torrents:

            # Schedule new torrents to start mining
            self.schedule_new_torrents()

            for policy in self.policies:
                self._logger.info("Running policy:%s", policy)
                policy.run()

    def monitor_downloads(self, dslist):
        stopped = 0
        num_downloading = num_seeding = 0
        bytes_downloaded = bytes_uploaded = 0
        for ds in dslist:
            download = ds.get_download()

            if download.get_credit_mining():
                tdef = download.get_def()
                infohash = hexlify(tdef.get_infohash())

                if infohash not in self.torrents:
                    self.torrents[infohash] = CreditMiningTorrent(infohash, tdef.get_name())

                self.torrents[infohash].download = download
                self.torrents[infohash].state = ds

                if ds.get_status() in [DLSTATUS_DOWNLOADING]:
                    num_downloading += 1
                elif ds.get_status() in [DLSTATUS_SEEDING]:
                    num_seeding += 1
                elif ds.get_status() in [DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR]:
                    stopped += 1

                bytes_uploaded += ds.get_total_transferred(UPLOAD)
                bytes_downloaded += ds.get_total_transferred(DOWNLOAD)

                if ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
                    self._logger.error('Got an error for credit mining download %s', infohash)
                    if infohash in self.torrents and not self.torrents[infohash].force_checked:
                        self._logger.info('Attempting to recheck download %s', infohash)
                        download.force_recheck()
                        self.torrents[infohash].force_checked = True

        self._logger.info('Downloading: %d, Uploading: %d, Stopped: %d', num_seeding, num_downloading, stopped)
        self._logger.info('%d active download(s), %.3f MB uploaded, %.3f MB downloaded',
                          num_seeding + num_downloading, bytes_uploaded/MB, bytes_downloaded/MB)

        if not self.session_ready.called and len(dslist) == self.num_checkpoints:
            self.session_ready.callback(None)

        # We start the looping call when all torrents have been loaded
        total = num_seeding + num_downloading + stopped
        if not self.select_lc.running and total >= self.settings.max_torrents_active:
            self.select_lc.start(self.settings.auto_manage_interval, now=True)

        return num_downloading, num_seeding, stopped, bytes_downloaded, bytes_uploaded
