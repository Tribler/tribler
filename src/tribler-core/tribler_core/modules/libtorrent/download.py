"""
A wrapper around a libtorrent download.

Author(s): Arno Bakker, Egbert Bouman
"""
import base64
import logging
from asyncio import CancelledError, Future, iscoroutine, sleep, wait_for
from collections import defaultdict
from pathlib import Path

from ipv8.taskmanager import TaskManager, task
from ipv8.util import int2byte, succeed

import libtorrent as lt
from libtorrent import create_torrent

from tribler_common.simpledefs import DLSTATUS_SEEDING, DLSTATUS_STOPPED, DOWNLOAD, NTFY

from tribler_core.exceptions import SaveResumeDataError
from tribler_core.modules.libtorrent import check_handle, require_handle
from tribler_core.modules.libtorrent.download_config import DownloadConfig, get_default_dest_dir
from tribler_core.modules.libtorrent.download_state import DownloadState
from tribler_core.modules.libtorrent.stream import Stream
from tribler_core.modules.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler_core.utilities import path_util
from tribler_core.utilities.osutils import fix_filebasename
from tribler_core.utilities.torrent_utils import get_info_from_handle
from tribler_core.utilities.unicode import ensure_unicode, hexlify
from tribler_core.utilities.utilities import bdecode_compat


