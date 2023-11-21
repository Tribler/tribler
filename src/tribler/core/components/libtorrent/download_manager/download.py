"""
A wrapper around a libtorrent download.

Author(s): Arno Bakker, Egbert Bouman
"""
from __future__ import annotations

import asyncio
import base64
import itertools
import logging
from asyncio import CancelledError, Future, iscoroutine, sleep, wait_for, get_running_loop
from collections import defaultdict
from contextlib import suppress
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from bitarray import bitarray
from ipv8.taskmanager import TaskManager, task
from ipv8.util import succeed

from tribler.core import notifications
from tribler.core.components.libtorrent.download_manager.download_config import DownloadConfig
from tribler.core.components.libtorrent.download_manager.download_state import DownloadState
from tribler.core.components.libtorrent.download_manager.stream import Stream
from tribler.core.components.libtorrent.settings import DownloadDefaultsSettings
from tribler.core.components.libtorrent.torrent_file_tree import TorrentFileTree
from tribler.core.components.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler.core.components.libtorrent.utils.libtorrent_helper import libtorrent as lt
from tribler.core.components.libtorrent.utils.torrent_utils import check_handle, get_info_from_handle, require_handle
from tribler.core.components.reporter.exception_handler import NoCrashException
from tribler.core.exceptions import SaveResumeDataError
from tribler.core.utilities.async_force_switch import switch
from tribler.core.utilities.notifier import Notifier
from tribler.core.utilities.osutils import fix_filebasename
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.simpledefs import DOWNLOAD, DownloadStatus
from tribler.core.utilities.unicode import ensure_unicode, hexlify
from tribler.core.utilities.utilities import bdecode_compat

Getter = Callable[[Any], Any]


class IllegalFileIndex(Enum):
    """
    Error codes for Download.get_file_index(). These are used by the GUI to render directories.
    """
    collapsed_dir = -1
    expanded_dir = -2
    unloaded = -3


