"""
A wrapper around a libtorrent download.

Author(s): Arno Bakker, Egbert Bouman
"""
import base64
import logging
import shutil
import sys
import time
from asyncio import CancelledError, Future, as_completed, iscoroutine, sleep
from collections import defaultdict

import libtorrent as lt

from Tribler.Core.Config.download_config import DownloadConfig, get_default_dest_dir
from Tribler.Core.DownloadState import DownloadState
from Tribler.Core.Libtorrent import check_handle, require_handle
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities import path_util
from Tribler.Core.Utilities.torrent_utils import commonprefix, get_info_from_handle
from Tribler.Core.Utilities.unicode import ensure_unicode, hexlify
from Tribler.Core.Utilities.utilities import bdecode_compat, succeed
from Tribler.Core.exceptions import SaveResumeDataError
from Tribler.Core.osutils import fix_filebasename
from Tribler.Core.simpledefs import (
    DLMODE_VOD,
    DLSTATUS_SEEDING,
    DLSTATUS_STOPPED,
    NTFY_ERROR,
    NTFY_FINISHED,
    NTFY_TORRENT,
)
from Tribler.pyipv8.ipv8.taskmanager import TaskManager
from Tribler.pyipv8.ipv8.util import int2byte

if sys.platform == "win32":
    try:
        import ctypes
    except ImportError:
        pass


class VODFile(object):

    def __init__(self, f, d):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._file = f
        self._download = d

        pieces = self._download.tdef.get_pieces()
        self.pieces = [pieces[x:x + 20] for x in range(0, len(pieces), 20)]
        self.piecesize = self._download.tdef.get_piece_length()

        self.startpiece = get_info_from_handle(self._download.handle).map_file(self._download.get_vod_fileindex(),
                                                                               0, 0)
        self.endpiece = get_info_from_handle(self._download.handle).map_file(self._download.get_vod_fileindex(),
                                                                             self._download.get_vod_filesize(), 0)

    def read(self, *args):
        oldpos = self._file.tell()

        self._logger.debug('VODFile: get bytes %s - %s', oldpos, oldpos + args[0])

        while not self._file.closed and self._download.get_byte_progress([
            (self._download.get_vod_fileindex(), oldpos, oldpos + args[0])]) < 1 \
                and self._download.vod_seekpos is not None:
            time.sleep(1)

        if self._file.closed:
            self._logger.debug('VODFile: got no bytes, file is closed')
            return ''

        result = self._file.read(*args)

        newpos = self._file.tell()
        if self._download.vod_seekpos == oldpos:
            self._download.vod_seekpos = newpos

        self._logger.debug('VODFile: got bytes %s - %s', oldpos, newpos)

        return result

    def seek(self, *args):
        self._file.seek(*args)
        newpos = self._file.tell()

        self._logger.debug('VODFile: seek %s %s', newpos, args)

        if self._download.vod_seekpos is None or abs(newpos - self._download.vod_seekpos) < 1024 * 1024:
            self._download.vod_seekpos = newpos
        self._download.set_byte_priority([(self._download.get_vod_fileindex(), 0, newpos)], 0)
        self._download.set_byte_priority([(self._download.get_vod_fileindex(), newpos, -1)], 1)

        self._logger.debug('VODFile: seek, get pieces %s', self._download.handle.piece_priorities())
        self._logger.debug('VODFile: seek, got pieces %s', [
            int(piece) for piece in self._download.handle.status().pieces])

    def close(self, *args):
        self._file.close(*args)

    @property
    def closed(self):
        return self._file.closed