class Download(TaskManager):
    """ Download subclass that represents a libtorrent download."""

    def __init__(self, session, tdef, dummy=False):
        super(Download, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        self.dummy = dummy
        self.session = session
        self.config = None
        self.tdef = tdef
        self.handle = None
        self.config = None
        self.state_dir = self.session.config.get_state_dir() if self.session else None
        self.dlmgr = self.session.dlmgr if self.session else None

        # With hidden True download will not be in GET/downloads set, as a result will not be shown in GUI
        self.hidden = False

        # Libtorrent status
        self.lt_status = None
        self.error = None
        self.pause_after_next_hashcheck = False
        self.checkpoint_after_next_hashcheck = False
        self.tracker_status = {}  # {url: [num_peers, status_str]}
        self.checkpoint_disabled = self.dummy

        self.futures = defaultdict(list)
        self.alert_handlers = defaultdict(list)

        self.future_added = self.wait_for_alert('add_torrent_alert', lambda a: a.handle)
        self.future_removed = self.wait_for_alert('torrent_removed_alert')
        self.future_finished = self.wait_for_alert('torrent_finished_alert')
        self.future_metainfo = self.wait_for_alert('metadata_received_alert', lambda a: self.tdef.get_metainfo())

        alert_handlers = {'tracker_reply_alert': self.on_tracker_reply_alert,
                          'tracker_error_alert': self.on_tracker_error_alert,
                          'tracker_warning_alert': self.on_tracker_warning_alert,
                          'metadata_received_alert': self.on_metadata_received_alert,
                          'performance_alert': self.on_performance_alert,
                          'torrent_checked_alert': self.on_torrent_checked_alert,
                          'torrent_finished_alert': self.on_torrent_finished_alert,
                          'save_resume_data_alert': self.on_save_resume_data_alert,
                          'state_changed_alert': self.on_state_changed_alert,
                          'torrent_error_alert': self.on_torrent_error_alert,
                          'add_torrent_alert': self.on_add_torrent_alert,
                          'torrent_removed_alert': self.on_torrent_removed_alert}

        for alert_type, alert_handler in alert_handlers.items():
            self.register_alert_handler(alert_type, alert_handler)
        self.stream = Stream(self)

    def __str__(self):
        return "Download <name: '%s' hops: %d checkpoint_disabled: %d>" % \
               (self.tdef.get_name(), self.config.get_hops(), self.checkpoint_disabled)

    def __repr__(self):
        return self.__str__()

    def get_torrent_data(self):
        """
        Return torrent data, if the handle is valid and metadata is available.
        """
        if not self.handle or not self.handle.is_valid() or not self.handle.has_metadata():
            return None

        torrent_info = get_info_from_handle(self.handle)
        t = create_torrent(torrent_info)
        return t.generate()

    def register_alert_handler(self, alert_type, handler):
        self.alert_handlers[alert_type].append(handler)

    def wait_for_alert(self, success_type, success_getter=None, fail_type=None, fail_getter=None):
        future = Future()
        if success_type:
            self.futures[success_type].append((future, future.set_result, success_getter))
        if fail_type:
            self.futures[fail_type].append((future, future.set_exception, fail_getter))
        return future

    async def wait_for_status(self, *status):
        current = self.get_state().get_status()
        while current not in status:
            await self.wait_for_alert('state_changed_alert')
            current = self.get_state().get_status()

    def get_def(self):
        return self.tdef

    def get_handle(self):
        """
        Returns a deferred that fires with a valid libtorrent download handle.
        """
        if self.handle and self.handle.is_valid():
            return succeed(self.handle)

        return self.wait_for_alert('add_torrent_alert', lambda a: a.handle)

    def setup(self, config=None, hidden=False, checkpoint_disabled=False):
        """
        Create a Download object. Used internally by Session.
        @param config DownloadConfig or None (in which case a new DownloadConfig() is created
        :returns a Deferred to which a callback can be added which returns the result of network_create_engine_wrapper.
        """
        self.hidden = hidden
        self.checkpoint_disabled = checkpoint_disabled or self.dummy
        self.config = config or DownloadConfig(state_dir=self.session.config.get_state_dir())

        self._logger.debug("Setup: %s", hexlify(self.tdef.get_infohash()))

        self.checkpoint()

        atp = {"save_path": path_util.normpath(get_default_dest_dir() / self.config.get_dest_dir()),
               "storage_mode": lt.storage_mode_t.storage_mode_sparse,
               "flags": lt.add_torrent_params_flags_t.flag_paused
                        | lt.add_torrent_params_flags_t.flag_duplicate_is_error
                        | lt.add_torrent_params_flags_t.flag_update_subscribe}

        if self.config.get_share_mode():
            atp["flags"] = atp["flags"] | lt.add_torrent_params_flags_t.flag_share_mode
        if self.config.get_upload_mode():
            atp["flags"] = atp["flags"] | lt.add_torrent_params_flags_t.flag_upload_mode

        resume_data = self.config.get_engineresumedata()
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            metainfo = self.tdef.get_metainfo()
            torrentinfo = lt.torrent_info(metainfo)

            atp["ti"] = torrentinfo
            if resume_data and isinstance(resume_data, dict):
                # Rewrite save_path as a global path, if it is given as a relative path
                if b"save_path" in resume_data and not path_util.isabs(ensure_unicode(resume_data[b"save_path"], 'utf8')):
                    resume_data[b"save_path"] = self.state_dir / ensure_unicode(resume_data[b"save_path"], 'utf8')
                atp["resume_data"] = lt.bencode(resume_data)
        else:
            atp["url"] = self.tdef.get_url() or "magnet:?xt=urn:btih:" + hexlify(self.tdef.get_infohash())
            atp["name"] = self.tdef.get_name_as_unicode()

        return atp

    def on_add_torrent_alert(self, alert):
        if hasattr(alert, 'error') and alert.error.value():
            self._logger.error("Failed to add torrent (%s)", self.tdef.get_name_as_unicode())
            raise RuntimeError(alert.error.message())
        elif not alert.handle.is_valid():
            self._logger.error("Received invalid torrent handle")
            return

        self.handle = alert.handle
        self._logger.debug("Added torrent %s", str(self.handle.info_hash()))

        self.set_selected_files()

        user_stopped = self.config.get_user_stopped()

        # If we lost resume_data always resume download in order to force checking
        if not user_stopped or not self.config.get_engineresumedata():
            self.handle.resume()

            # If we only needed to perform checking, pause download after it is complete
            self.pause_after_next_hashcheck = user_stopped

        # Limit the amount of connections if we have specified that
        self.handle.set_max_connections(self.session.config.get_libtorrent_max_conn_download())

        # Set limit on download for a bootstrap file
        if self.config.get_bootstrap_download():
            self.handle.set_download_limit(self.session.config.get_bootstrap_max_download_rate())

        # By default don't apply the IP filter
        self.apply_ip_filter(False)

        self.checkpoint()

    def get_anon_mode(self):
        return self.config.get_hops() > 0

    @check_handle(b'')
    def get_pieces_base64(self):
        """
        Returns a base64 encoded bitmask of the pieces that we have.
        """
        bitstr = b""
        for bit in self.handle.status().pieces:
            bitstr += b'1' if bit else b'0'

        encoded_str = b""
        for i in range(0, len(bitstr), 8):
            encoded_str += int2byte(int(bitstr[i:i + 8].ljust(8, b'0'), 2))
        return base64.b64encode(encoded_str)

    def post_alert(self, alert_type, alert_dict=None):
        alert_dict = alert_dict or {}
        alert_dict['category'] = lambda _: None
        alert = type('anonymous_alert', (object,), alert_dict)()
        return self.process_alert(alert, alert_type)

    def process_alert(self, alert, alert_type):
        if alert.category() in [lt.alert.category_t.error_notification, lt.alert.category_t.performance_warning]:
            self._logger.debug("Got alert: %s", alert)

        for handler in self.alert_handlers.get(alert_type, []):
            handler(alert)

        for future, future_setter, getter in self.futures.pop(alert_type, []):
            if not future.done():
                future_setter(getter(alert) if getter else alert)

    def on_torrent_error_alert(self, alert):
        self._logger.error("Error during download: %s", alert.error)
        #FIXME Unused notification
        #self.session.notifier.notify(NTFY.TORRENT_ERROR, self.tdef.get_infohash(), alert.error, self.hidden)

    def on_state_changed_alert(self, alert):
        if not self.handle:
            return
        self.update_lt_status(self.handle.status())

        enable = alert.state == lt.torrent_status.seeding and self.config.get_hops() > 0
        self._logger.debug('Setting IP filter for %s to %s', hexlify(self.tdef.get_infohash()), enable)
        self.apply_ip_filter(enable)

        # On a rare occasion we don't get a metadata_received_alert. If this is the case, post an alert manually.
        if alert.state == lt.torrent_status.downloading and isinstance(self.tdef, TorrentDefNoMetainfo):
            self.post_alert('metadata_received_alert')

    def on_save_resume_data_alert(self, alert):
        """
        Callback for the alert that contains the resume data of a specific download.
        This resume data will be written to a file on disk.
        """
        if self.checkpoint_disabled:
            return

        resume_data = alert.resume_data
        # Make save_path relative if the torrent is saved in the Tribler state directory
        if self.state_dir and b'save_path' in resume_data:
            save_path = path_util.abspath(resume_data[b'save_path'].decode('utf8'))
            if save_path.exists() and path_util.issubfolder(self.state_dir, save_path):
                resume_data[b'save_path'] = str(path_util.norm_path(self.state_dir, save_path))

        metainfo = {
            'infohash': self.tdef.get_infohash(),
            'name': self.tdef.get_name_as_unicode(),
            'url': self.tdef.get_url()
        } if isinstance(self.tdef, TorrentDefNoMetainfo) else self.tdef.get_metainfo()

        self.config.set_metainfo(metainfo)
        self.config.set_engineresumedata(resume_data)

        # Save it to file
        basename = hexlify(resume_data[b'info-hash']) + '.conf'
        filename = self.dlmgr.get_checkpoint_dir() / basename
        self.config.config['download_defaults']['name'] = self.tdef.get_name_as_unicode()  # store name (for debugging)
        self.config.write(str(filename))
        self._logger.debug('Saving download config to file %s', filename)

    def on_tracker_reply_alert(self, alert):
        self.tracker_status[alert.url] = [alert.num_peers, 'Working']

    def on_tracker_error_alert(self, alert):
        peers = self.tracker_status[alert.url][0] if alert.url in self.tracker_status else 0
        if alert.msg:
            status = 'Error: ' + alert.msg
        elif alert.status_code > 0:
            status = 'HTTP status code %d' % alert.status_code
        elif alert.status_code == 0:
            status = 'Timeout'
        else:
            status = 'Not working'

        self.tracker_status[alert.url] = [peers, status]

    def on_tracker_warning_alert(self, alert):
        peers = self.tracker_status[alert.url][0] if alert.url in self.tracker_status else 0
        status = 'Warning: ' + str(alert.message())

        self.tracker_status[alert.url] = [peers, status]

    def on_metadata_received_alert(self, _):
        torrent_info = get_info_from_handle(self.handle)
        if not torrent_info:
            return

        metadata = {b'info': bdecode_compat(torrent_info.metadata()), b'leechers': 0, b'seeders': 0}
        trackers = [tracker['url'].encode('utf-8') for tracker in self.handle.trackers()]
        if len(trackers) > 1:
            metadata[b"announce-list"] = [trackers]
        elif trackers:
            metadata[b"announce"] = trackers[0]

        for peer in self.handle.get_peer_info():
            if peer.progress == 1:
                metadata[b"seeders"] += 1
            else:
                metadata[b"leechers"] += 1

        try:
            self.tdef = TorrentDef.load_from_dict(metadata)
        except ValueError as ve:
            self._logger.exception(ve)
            return

        self.set_selected_files()
        self.checkpoint()

    def on_performance_alert(self, alert):
        if self.get_anon_mode() or self.dlmgr.ltsessions is None:
            return

        # When the send buffer watermark is too low, double the buffer size to a
        # maximum of 50MiB. This is the same mechanism as Deluge uses.
        lt_session = self.dlmgr.get_session(self.config.get_hops())
        settings = self.dlmgr.get_session_settings(lt_session)
        if alert.message().endswith("send buffer watermark too low (upload rate will suffer)"):
            if settings['send_buffer_watermark'] <= 26214400:
                self._logger.info("Setting send_buffer_watermark to %s", 2 * settings['send_buffer_watermark'])
                settings['send_buffer_watermark'] *= 2
                self.dlmgr.set_session_settings(self.dlmgr.get_session(), settings)
        # When the write cache is too small, double the buffer size to a maximum
        # of 64MiB. Again, this is the same mechanism as Deluge uses.
        elif alert.message().endswith("max outstanding disk writes reached"):
            if settings['max_queued_disk_bytes'] <= 33554432:
                self._logger.info("Setting max_queued_disk_bytes to %s", 2 * settings['max_queued_disk_bytes'])
                settings['max_queued_disk_bytes'] *= 2
                self.dlmgr.set_session_settings(self.dlmgr.get_session(), settings)

    def on_torrent_removed_alert(self, _):
        self._logger.debug("Removing %s", self.tdef.get_name())
        self.handle = None

    def on_torrent_checked_alert(self, _):
        if self.pause_after_next_hashcheck:
            self.pause_after_next_hashcheck = False
            self.handle.pause()
        if self.checkpoint_after_next_hashcheck:
            self.checkpoint_after_next_hashcheck = False
            self.checkpoint()

    @check_handle()
    def on_torrent_finished_alert(self, _):
        self.update_lt_status(self.handle.status())
        self.checkpoint()
        if self.get_state().get_total_transferred(DOWNLOAD) > 0 \
                and not self.stream.enabled:
            self.session.notifier.notify(NTFY.TORRENT_FINISHED, self.tdef.get_infohash(),
                                         self.tdef.get_name_as_unicode(), self.hidden or
                                         self.config.get_channel_download())

    def update_lt_status(self, lt_status):
        """ Update libtorrent stats and check if the download should be stopped."""
        self.lt_status = lt_status
        self._stop_if_finished()

    def _stop_if_finished(self):
        state = self.get_state()
        if state.get_status() == DLSTATUS_SEEDING:
            mode = self.session.config.get_seeding_mode()
            if mode == 'never' \
                    or (mode == 'ratio' and state.get_seeding_ratio() >= self.session.config.get_seeding_ratio()) \
                    or (mode == 'time' and state.get_seeding_time() >= self.session.config.get_seeding_time()):
                self.stop()

    @check_handle()
    def set_selected_files(self, selected_files=None, prio=4, force=False):
        if not force and self.stream.enabled:
            return
        if not isinstance(self.tdef, TorrentDefNoMetainfo) and not self.get_share_mode():
            if selected_files is None:
                selected_files = self.config.get_selected_files()
            else:
                self.config.set_selected_files(selected_files)

            torrent_info = get_info_from_handle(self.handle)
            if not torrent_info or not hasattr(torrent_info, 'files'):
                self._logger.error("File info not available for torrent %s", hexlify(self.tdef.get_infohash()))
                return

            filepriorities = []
            torrent_storage = torrent_info.files()
            for index, file_entry in enumerate(torrent_storage):
                filepriorities.append(prio if index in selected_files or not selected_files else 0)
            self.set_file_priorities(filepriorities)

    @check_handle(False)
    def move_storage(self, new_dir):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            self.handle.move_storage(str(new_dir))
        self.config.set_dest_dir(new_dir)

    @check_handle()
    def force_recheck(self):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            if self.get_state().get_status() == DLSTATUS_STOPPED:
                self.pause_after_next_hashcheck = True
            self.checkpoint_after_next_hashcheck = True
            self.handle.resume()
            self.handle.force_recheck()

    def get_state(self):
        """ Returns a snapshot of the current state of the download
        @return DownloadState
        """
        return DownloadState(self, self.lt_status, self.error)

    @task
    async def save_resume_data(self, timeout=10):
        """
        Save the resume data of a download. This method returns when the resume data is available.
        Note that this method only calls save_resume_data once on subsequent calls.
        """
        if 'save_resume_data' not in self.futures:
            handle = await self.get_handle()
            handle.save_resume_data()

        try:
            await wait_for(self.wait_for_alert('save_resume_data_alert', None,
                                               'save_resume_data_failed_alert',
                                               lambda a: SaveResumeDataError(a.error.message())), timeout=timeout)
        except (CancelledError, SaveResumeDataError, TimeoutError) as e:
            self._logger.error("Resume data failed to save: %s", e)

    def get_peerlist(self):
        """ Returns a list of dictionaries, one for each connected peer
        containing the statistics for that peer. In particular, the
        dictionary contains the keys:
        <pre>
        'id' = PeerID or 'http seed'
        'extended_version' = Peer client version, as received during the extend handshake message
        'ip' = IP address as string or URL of httpseed
        'port' = Port
        'pex_received' = True/False
        'optimistic' = True/False
        'direction' = 'L'/'R' (outgoing/incoming)
        'uprate' = Upload rate in KB/s
        'uinterested' = Upload Interested: True/False
        'uchoked' = Upload Choked: True/False
        'uhasqueries' = Upload has requests in buffer and not choked
        'uflushed' = Upload is not flushed
        'downrate' = Download rate in KB/s
        'dinterested' = Download interested: True/Flase
        'dchoked' = Download choked: True/False
        'snubbed' = Download snubbed: True/False
        'utotal' = Total uploaded from peer in KB
        'dtotal' = Total downloaded from peer in KB
        'completed' = Fraction of download completed by peer (0-1.0)
        -- QUESTION(lipu): swift and Bitfield are gone. Does this 'have' thing has anything to do with swift?
        'have' = Bitfield object for this peer if not complete
        'speed' = The peer's current total download speed (estimated)
        </pre>
        """
        peers = []
        peer_infos = self.handle.get_peer_info() if self.handle and self.handle.is_valid() else []
        for peer_info in peer_infos:
            try:
                extended_version = peer_info.client
            except UnicodeDecodeError:
                extended_version = 'unknown'
            peer_dict = {'id': hexlify(peer_info.pid.to_bytes()),
                         'extended_version': extended_version,
                         'ip': peer_info.ip[0],
                         'port': peer_info.ip[1],
                         # optimistic_unchoke = 0x800 seems unavailable in python bindings
                         'optimistic': bool(peer_info.flags & 0x800),
                         'direction': 'L' if bool(peer_info.flags & peer_info.local_connection) else 'R',
                         'uprate': peer_info.payload_up_speed,
                         'uinterested': bool(peer_info.flags & peer_info.remote_interested),
                         'uchoked': bool(peer_info.flags & peer_info.remote_choked),
                         'uhasqueries': peer_info.upload_queue_length > 0,
                         'uflushed': peer_info.used_send_buffer > 0,
                         'downrate': peer_info.payload_down_speed,
                         'dinterested': bool(peer_info.flags & peer_info.interesting),
                         'dchoked': bool(peer_info.flags & peer_info.choked),
                         'snubbed': bool(peer_info.flags & 0x1000),
                         'utotal': peer_info.total_upload,
                         'dtotal': peer_info.total_download,
                         'completed': peer_info.progress,
                         'have': peer_info.pieces, 'speed': peer_info.remote_dl_rate,
                         'connection_type': peer_info.connection_type,
                         'seed': bool(peer_info.flags & peer_info.seed),
                         'upload_only': bool(peer_info.flags & peer_info.upload_only)}
            peers.append(peer_dict)
        return peers

    def get_num_connected_seeds_peers(self):
        """ Returns number of connected seeders and leechers """
        num_seeds = num_peers = 0
        if not self.handle or not self.handle.is_valid():
            return 0, 0

        for peer_info in self.handle.get_peer_info():
            if peer_info.flags & peer_info.seed:
                num_seeds += 1
            else:
                num_peers += 1

        return num_seeds, num_peers

    def get_torrent(self):
        if not self.handle or not self.handle.is_valid() or not self.handle.has_metadata():
            return None

        torrent_info = get_info_from_handle(self.handle)
        t = lt.create_torrent(torrent_info)
        return t.generate()

    @check_handle(default={})
    def get_tracker_status(self):
        # Make sure all trackers are in the tracker_status dict
        for announce_entry in self.handle.trackers():
            if announce_entry['url'] not in self.tracker_status:
                try:
                    url = announce_entry['url']
                    self.tracker_status[url] = [0, 'Not contacted yet']
                except UnicodeDecodeError:
                    pass

        # Count DHT and PeX peers
        dht_peers = pex_peers = 0
        for peer_info in self.handle.get_peer_info():
            if peer_info.source & peer_info.dht:
                dht_peers += 1
            if peer_info.source & peer_info.pex:
                pex_peers += 1

        ltsession = self.dlmgr.get_session(self.config.get_hops())
        public = self.tdef and not self.tdef.is_private()

        result = self.tracker_status.copy()
        result['[DHT]'] = [dht_peers, 'Working' if ltsession.is_dht_running() and public else 'Disabled']
        result['[PeX]'] = [pex_peers, 'Working']
        return result

    def set_state_callback(self, usercallback):
        async def state_callback_loop():
            if usercallback:
                when = 1
                while when and not self.future_removed.done() and not self.session.shutdownstarttime:
                    result = usercallback(self.get_state())
                    when = (await result) if iscoroutine(result) else result
                    if when > 0.0 and not self.session.shutdownstarttime:
                        await sleep(when)
        return self.register_anonymous_task("downloads_cb", state_callback_loop)

    async def shutdown(self):
        self.alert_handlers.clear()
        self.stream.close()
        for _, futures in self.futures.items():
            for future, _, _ in futures:
                future.cancel()
        self.futures.clear()
        await self.shutdown_task_manager()

    def stop(self, user_stopped=None):
        self._logger.debug("Stopping %s", self.tdef.get_name())
        self.stream.disable()
        if user_stopped is not None:
            self.config.set_user_stopped(user_stopped)
        if self.handle and self.handle.is_valid():
            self.handle.pause()
            return self.checkpoint()
        return succeed(None)

    def resume(self):
        self._logger.debug("Resuming %s", self.tdef.get_name())

        self.config.set_user_stopped(False)

        if self.handle and self.handle.is_valid():
            self.handle.set_upload_mode(self.get_upload_mode())
            self.handle.resume()

    def get_content_dest(self):
        """ Returns the file to which the downloaded content is saved. """
        return self.config.get_dest_dir() / fix_filebasename(self.tdef.get_name_as_unicode())

    def checkpoint(self):
        """
        Checkpoint this download. Returns when the checkpointing is completed.
        """
        if self.checkpoint_disabled:
            self._logger.debug("Ignoring checkpoint() call as checkpointing is disabled for this download")
            return succeed(None)

        if self.handle and self.handle.is_valid() and not self.handle.need_save_resume_data():
            self._logger.debug("Ignoring checkpoint() call as checkpointing is not needed")
            return succeed(None)

        if not self.handle or not self.handle.is_valid():
            # Libtorrent hasn't received or initialized this download yet
            # 1. Check if we have data for this infohash already (don't overwrite it if we do!)
            basename = hexlify(self.tdef.get_infohash()) + '.conf'
            filename = Path(self.dlmgr.get_checkpoint_dir() / basename)
            if not filename.is_file():
                # 2. If there is no saved data for this infohash, checkpoint it without data so we do not
                #    lose it when we crash or restart before the download becomes known.
                resume_data = self.config.get_engineresumedata() or {
                    b'file-format': b"libtorrent resume file",
                    b'file-version': 1,
                    b'info-hash': self.tdef.get_infohash()
                }
                self.post_alert('save_resume_data_alert', dict(resume_data=resume_data))
            else:
                self._logger.warning("Either file does not exist or is not file")
            return succeed(None)
        return self.save_resume_data()

    def set_def(self, tdef):
        self.tdef = tdef

    @check_handle()
    def add_trackers(self, trackers):
        if hasattr(self.handle, 'add_tracker'):
            for tracker in trackers:
                self.handle.add_tracker({'url': tracker, 'verified': False})

    @check_handle()
    def get_magnet_link(self):
        return lt.make_magnet_uri(self.handle)

    @require_handle
    def add_peer(self, addr):
        """ Add a peer address from 3rd source (not tracker, not DHT) to this download.
        @param (hostname_ip,port) tuple
        """
        self.handle.connect_peer(addr, 0)

    @require_handle
    def set_priority(self, prio):
        self.handle.set_priority(prio)

    @require_handle
    def set_max_upload_rate(self, value):
        self.handle.set_upload_limit(value * 1024)

    @require_handle
    def set_max_download_rate(self, value):
        self.handle.set_download_limit(value * 1024)

    @require_handle
    def apply_ip_filter(self, enable):
        self.handle.apply_ip_filter(enable)

    def get_share_mode(self):
        return self.config.get_share_mode()

    @require_handle
    def set_share_mode(self, share_mode):
        self.config.set_share_mode(share_mode)
        self.handle.set_share_mode(share_mode)

    def get_upload_mode(self):
        return self.config.get_upload_mode()

    @require_handle
    def set_upload_mode(self, upload_mode):
        self.config.set_upload_mode(upload_mode)
        self.handle.set_upload_mode(upload_mode)

    @check_handle()
    def get_upload_mode(self):
        return self.handle.status().upload_mode

    @require_handle
    def set_upload_mode(self, upload_mode):
        self.handle.set_upload_mode(upload_mode)

    @require_handle
    def force_dht_announce(self):
        self.handle.force_dht_announce()

    @require_handle
    def set_sequential_download(self, enable):
        self.handle.set_sequential_download(enable)

    @check_handle(None)
    def set_piece_priorities(self, piece_priorities):
        self.handle.prioritize_pieces(piece_priorities)

    @check_handle([])
    def get_piece_priorities(self):
        return self.handle.piece_priorities()

    @check_handle(None)
    def set_file_priorities(self, file_priorities):
        self.handle.prioritize_files(file_priorities)

    @check_handle(None)
    def reset_piece_deadline(self, piece):
        self.handle.reset_piece_deadline(piece)

    @check_handle(None)
    def set_piece_deadline(self, piece, deadline, flags=0):
        self.handle.set_piece_deadline(piece, deadline, flags)

    @check_handle([])
    def get_file_priorities(self):
        return self.handle.file_priorities()