class Download(TaskManager):
    """ Download subclass that represents a libtorrent download."""

    def __init__(self,
                 tdef: TorrentDef,
                 config: DownloadConfig = None,
                 download_defaults: DownloadDefaultsSettings = None,
                 notifier: Notifier = None,
                 state_dir: Path = None,
                 download_manager=None,
                 checkpoint_disabled=False,
                 hidden=False,
                 dummy=False):
        super().__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        self.dummy = dummy
        self.tdef = tdef
        self.handle: Optional[lt.torrent_handle] = None
        self.state_dir = state_dir
        self.download_manager = download_manager
        self.download_defaults = download_defaults or DownloadDefaultsSettings()
        self.notifier = notifier

        # Libtorrent status
        self.lt_status: Optional[lt.torrent_status] = None
        self.error = None
        self.pause_after_next_hashcheck = False
        self.checkpoint_after_next_hashcheck = False
        self.tracker_status = {}  # {url: [num_peers, status_str]}

        self.futures: Dict[str, list[tuple[Future, Callable, Optional[Getter]]]] = defaultdict(list)
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
        self.stream: Optional[Stream] = None

        # With hidden True download will not be in GET/downloads set, as a result will not be shown in GUI
        self.hidden = hidden
        self.checkpoint_disabled = checkpoint_disabled or self.dummy
        self.config = config or DownloadConfig(state_dir=self.state_dir)

        self._logger.debug("Setup: %s", hexlify(self.tdef.get_infohash()))

        self.checkpoint()

    def __str__(self):
        return "Download <name: '%s' hops: %d checkpoint_disabled: %d>" % \
            (self.tdef.get_name(), self.config.get_hops(), self.checkpoint_disabled)

    def __repr__(self):
        return self.__str__()

    def add_stream(self):
        assert self.stream is None
        self.stream = Stream(self)

    def get_torrent_data(self) -> Optional[object]:
        """
        Return torrent data, if the handle is valid and metadata is available.
        """
        if not self.handle or not self.handle.is_valid() or not self.handle.has_metadata():
            return None

        torrent_info = get_info_from_handle(self.handle)
        t = lt.create_torrent(torrent_info)
        return t.generate()

    def register_alert_handler(self, alert_type: str, handler: lt.torrent_handle):
        self.alert_handlers[alert_type].append(handler)

    def wait_for_alert(self, success_type: str, success_getter: Optional[Getter] = None,
                       fail_type: str = None, fail_getter: Optional[Getter] = None) -> Future:
        future = Future()
        if success_type:
            self.futures[success_type].append((future, future.set_result, success_getter))
        if fail_type:
            self.futures[fail_type].append((future, future.set_exception, fail_getter))
        return future

    async def wait_for_status(self, *status):
        while self.get_state().get_status() not in status:
            await switch()
            await self.wait_for_alert('state_changed_alert')

    def get_def(self) -> TorrentDef:
        return self.tdef

    def get_handle(self) -> Awaitable[lt.torrent_handle]:
        """
        Returns a deferred that fires with a valid libtorrent download handle.
        """
        if self.handle:
            # This block could be safely omitted because `self.future_added` does the same thing.
            # However, it is used in tests, therefore it is better to keep it for now.
            return succeed(self.handle)

        return self.future_added

    def get_atp(self) -> Dict:
        save_path = self.config.get_dest_dir()
        atp = {"save_path": str(save_path),
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
                save_path = (ensure_unicode(resume_data[b"save_path"], 'utf8') if b"save_path" in resume_data
                             else None)
                if save_path and not Path(save_path).is_absolute():
                    resume_data[b"save_path"] = str(self.state_dir / save_path)
                atp["resume_data"] = lt.bencode(resume_data)
        else:
            atp["url"] = self.tdef.get_url() or "magnet:?xt=urn:btih:" + hexlify(self.tdef.get_infohash())
            atp["name"] = self.tdef.get_name_as_unicode()

        return atp

    def on_add_torrent_alert(self, alert: lt.add_torrent_alert):
        self._logger.info(f'On add torrent alert: {alert}')

        if hasattr(alert, 'error') and alert.error.value():
            self._logger.error("Failed to add torrent (%s)", self.tdef.get_name_as_unicode())
            raise RuntimeError(alert.error.message())
        elif not alert.handle.is_valid():
            self._logger.error("Received invalid torrent handle")
            return

        self.handle = alert.handle
        self._logger.debug("Added torrent %s", str(self.handle.info_hash()))
        # In LibTorrent auto_managed flag is now on by default, and as a result
        # any torrent's state can change from Stopped to Downloading at any time.
        # Here we unset this flag to prevent auto-resuming of stopped torrents.
        if hasattr(self.handle, 'unset_flags'):
            self.handle.unset_flags(lt.add_torrent_params_flags_t.flag_auto_managed)

        self.set_selected_files()

        user_stopped = self.config.get_user_stopped()

        # If we lost resume_data always resume download in order to force checking
        if not user_stopped or not self.config.get_engineresumedata():
            self.handle.resume()

            # If we only needed to perform checking, pause download after it is complete
            self.pause_after_next_hashcheck = user_stopped

        # Limit the amount of connections if we have specified that
        self.handle.set_max_connections(self.download_manager.config.max_connections_download)

        # By default don't apply the IP filter
        self.apply_ip_filter(False)

        self.checkpoint()

    def get_anon_mode(self) -> bool:
        return self.config.get_hops() > 0

    @check_handle(b'')
    def get_pieces_base64(self) -> bytes:
        """
        Returns a base64 encoded bitmask of the pieces that we have.
        """
        binary_gen = (int(boolean) for boolean in self.handle.status().pieces)
        bits = bitarray(binary_gen)
        return base64.b64encode(bits.tobytes())

    def post_alert(self, alert_type: str, alert_dict: Optional[Dict] = None):
        alert_dict = alert_dict or {}
        alert_dict['category'] = lambda _: None
        alert = type('anonymous_alert', (object,), alert_dict)()
        self.process_alert(alert, alert_type)

    def process_alert(self, alert: lt.torrent_alert, alert_type: str):
        try:
            if alert.category() in [lt.alert.category_t.error_notification, lt.alert.category_t.performance_warning]:
                self._logger.debug("Got alert: %s", alert)

            for handler in self.alert_handlers.get(alert_type, []):
                handler(alert)

            for future, future_setter, getter in self.futures.pop(alert_type, []):
                if not future.done():
                    future_setter(getter(alert) if getter else alert)
        except Exception as e:
            self._logger.exception(f'Failed process alert: {e}')
            raise NoCrashException from e

    def on_torrent_error_alert(self, alert: lt.torrent_error_alert):
        self._logger.error(f'On torrent error alert: {alert}')

    def on_state_changed_alert(self, alert: lt.state_changed_alert):
        self._logger.info(f'On state changed alert: {alert}')

        if not self.handle:
            return
        self.update_lt_status(self.handle.status())

        enable = alert.state == lt.torrent_status.seeding and self.config.get_hops() > 0
        self._logger.debug('Setting IP filter for %s to %s', hexlify(self.tdef.get_infohash()), enable)
        self.apply_ip_filter(enable)

        # On a rare occasion we don't get a metadata_received_alert. If this is the case, post an alert manually.
        if alert.state == lt.torrent_status.downloading and isinstance(self.tdef, TorrentDefNoMetainfo):
            self.post_alert('metadata_received_alert')

    def on_save_resume_data_alert(self, alert: lt.save_resume_data_alert):
        """
        Callback for the alert that contains the resume data of a specific download.
        This resume data will be written to a file on disk.
        """
        self._logger.debug('On save resume data alert: %s', alert)
        if self.checkpoint_disabled:
            return

        resume_data = alert.resume_data
        # Make save_path relative if the torrent is saved in the Tribler state directory
        if self.state_dir and b'save_path' in resume_data:
            save_path = Path(resume_data[b'save_path'].decode('utf8'))
            resume_data[b'save_path'] = str(save_path.normalize_to(self.state_dir))

        metainfo = {
            'infohash': self.tdef.get_infohash(),
            'name': self.tdef.get_name_as_unicode(),
            'url': self.tdef.get_url()
        } if isinstance(self.tdef, TorrentDefNoMetainfo) else self.tdef.get_metainfo()

        self.config.set_metainfo(metainfo)
        self.config.set_engineresumedata(resume_data)

        # Save it to file
        basename = hexlify(resume_data[b'info-hash']) + '.conf'
        filename = self.download_manager.get_checkpoint_dir() / basename
        self.config.config['download_defaults']['name'] = self.tdef.get_name_as_unicode()  # store name (for debugging)
        try:
            self.config.write(str(filename))
        except OSError as e:
            self._logger.warning(f'{e.__class__.__name__}: {e}')
        else:
            self._logger.debug(f'Resume data has been saved to: {filename}')

    def on_tracker_reply_alert(self, alert: lt.tracker_reply_alert):
        self._logger.info(f'On tracker reply alert: {alert}')

        self.tracker_status[alert.url] = [alert.num_peers, 'Working']

    def on_tracker_error_alert(self, alert: lt.tracker_error_alert):
        """
        This alert is generated on tracker timeouts, premature disconnects, invalid response
        or an HTTP response other than "200 OK". - From Libtorrent documentation.
        """
        # The try-except block is added as a workaround to suppress UnicodeDecodeError in `repr(alert)`,
        # `alert.url` and `alert.msg`. See https://github.com/arvidn/libtorrent/issues/143
        try:
            self._logger.error(f'On tracker error alert: {alert}')
            url = alert.url

            if alert.msg:
                status = 'Error: ' + alert.msg
            elif alert.status_code > 0:
                status = 'HTTP status code %d' % alert.status_code
            elif alert.status_code == 0:
                status = 'Timeout'
            else:
                status = 'Not working'

            peers = 0  # If there is a tracker error, alert.num_peers is not available. So resetting peer count to zero.
            self.tracker_status[url] = [peers, status]
        except UnicodeDecodeError as e:
            self._logger.warning(f'UnicodeDecodeError in on_tracker_error_alert: {e}')

    def on_tracker_warning_alert(self, alert: lt.tracker_warning_alert):
        self._logger.warning(f'On tracker warning alert: {alert}')

        peers = self.tracker_status[alert.url][0] if alert.url in self.tracker_status else 0
        status = 'Warning: ' + str(alert.message())

        self.tracker_status[alert.url] = [peers, status]

    @check_handle()
    def on_metadata_received_alert(self, alert: lt.metadata_received_alert):
        self._logger.info(f'On metadata received alert: {alert}')

        torrent_info = get_info_from_handle(self.handle)
        if not torrent_info:
            return

        metadata = {b'info': bdecode_compat(torrent_info.metadata()), b'leechers': 0, b'seeders': 0}
        tracker_urls = []
        for tracker in self.handle.trackers():
            url = tracker['url']
            try:
                tracker_urls.append(url.encode('utf-8'))
            except UnicodeDecodeError as e:
                self._logger.warning(e)

        if len(tracker_urls) > 1:
            metadata[b"announce-list"] = [tracker_urls]
        elif tracker_urls:
            metadata[b"announce"] = tracker_urls[0]

        for peer in self.handle.get_peer_info():
            if peer.progress == 1:
                metadata[b"seeders"] += 1
            else:
                metadata[b"leechers"] += 1

        try:
            self.tdef = TorrentDef.load_from_dict(metadata)
            with suppress(RuntimeError):
                # Try to load the torrent info in the background if we have a loop.
                get_running_loop().run_in_executor(None, self.tdef.load_torrent_info)
        except ValueError as ve:
            self._logger.exception(ve)
            return

        self.set_selected_files()
        self.checkpoint()

    def on_performance_alert(self, alert: lt.performance_alert):
        self._logger.info(f'On performance alert: {alert}')

        if self.get_anon_mode() or self.download_manager.ltsessions is None:
            return

        # When the send buffer watermark is too low, double the buffer size to a
        # maximum of 50MiB. This is the same mechanism as Deluge uses.
        lt_session = self.download_manager.get_session(self.config.get_hops())
        settings = self.download_manager.get_session_settings(lt_session)
        if alert.message().endswith("send buffer watermark too low (upload rate will suffer)"):
            if settings['send_buffer_watermark'] <= 26214400:
                self._logger.info("Setting send_buffer_watermark to %s", 2 * settings['send_buffer_watermark'])
                settings['send_buffer_watermark'] *= 2
                self.download_manager.set_session_settings(self.download_manager.get_session(), settings)
        # When the write cache is too small, double the buffer size to a maximum
        # of 64MiB. Again, this is the same mechanism as Deluge uses.
        elif alert.message().endswith("max outstanding disk writes reached"):
            if settings['max_queued_disk_bytes'] <= 33554432:
                self._logger.info("Setting max_queued_disk_bytes to %s", 2 * settings['max_queued_disk_bytes'])
                settings['max_queued_disk_bytes'] *= 2
                self.download_manager.set_session_settings(self.download_manager.get_session(), settings)

    def on_torrent_removed_alert(self, alert: lt.torrent_removed_alert):
        self._logger.info(f'On torrent remove alert: {alert}')

        self._logger.debug("Removing %s", self.tdef.get_name())
        self.handle = None

    def on_torrent_checked_alert(self, alert: lt.torrent_checked_alert):
        self._logger.info(f'On torrent checked alert: {alert}')

        if self.pause_after_next_hashcheck:
            self.pause_after_next_hashcheck = False
            self.handle.pause()
        if self.checkpoint_after_next_hashcheck:
            self.checkpoint_after_next_hashcheck = False
            self.checkpoint()

    @check_handle()
    def on_torrent_finished_alert(self, alert: lt.torrent_finished_alert):
        self._logger.info(f'On torrent finished alert: {alert}')
        self.update_lt_status(self.handle.status())
        self.checkpoint()
        downloaded = self.get_state().get_total_transferred(DOWNLOAD)
        if downloaded > 0 and self.stream is not None and self.notifier is not None:
            name = self.tdef.get_name_as_unicode()
            infohash = self.tdef.get_infohash().hex()
            hidden = self.hidden or self.config.get_channel_download()
            self.notifier[notifications.torrent_finished](infohash=infohash, name=name, hidden=hidden)

    def update_lt_status(self, lt_status: lt.torrent_status):
        """ Update libtorrent stats and check if the download should be stopped."""
        self.lt_status = lt_status
        self._stop_if_finished()

    def _stop_if_finished(self):
        state = self.get_state()
        if state.get_status() == DownloadStatus.SEEDING:
            mode = self.download_defaults.seeding_mode
            seeding_ratio = self.download_defaults.seeding_ratio
            seeding_time = self.download_defaults.seeding_time
            if (mode == 'never' or
                    (mode == 'ratio' and state.get_seeding_ratio() >= seeding_ratio) or
                    (mode == 'time' and state.get_seeding_time() >= seeding_time)):
                self.stop()

    @check_handle()
    def set_selected_files(self, selected_files=None, prio: int = 4, force: bool = False):
        if not force and self.stream is not None:
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
    def move_storage(self, new_dir: Path):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            self.handle.move_storage(str(new_dir))
        self.config.set_dest_dir(new_dir)

    @check_handle()
    def force_recheck(self):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            if self.get_state().get_status() == DownloadStatus.STOPPED:
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
    async def save_resume_data(self, timeout: int = 10):
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
        except (CancelledError, SaveResumeDataError, TimeoutError, asyncio.exceptions.TimeoutError) as e:
            self._logger.error("Resume data failed to save: %s", e)

    def get_peerlist(self) -> List[Dict[Any, Any]]:
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

    def get_num_connected_seeds_peers(self) -> Tuple[int, int]:
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

    def get_torrent(self) -> object:
        if not self.handle or not self.handle.is_valid() or not self.handle.has_metadata():
            return None

        torrent_info = get_info_from_handle(self.handle)
        t = lt.create_torrent(torrent_info)
        return t.generate()

    @check_handle(default={})
    def get_tracker_status(self):
        # Make sure all trackers are in the tracker_status dict
        try:
            for announce_entry in self.handle.trackers():
                url = announce_entry['url']
                if url not in self.tracker_status:
                    self.tracker_status[url] = [0, 'Not contacted yet']
        except UnicodeDecodeError:
            self._logger.warning('UnicodeDecodeError in get_tracker_status')

        # Count DHT and PeX peers
        dht_peers = pex_peers = 0
        peer_info = []

        try:
            peer_info = self.handle.get_peer_info()
        except Exception as e:  # pylint: disable=broad-except
            self._logger.exception(e)

        for info in peer_info:
            if info.source & info.dht:
                dht_peers += 1
            if info.source & info.pex:
                pex_peers += 1

        ltsession = self.download_manager.get_session(self.config.get_hops())
        public = self.tdef and not self.tdef.is_private()

        result = self.tracker_status.copy()
        result['[DHT]'] = [dht_peers, 'Working' if ltsession.is_dht_running() and public else 'Disabled']
        result['[PeX]'] = [pex_peers, 'Working']
        return result

    def set_state_callback(self, usercallback):
        async def state_callback_loop():
            if usercallback:
                when = 1
                while when and not self.future_removed.done() and not self.download_manager._shutdown:
                    result = usercallback(self.get_state())
                    when = (await result) if iscoroutine(result) else result
                    if when > 0.0 and not self.download_manager._shutdown:
                        await sleep(when)

        return self.register_anonymous_task("downloads_cb", state_callback_loop)

    async def shutdown(self):
        self._logger.info('Shutting down...')
        self.alert_handlers.clear()
        if self.stream is not None:
            self.stream.close()

        active_futures = [f for f, _, _ in itertools.chain(*self.futures.values()) if not f.done()]
        for future in active_futures:
            future.cancel()
        with suppress(CancelledError):
            await asyncio.gather(*active_futures)  # wait for futures to be actually cancelled
        self.futures.clear()
        await self.shutdown_task_manager()

    def stop(self, user_stopped=None):
        self._logger.debug("Stopping %s", self.tdef.get_name())
        if self.stream is not None:
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

    def get_content_dest(self) -> Path:
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
            filename = Path(self.download_manager.get_checkpoint_dir() / basename)
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

    def set_def(self, tdef: TorrentDef):
        self.tdef = tdef

    @check_handle()
    def add_trackers(self, trackers: List[str]):
        if hasattr(self.handle, 'add_tracker'):
            for tracker in trackers:
                self.handle.add_tracker({'url': tracker, 'verified': False})

    @check_handle()
    def get_magnet_link(self) -> str:
        return lt.make_magnet_uri(self.handle)

    @require_handle
    def add_peer(self, addr):
        """ Add a peer address from 3rd source (not tracker, not DHT) to this download.
        @param (hostname_ip,port) tuple
        """
        self.handle.connect_peer(addr, 0)

    @require_handle
    def set_priority(self, priority: int):
        self.handle.set_priority(priority)

    @require_handle
    def set_max_upload_rate(self, value: int):
        self.handle.set_upload_limit(value * 1024)

    @require_handle
    def set_max_download_rate(self, value: int):
        self.handle.set_download_limit(value * 1024)

    @require_handle
    def apply_ip_filter(self, enable: bool):
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

    def file_piece_range(self, file_path: Path) -> list[int]:
        """
        Get the piece range of a given file, specified by the path.

        Calling this method with anything but a file path will return an empty list.
        """
        file_index = self.get_file_index(file_path)
        if file_index < 0:
            return []

        start_piece = self.tdef.torrent_info.map_file(file_index, 0, 1).piece
        # Note: next_piece contains the next piece that is NOT part of this file.
        if file_index < self.tdef.torrent_info.num_files() - 1:
            next_piece = self.tdef.torrent_info.map_file(file_index + 1, 0, 1).piece
        else:
            # There is no next file so the nex piece is the last piece index + 1 (num_pieces()).
            next_piece = self.tdef.torrent_info.num_pieces()

        return list(range(start_piece, next_piece))

    @check_handle(0.0)
    def get_file_completion(self, path: Path) -> float:
        """
        Calculate the completion of a given file or directory.
        """
        total = 0
        have = 0
        for piece_index in self.file_piece_range(path):
            have += self.handle.have_piece(piece_index)
            total += 1
        if total == 0:
            return 1.0
        return have/total

    def get_file_length(self, path: Path) -> int:
        """
        Get the length of a file or directory in bytes. Returns 0 if the given path does not point to an existing path.
        """
        result = self.tdef.torrent_file_tree.find(path)
        if result is not None:
            return result.size
        return 0

    def get_file_index(self, path: Path) -> int:
        """
        Get the index of a file or directory in a torrent. Note that directories do not have real file indices.

        Special cases ("error codes"):

         - ``-1`` (IllegalFileIndex.collapsed_dir): the given path is not a file but a collapsed directory.
         - ``-2`` (IllegalFileIndex.expanded_dir): the given path is not a file but an expanded directory.
         - ``-3`` (IllegalFileIndex.unloaded): the data structure is not loaded or the path is not found.
        """
        result = self.tdef.torrent_file_tree.find(path)
        if isinstance(result, TorrentFileTree.File):
            return self.tdef.torrent_file_tree.find(path).index
        if isinstance(result, TorrentFileTree.Directory):
            return (IllegalFileIndex.collapsed_dir.value if result.collapsed
                    else IllegalFileIndex.expanded_dir.value)
        return IllegalFileIndex.unloaded.value

    def is_file_selected(self, file_path: Path) -> bool:
        """
        Check if the given file path is selected.

        Calling this method with anything but a file path will return False.
        """
        result = self.tdef.torrent_file_tree.find(file_path)
        if isinstance(result, TorrentFileTree.File):
            return result.selected
        return False