class LibtorrentDownloadImpl(TaskManager):
    """ Download subclass that represents a libtorrent download."""

    def __init__(self, session, tdef):
        super(LibtorrentDownloadImpl, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        self.session = session
        self.tdef = tdef
        self.handle = None
        self.vod_index = None
        self.orig_files = None
        self.state_dir = self.session.config.get_state_dir() if self.session else None
        self.ltmgr = self.session.ltmgr if self.session else None

        # With hidden True download will not be in GET/downloads set, as a result will not be shown in GUI
        self.hidden = False

        # Libtorrent status
        self.lt_status = None
        self.error = None
        self.pause_after_next_hashcheck = False
        self.checkpoint_after_next_hashcheck = False
        self.tracker_status = {}  # {url: [num_peers, status_str]}

        self.prebuffsize = 5 * 1024 * 1024
        self.endbuffsize = 0
        self.vod_seekpos = 0
        self.max_prebuffsize = 5 * 1024 * 1024

        self.checkpoint_disabled = False

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
                          'file_renamed_alert': self.on_file_renamed_alert,
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

    def __str__(self):
        return "LibtorrentDownloadImpl <name: '%s' hops: %d checkpoint_disabled: %d>" % \
               (self.tdef.get_name(), self.config.get_hops(), self.checkpoint_disabled)

    def __repr__(self):
        return self.__str__()

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
        self.checkpoint_disabled = checkpoint_disabled
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

            self.orig_files = [file_entry.path for file_entry in torrentinfo.files()]

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

        self.set_vod_mode(self.config.get_mode() == DLMODE_VOD)

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

    def set_vod_mode(self, enable=True):

        self._logger.debug("LibtorrentDownloadImpl: set_vod_mode for %s (enable = %s)", self.tdef.get_name(), enable)

        if enable:
            self.vod_seekpos = 0

            filename = self.config.get_selected_files()[0] if self.tdef.is_multifile_torrent() else self.tdef.get_name()
            self.vod_index = self.tdef.get_index_of_file_in_files(filename) if self.tdef.is_multifile_torrent() else 0

            self.prebuffsize = max(int(self.get_vod_filesize() * 0.05), self.max_prebuffsize)
            self.endbuffsize = 1 * 1024 * 1024

            self.handle.set_sequential_download(True)
            self.handle.set_priority(255)
            self.set_byte_priority([(self.get_vod_fileindex(), self.prebuffsize, -self.endbuffsize)], 0)
            self.set_byte_priority([(self.get_vod_fileindex(), 0, self.prebuffsize)], 1)
            self.set_byte_priority([(self.get_vod_fileindex(), -self.endbuffsize, -1)], 1)

            self._logger.debug("LibtorrentDownloadImpl: going into VOD mode %s", filename)
        else:
            self.handle.set_sequential_download(False)
            self.handle.set_priority(0 if self.config.get_credit_mining() else 1)
            if self.get_vod_fileindex() >= 0:
                self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)

    def get_vod_fileindex(self):
        if self.vod_index is not None:
            return self.vod_index
        return -1

    @check_handle(0)
    def get_vod_filesize(self):
        fileindex = self.get_vod_fileindex()
        torrent_info = get_info_from_handle(self.handle)
        if fileindex >= 0 and torrent_info:
            file_entry = torrent_info.file_at(fileindex)
            return file_entry.size
        return 0

    @check_handle(0.0)
    def get_piece_progress(self, pieces, consecutive=False):
        if not pieces:
            return 1.0
        elif consecutive:
            pieces.sort()

        status = self.handle.status()
        if status:
            pieces_have = 0
            pieces_all = len(pieces)
            bitfield = status.pieces
            for pieceindex in pieces:
                if pieceindex < len(bitfield) and bitfield[pieceindex]:
                    pieces_have += 1
                elif consecutive:
                    break
            return pieces_have / pieces_all
        return 0.0

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

    @check_handle(0.0)
    def get_byte_progress(self, byteranges, consecutive=False):
        pieces = []
        torrent_info = get_info_from_handle(self.handle)
        if not torrent_info:
            self._logger.info("LibtorrentDownloadImpl: could not get info from download handle")

        for fileindex, bytes_begin, bytes_end in byteranges:
            if fileindex >= 0 and torrent_info:
                # Ensure the we remain within the file's boundaries
                file_entry = torrent_info.file_at(fileindex)
                bytes_begin = min(
                    file_entry.size, bytes_begin) if bytes_begin >= 0 else file_entry.size + (bytes_begin + 1)
                bytes_end = min(file_entry.size, bytes_end) if bytes_end >= 0 else file_entry.size + (bytes_end + 1)

                startpiece = torrent_info.map_file(fileindex, bytes_begin, 0).piece
                endpiece = torrent_info.map_file(fileindex, bytes_end, 0).piece + 1
                startpiece = max(startpiece, 0)
                endpiece = min(endpiece, torrent_info.num_pieces())

                pieces += list(range(startpiece, endpiece))
            else:
                self._logger.info("LibtorrentDownloadImpl: could not get progress for incorrect fileindex")

        pieces = list(set(pieces))
        return self.get_piece_progress(pieces, consecutive)

    @check_handle()
    def set_piece_priority(self, pieces_need, priority):
        do_prio = False
        pieces_have = self.handle.status().pieces
        piecepriorities = self.handle.piece_priorities()
        for piece in pieces_need:
            if piece < len(piecepriorities):
                if piecepriorities[piece] != priority and not pieces_have[piece]:
                    piecepriorities[piece] = priority
                    do_prio = True
            else:
                self._logger.info(
                    "LibtorrentDownloadImpl: could not set priority for non-existing piece %d / %d", piece,
                    len(piecepriorities))
        if do_prio:
            self.handle.prioritize_pieces(piecepriorities)
        else:
            self._logger.info("LibtorrentDownloadImpl: skipping set_piece_priority")

    @check_handle()
    def set_byte_priority(self, byteranges, priority):
        pieces = []
        torrent_info = get_info_from_handle(self.handle)
        if not torrent_info:
            self._logger.info("LibtorrentDownloadImpl: could not get info from download handle")

        for fileindex, bytes_begin, bytes_end in byteranges:
            if fileindex >= 0 and torrent_info:
                # Ensure the we remain within the file's boundaries
                file_entry = torrent_info.file_at(fileindex)
                bytes_begin = min(
                    file_entry.size, bytes_begin) if bytes_begin >= 0 else file_entry.size + (bytes_begin + 1)
                bytes_end = min(file_entry.size, bytes_end) if bytes_end >= 0 else file_entry.size + (bytes_end + 1)

                startpiece = torrent_info.map_file(fileindex, bytes_begin, 0).piece
                endpiece = torrent_info.map_file(fileindex, bytes_end, 0).piece + 1
                startpiece = max(startpiece, 0)
                endpiece = min(endpiece, torrent_info.num_pieces())

                pieces += list(range(startpiece, endpiece))
            else:
                self._logger.info("LibtorrentDownloadImpl: could not set priority for incorrect fileindex")

        if pieces:
            pieces = list(set(pieces))
            self.set_piece_priority(pieces, priority)

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
        self.session.notifier.notify(NTFY_TORRENT, NTFY_ERROR, self.tdef.get_infohash(), alert.error, self.hidden)

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
                resume_data[b'save_path'] = path_util.norm_path(self.state_dir, save_path).to_text()

        metainfo = {
            'infohash': self.tdef.get_infohash(),
            'name': self.tdef.get_name_as_unicode(),
            'url': self.tdef.get_url()
        } if isinstance(self.tdef, TorrentDefNoMetainfo) else self.tdef.get_metainfo()

        self.config.set_metainfo(metainfo)
        self.config.set_engineresumedata(resume_data)

        # Save it to file
        basename = hexlify(resume_data[b'info-hash']) + '.conf'
        filename = self.ltmgr.get_checkpoint_dir() / basename
        self.config.write(filename.to_text())
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

        try:
            torrent_files = lt.torrent_info(metadata).files()
        except RuntimeError:
            self._logger.warning("Torrent contains no files!")
            torrent_files = []

        self.orig_files = [torrent_file.path for torrent_file in torrent_files]
        self.set_selected_files()

        self.checkpoint()

    def on_file_renamed_alert(self, _):
        unwanteddir_abs = self.get_save_path() / self.unwanted_dir
        if unwanteddir_abs.exists() and all(self.handle.file_priorities()):
            shutil.rmtree(unwanteddir_abs, ignore_errors=True)

    def on_performance_alert(self, alert):
        if self.get_anon_mode() or self.ltmgr.ltsessions is None:
            return

        # When the send buffer watermark is too low, double the buffer size to a
        # maximum of 50MiB. This is the same mechanism as Deluge uses.
        lt_session = self.ltmgr.get_session(self.config.get_hops())
        settings = self.ltmgr.get_session_settings(lt_session)
        if alert.message().endswith("send buffer watermark too low (upload rate will suffer)"):
            if settings['send_buffer_watermark'] <= 26214400:
                self._logger.info(
                    "LibtorrentDownloadImpl: setting send_buffer_watermark to %s",
                    2 * settings['send_buffer_watermark'])
                settings['send_buffer_watermark'] *= 2
                self.ltmgr.set_session_settings(self.ltmgr.get_session(), settings)
        # When the write cache is too small, double the buffer size to a maximum
        # of 64MiB. Again, this is the same mechanism as Deluge uses.
        elif alert.message().endswith("max outstanding disk writes reached"):
            if settings['max_queued_disk_bytes'] <= 33554432:
                self._logger.info(
                    "LibtorrentDownloadImpl: setting max_queued_disk_bytes to %s",
                    2 * settings['max_queued_disk_bytes'])
                settings['max_queued_disk_bytes'] *= 2
                self.ltmgr.set_session_settings(self.ltmgr.get_session(), settings)

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

        progress = self.get_state().get_progress()
        if self.config.get_mode() == DLMODE_VOD:
            if progress == 1.0:
                self.handle.set_sequential_download(False)
                self.handle.set_priority(0)
                if self.get_vod_fileindex() >= 0:
                    self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)
            elif progress < 1.0:
                # If we are in VOD mode and still need to download pieces and libtorrent
                # says we are finished, reset the piece priorities to 1.
                def reset_priorities():
                    if self and self.get_state().get_progress() == 1.0:
                        self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)
                self.register_anonymous_task("reset_priorities", reset_priorities, delay=5)

            if self.endbuffsize:
                self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)
                self.endbuffsize = 0

        self.checkpoint()
        self.session.notifier.notify(NTFY_TORRENT, NTFY_FINISHED, self.tdef.get_infohash(),
                                     self.tdef.get_name_as_unicode(), self.hidden)

    def update_lt_status(self, lt_status):
        """ Update libtorrent stats and check if the download should be stopped."""
        self.lt_status = lt_status
        self._stop_if_finished()

    def _stop_if_finished(self):
        state = self.get_state()
        # Credit mining downloads are not affected by seeding policy
        if self.config.get_credit_mining():
            return
        if state.get_status() == DLSTATUS_SEEDING:
            mode = self.session.config.get_seeding_mode()
            if mode == 'never' \
                    or (mode == 'ratio' and state.get_seeding_ratio() >= self.session.config.get_seeding_ratio()) \
                    or (mode == 'time' and state.get_seeding_time() >= self.session.config.get_seeding_time()):
                self.stop()

    @property
    def swarmname(self):
        """
        Return the swarm name of the torrent.
        """
        orig_files = [path_util.Path(f) for f in self.orig_files]
        is_multifile = len(orig_files) > 1
        path = path_util.Path(commonprefix(orig_files).parts[0]) if is_multifile else path_util.Path()
        return path

    @property
    def unwanted_dir(self):
        """
        Return the name of the directory containing the unwanted files (files with a priority of 0).
        """
        return self.swarmname / u'.unwanted'

    @check_handle()
    def set_selected_files(self, selected_files=None):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            if selected_files is None:
                selected_files = self.config.get_selected_files()
            else:
                self.config.set_selected_files(selected_files)

            torrent_info = get_info_from_handle(self.handle)
            if not torrent_info or not hasattr(torrent_info, 'files'):
                self._logger.error("File info not available for torrent %s", hexlify(self.tdef.get_infohash()))
                return

            unwanteddir_abs = self.get_save_path() / self.unwanted_dir

            filepriorities = []
            torrent_storage = torrent_info.files()
            for index, orig_path in enumerate(self.orig_files):
                filename = orig_path[len(self.swarmname.to_text()) + 1:] if self.swarmname.to_text() else orig_path
                if filename in selected_files or not selected_files:
                    filepriorities.append(1)
                    new_path = orig_path
                else:
                    filepriorities.append(0)
                    new_path = (unwanteddir_abs / ('%s%d' % (hexlify(self.tdef.get_infohash()), index))).to_text()

                # as from libtorrent 1.0, files returning file_storage (lazy-iterable)
                if hasattr(lt, 'file_storage') and isinstance(torrent_storage, lt.file_storage):
                    cur_path = torrent_storage.at(index).path
                else:
                    cur_path = torrent_storage[index].path

                if cur_path != new_path:
                    if not unwanteddir_abs.exists() and self.unwanted_dir.to_text() in new_path:
                        try:
                            path_util.makedirs(unwanteddir_abs)
                            if sys.platform == "win32":
                                # Hide the directory (2 = FILE_ATTRIBUTE_HIDDEN)
                                ctypes.windll.kernel32.SetFileAttributesW(unwanteddir_abs.to_text(), 2)
                        except OSError:
                            self._logger.error("LibtorrentDownloadImpl: could not create %s" % unwanteddir_abs)
                            # Note: If the destination directory can't be accessed, libtorrent will not be able
                            # to store the files. This will result in a DLSTATUS_STOPPED_ON_ERROR.

                    # Path should be unicode if Libtorrent is using std::wstring (on Windows),
                    # else we use str (on Linux).
                    try:
                        self.handle.rename_file(index, new_path)
                    except TypeError:
                        self.handle.rename_file(index, new_path.encode("utf-8"))

            # if in share mode, don't change priority of the file
            if not self.get_share_mode():
                self.handle.prioritize_files(filepriorities)

    @check_handle(False)
    def move_storage(self, new_dir):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            self.handle.move_storage(new_dir)
            self.config.set_dest_dir(new_dir)
            return True

    @check_handle()
    def get_save_path(self):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            # torrent_handle.save_path() is deprecated in newer versions of Libtorrent. We should use
            # self.handle.status().save_path to query the save path of a torrent. However, this attribute
            # is only included in libtorrent 1.0.9+
            status = self.handle.status()
            return status.save_path if hasattr(status, 'save_path') else self.handle.save_path()

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
        vod = {'vod_prebuf_frac': self.calc_prebuf_frac(),
               'vod_prebuf_frac_consec': self.calc_prebuf_frac(True)} if self.config.get_mode() == DLMODE_VOD else {}

        return DownloadState(self, self.lt_status, self.error, vod)

    @task
    async def save_resume_data(self):
        """
        Save the resume data of a download. This method returns when the resume data is available.
        Note that this method only calls save_resume_data once on subsequent calls.
        """
        if 'save_resume_data' not in self.futures:
            handle = await self.get_handle()
            handle.save_resume_data()

        try:
            await self.wait_for_alert('save_resume_data_alert', None,
                                      'save_resume_data_failed_alert',
                                      lambda a: SaveResumeDataError(a.error.message()))
        except (CancelledError, SaveResumeDataError) as e:
            self._logger.error("Resume data failed to save: %s", e)

    def calc_prebuf_frac(self, consecutive=False):
        if self.config.get_mode() == DLMODE_VOD and self.get_vod_fileindex() >= 0 and self.vod_seekpos is not None:
            if self.endbuffsize:
                return self.get_byte_progress(
                    [(self.get_vod_fileindex(), self.vod_seekpos, self.vod_seekpos + self.prebuffsize),
                     (self.get_vod_fileindex(), -self.endbuffsize - 1, -1)], consecutive=consecutive)
            return self.get_byte_progress(
                [(self.get_vod_fileindex(), self.vod_seekpos, self.vod_seekpos + self.prebuffsize)],
                consecutive=consecutive)
        return 0.0

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

        ltsession = self.ltmgr.get_session(self.config.get_hops())
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
        for _, futures in self.futures.items():
            for future, _, _ in futures:
                future.cancel()
        self.futures.clear()
        await self.shutdown_task_manager()

    def stop(self, user_stopped=None):
        self._logger.debug("Stopping %s", self.tdef.get_name())

        if user_stopped is not None:
            self.config.set_user_stopped(user_stopped)

        if self.handle and self.handle.is_valid():
            self.set_vod_mode(False)
            self.handle.pause()
            future = next(as_completed([self.wait_for_alert('save_resume_data_alert', None),
                                        self.wait_for_alert('save_resume_data_failed_alert', None)]))
            self.checkpoint()
            return future
        return succeed(None)

    def resume(self):
        self._logger.debug("Resuming %s", self.tdef.get_name())

        self.config.set_user_stopped(False)

        if self.handle and self.handle.is_valid():
            self.handle.set_upload_mode(self.get_upload_mode())
            self.handle.resume()
            self.set_vod_mode(self.config.get_mode() == DLMODE_VOD)

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

        if not self.handle or not self.handle.is_valid():
            # Libtorrent hasn't received or initialized this download yet
            # 1. Check if we have data for this infohash already (don't overwrite it if we do!)
            basename = hexlify(self.tdef.get_infohash()) + '.state'
            filename = self.ltmgr.get_checkpoint_dir() / basename
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
                self._logger.warning("either file does not exist or is not file")
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
