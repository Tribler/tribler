"""
A wrapper around a libtorrent download.

Author(s): Arno Bakker, Egbert Bouman
"""
from __future__ import absolute_import

import base64
import logging
import os
import shutil
import sys
import time
from binascii import hexlify
from threading import RLock

import libtorrent as lt

import six
from six.moves import xrange

from twisted.internet import reactor
from twisted.internet.defer import CancelledError, Deferred, succeed
from twisted.internet.task import LoopingCall
from twisted.python.failure import Failure

from Tribler.Core.DownloadConfig import DownloadConfigInterface, DownloadStartupConfig, get_default_dest_dir
from Tribler.Core.DownloadState import DownloadState
from Tribler.Core.Libtorrent import checkHandleAndSynchronize
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.Utilities import maketorrent
from Tribler.Core.Utilities.torrent_utils import get_info_from_handle
from Tribler.Core.exceptions import SaveResumeDataError
from Tribler.Core.osutils import fix_filebasename
from Tribler.Core.simpledefs import DLMODE_NORMAL, DLMODE_VOD, DLSTATUS_SEEDING, DLSTATUS_STOPPED, \
    PERSISTENTSTATE_CURRENTVERSION, dlstatus_strings
from Tribler.pyipv8.ipv8.taskmanager import TaskManager

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
        self.pieces = [pieces[x:x + 20] for x in xrange(0, len(pieces), 20)]
        self.piecesize = self._download.tdef.get_piece_length()

        self.startpiece = get_info_from_handle(self._download.handle).map_file(
            self._download.get_vod_fileindex(), 0, 0)
        self.endpiece = get_info_from_handle(self._download.handle).map_file(
            self._download.get_vod_fileindex(), self._download.get_vod_filesize(), 0)

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


class LibtorrentDownloadImpl(DownloadConfigInterface, TaskManager):
    """ Download subclass that represents a libtorrent download."""

    def __init__(self, session, tdef):
        super(LibtorrentDownloadImpl, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        self.dllock = RLock()
        self.session = session
        self.tdef = tdef
        self.handle = None
        self.vod_index = None
        self.orig_files = None
        self.finished_deferred = Deferred()
        self.finished_deferred_already_called = False
        self.is_bootstrap_download = False

        if session:
            self.state_dir = self.session.config.get_state_dir()

        # With hidden True download will not be in GET/downloads set, as a result will not be shown in GUI
        self.hidden = False

        # To be able to return the progress of a stopped torrent, how far it got.
        self.progressbeforestop = 0.0
        self.filepieceranges = []

        # Libtorrent session manager, can be None at this point as the core could have
        # not been started. Will set in create_engine wrapper
        self.ltmgr = None

        # Libtorrent status
        self.lt_status = None
        self.error = None
        self.done = False
        self.pause_after_next_hashcheck = False
        self.checkpoint_after_next_hashcheck = False
        self.tracker_status = {}  # {url: [num_peers, status_str]}

        self.prebuffsize = 5 * 1024 * 1024
        self.endbuffsize = 0
        self.vod_seekpos = 0

        self.max_prebuffsize = 5 * 1024 * 1024

        self.pstate_for_restart = None

        self.cew_scheduled = False
        self.askmoreinfo = False

        self.correctedinfoname = u""
        self._checkpoint_disabled = False

        self.deferreds_resume = []
        self.deferreds_handle = []
        self.deferred_added = Deferred()
        self.deferred_removed = Deferred()

        self.handle_check_lc = self.register_task("handle_check", LoopingCall(self.check_handle))

    def __str__(self):
        return "LibtorrentDownloadImpl <name: '%s' hops: %d checkpoint_disabled: %d>" % \
               (self.correctedinfoname, self.get_hops(), self._checkpoint_disabled)

    def __repr__(self):
        return self.__str__()

    def get_def(self):
        return self.tdef

    def set_checkpoint_disabled(self, disabled=True):
        self._checkpoint_disabled = disabled

    def get_checkpoint_disabled(self):
        return self._checkpoint_disabled

    def check_handle(self):
        """
        Check whether the handle exists and is valid. If so, stop the looping call and fire the deferreds waiting
        for the handle.
        """
        if self.handle and self.handle.is_valid():
            self.handle_check_lc.stop()
            for deferred in self.deferreds_handle:
                deferred.callback(self.handle)

    def get_handle(self):
        """
        Returns a deferred that fires with a valid libtorrent download handle.
        """
        if self.handle and self.handle.is_valid():
            return succeed(self.handle)

        deferred = Deferred()
        self.deferreds_handle.append(deferred)
        return deferred

    def setup(self, dcfg=None, pstate=None, wrapperDelay=0, share_mode=False, checkpoint_disabled=False, hidden=False):
        """
        Create a Download object. Used internally by Session.
        @param dcfg DownloadStartupConfig or None (in which case
        a new DownloadConfig() is created and the result
        becomes the runtime config of this Download.
        :returns a Deferred to which a callback can be added which returns the result of
        network_create_engine_wrapper.
        """
        # Called by any thread, assume sessionlock is held
        self.set_checkpoint_disabled(checkpoint_disabled)
        self.hidden = hidden
        try:
            # The deferred to be returned
            deferred = Deferred()
            with self.dllock:
                # Copy dlconfig, from default if not specified
                cdcfg = dcfg or DownloadStartupConfig(state_dir=self.session.config.get_state_dir())

                self.is_bootstrap_download = cdcfg.is_bootstrap_download
                self.dlconfig = cdcfg.dlconfig.copy()
                self.dlconfig.lock = self.dllock
                self.dlconfig.set_callback(self.dlconfig_changed_callback)

                if not isinstance(self.tdef, TorrentDefNoMetainfo):
                    self.set_corrected_infoname()
                    self.set_filepieceranges()

                self._logger.debug(u"setup: %s", hexlify(self.tdef.get_infohash()))

                def schedule_create_engine():
                    self.cew_scheduled = True
                    create_engine_wrapper_deferred = self.network_create_engine_wrapper(
                        (pstate or self.pstate_for_restart), share_mode=share_mode,
                        checkpoint_disabled=checkpoint_disabled)
                    create_engine_wrapper_deferred.chainDeferred(deferred)

                self.register_task("schedule_create_engine", reactor.callLater(wrapperDelay, schedule_create_engine))

            self.pstate_for_restart = pstate
            self.checkpoint()
            self.handle_check_lc.start(1, now=True)
            return deferred

        except Exception as e:
            self.error = e

    def network_create_engine_wrapper(self, pstate, checkpoint_disabled=False, share_mode=False, upload_mode=False):
        self.ltmgr = self.session.lm.ltmgr
        with self.dllock:
            self._logger.debug("LibtorrentDownloadImpl: network_create_engine_wrapper()")

            atp = {}
            atp["save_path"] = os.path.normpath(os.path.join(get_default_dest_dir(), self.get_dest_dir()))
            atp["storage_mode"] = lt.storage_mode_t.storage_mode_sparse
            atp["hops"] = self.get_hops()
            atp["flags"] = lt.add_torrent_params_flags_t.flag_paused | \
                           lt.add_torrent_params_flags_t.flag_duplicate_is_error | \
                           lt.add_torrent_params_flags_t.flag_update_subscribe

            if share_mode:
                atp["flags"] = atp["flags"] | lt.add_torrent_params_flags_t.flag_share_mode
            if upload_mode:
                atp["flags"] = atp["flags"] | lt.add_torrent_params_flags_t.flag_upload_mode

            self.set_checkpoint_disabled(checkpoint_disabled)

            resume_data = pstate.get('state', 'engineresumedata') if pstate else None
            if not isinstance(self.tdef, TorrentDefNoMetainfo):
                metainfo = self.tdef.get_metainfo()
                torrentinfo = lt.torrent_info(metainfo)

                self.orig_files = [file_entry.path.decode('utf-8') for file_entry in torrentinfo.files()]
                is_multifile = len(self.orig_files) > 1
                commonprefix = os.path.commonprefix(self.orig_files) if is_multifile else ''
                swarmname = commonprefix.partition(os.path.sep)[0]

                if is_multifile and swarmname != self.correctedinfoname:
                    for i, filename_old in enumerate(self.orig_files):
                        filename_new = os.path.join(self.correctedinfoname, filename_old[len(swarmname) + 1:])
                        # Path should be unicode if Libtorrent is using std::wstring (on Windows),
                        # else we use str (on Linux).
                        try:
                            torrentinfo.rename_file(i, filename_new)
                        except TypeError:
                            torrentinfo.rename_file(i, filename_new.encode("utf-8"))
                        self.orig_files[i] = filename_new

                atp["ti"] = torrentinfo
                if resume_data and isinstance(resume_data, dict):
                    # Rewrite save_path as a global path, if it is given as a relative path
                    if "save_path" in resume_data and not os.path.isabs(resume_data["save_path"]):
                        resume_data["save_path"] = str(os.path.join(self.state_dir, resume_data["save_path"]))
                    atp["resume_data"] = lt.bencode(resume_data)
            else:
                atp["url"] = self.tdef.get_url() or "magnet:?xt=urn:btih:" + hexlify(self.tdef.get_infohash())
                atp["name"] = self.tdef.get_name_as_unicode()

        def on_torrent_added(handle):
            self.handle = handle

            if self.handle and self.handle.is_valid():
                self.set_selected_files()

                user_stopped = pstate.get('download_defaults', 'user_stopped') if pstate else False

                # If we lost resume_data always resume download in order to force checking
                if not user_stopped or not resume_data:
                    self.handle.resume()

                    # If we only needed to perform checking, pause download after it is complete
                    self.pause_after_next_hashcheck = user_stopped

                self.set_vod_mode(self.get_mode() == DLMODE_VOD)

                # Limit the amount of connections if we have specified that
                self.handle.set_max_connections(self.session.config.get_libtorrent_max_conn_download())

                # Set limit on download for a bootstrap file
                if self.is_bootstrap_download:
                    self.handle.set_download_limit(self.session.config.get_bootstrap_max_download_rate())

                return self

        def on_torrent_failed(failure):
            self._logger.error("Could not add torrent to LibtorrentManager %s", self.tdef.get_name_as_unicode())

            self.cew_scheduled = False

            return Failure((self, pstate))

        return self.ltmgr.add_torrent(self, atp).addCallbacks(on_torrent_added, on_torrent_failed)

    def get_anon_mode(self):
        return self.get_hops() > 0

    def set_vod_mode(self, enable=True):
        self._logger.debug("LibtorrentDownloadImpl: set_vod_mode for %s (enable = %s)", self.tdef.get_name(), enable)

        if enable:
            self.vod_seekpos = 0

            filename = self.get_selected_files()[0] if self.tdef.is_multifile_torrent() else self.tdef.get_name()
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
            self.handle.set_priority(0 if self.get_credit_mining() else 1)
            if self.get_vod_fileindex() >= 0:
                self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)

    def get_vod_fileindex(self):
        if self.vod_index is not None:
            return self.vod_index
        return -1

    @checkHandleAndSynchronize(0)
    def get_vod_filesize(self):
        fileindex = self.get_vod_fileindex()
        torrent_info = get_info_from_handle(self.handle)
        if fileindex >= 0 and torrent_info:
            file_entry = torrent_info.file_at(fileindex)
            return file_entry.size
        return 0

    @checkHandleAndSynchronize(0.0)
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
            return float(pieces_have) / pieces_all
        return 0.0

    @checkHandleAndSynchronize('')
    def get_pieces_base64(self):
        """
        Returns a base64 encoded bitmask of the pieces that we have.
        """
        bitstr = ""
        for bit in self.handle.status().pieces:
            bitstr += '1' if bit else '0'

        encoded_str = ""
        for i in range(0, len(bitstr), 8):
            encoded_str += chr(int(bitstr[i:i + 8].ljust(8, '0'), 2))
        return base64.b64encode(encoded_str)

    @checkHandleAndSynchronize(0.0)
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

                pieces += range(startpiece, endpiece)
            else:
                self._logger.info("LibtorrentDownloadImpl: could not get progress for incorrect fileindex")

        pieces = list(set(pieces))
        return self.get_piece_progress(pieces, consecutive)

    @checkHandleAndSynchronize()
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

    @checkHandleAndSynchronize()
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

                pieces += range(startpiece, endpiece)
            else:
                self._logger.info("LibtorrentDownloadImpl: could not set priority for incorrect fileindex")

        if pieces:
            pieces = list(set(pieces))
            self.set_piece_priority(pieces, priority)

    @checkHandleAndSynchronize()
    def process_alert(self, alert, alert_type):
        if alert.category() in [lt.alert.category_t.error_notification, lt.alert.category_t.performance_warning]:
            self._logger.debug("LibtorrentDownloadImpl: alert %s with message %s", alert_type, alert)

        alert_types = ('tracker_reply_alert', 'tracker_error_alert', 'tracker_warning_alert', 'metadata_received_alert',
                       'file_renamed_alert', 'performance_alert', 'torrent_checked_alert', 'torrent_finished_alert',
                       'save_resume_data_alert', 'save_resume_data_failed_alert')

        if alert_type in alert_types:
            getattr(self, 'on_' + alert_type)(alert)

    def on_save_resume_data_alert(self, alert):
        """
        Callback for the alert that contains the resume data of a specific download.
        This resume data will be written to a file on disk.
        """
        if self._checkpoint_disabled:
            return

        resume_data = alert.resume_data

        self.pstate_for_restart = self.get_persistent_download_config()

        # Make save_path relative if the torrent is saved in the Tribler state directory
        if self.state_dir and 'save_path' in resume_data and os.path.abspath(resume_data['save_path']):
            if self.state_dir == os.path.commonprefix([resume_data['save_path'], self.state_dir]):
                resume_data['save_path'] = str(os.path.relpath(resume_data['save_path'], self.state_dir))

        self.pstate_for_restart.set('state', 'engineresumedata', resume_data)
        self._logger.debug("%s get resume data %s", hexlify(resume_data['info-hash']), resume_data)

        # save it to file
        basename = hexlify(resume_data['info-hash']) + '.state'
        filename = os.path.join(self.session.get_downloads_pstate_dir(), basename)

        self._logger.debug("tlm: network checkpointing: to file %s", filename)

        self.pstate_for_restart.write_file(filename)

        # fire callback for all deferreds_resume
        for deferred_r in self.deferreds_resume:
            deferred_r.callback(resume_data)

        # empties the deferred list
        self.deferreds_resume = []

    def on_save_resume_data_failed_alert(self, alert):
        # fire errback for all deferreds_resume
        for deferred_r in self.deferreds_resume:
            deferred_r.errback(SaveResumeDataError(alert.msg))

        # empties the deferred list
        self.deferreds_resume = []

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

    def on_metadata_received_alert(self, alert):
        torrent_info = get_info_from_handle(self.handle)
        if not torrent_info:
            return

        metadata = {'info': lt.bdecode(torrent_info.metadata())}

        trackers = [tracker['url'] for tracker in self.handle.trackers()]
        if trackers:
            if len(trackers) > 1:
                metadata["announce-list"] = [trackers]
            else:
                metadata["announce"] = trackers[0]

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

        self.orig_files = [torrent_file.path.decode('utf-8') for torrent_file in torrent_files]
        self.set_corrected_infoname()
        self.set_filepieceranges()
        self.set_selected_files()

        self.checkpoint()

    def on_file_renamed_alert(self, alert):
        unwanteddir_abs = os.path.join(self.get_save_path().decode('utf-8'), self.unwanted_directory_name)
        if os.path.exists(unwanteddir_abs) and all(self.handle.file_priorities()):
            shutil.rmtree(unwanteddir_abs, ignore_errors=True)

    def on_performance_alert(self, alert):
        if self.get_anon_mode() or self.ltmgr.ltsessions is None:
            return

        # When the send buffer watermark is too low, double the buffer size to a
        # maximum of 50MiB. This is the same mechanism as Deluge uses.
        if alert.message().endswith("send buffer watermark too low (upload rate will suffer)"):
            settings = self.ltmgr.get_session().get_settings()
            if settings['send_buffer_watermark'] <= 26214400:
                self._logger.info(
                    "LibtorrentDownloadImpl: setting send_buffer_watermark to %s",
                    2 * settings['send_buffer_watermark'])
                settings['send_buffer_watermark'] *= 2
                self.ltmgr.set_session_settings(self.ltmgr.get_session(), settings)
        # When the write cache is too small, double the buffer size to a maximum
        # of 64MiB. Again, this is the same mechanism as Deluge uses.
        elif alert.message().endswith("max outstanding disk writes reached"):
            settings = self.ltmgr.get_session().get_settings()
            if settings['max_queued_disk_bytes'] <= 33554432:
                self._logger.info(
                    "LibtorrentDownloadImpl: setting max_queued_disk_bytes to %s",
                    2 * settings['max_queued_disk_bytes'])
                settings['max_queued_disk_bytes'] *= 2
                self.ltmgr.set_session_settings(self.ltmgr.get_session(), settings)

    def on_torrent_checked_alert(self, alert):
        if self.pause_after_next_hashcheck:
            self.pause_after_next_hashcheck = False
            self.handle.pause()
        if self.checkpoint_after_next_hashcheck:
            self.checkpoint_after_next_hashcheck = False
            self.checkpoint()

    @checkHandleAndSynchronize()
    def on_torrent_finished_alert(self, alert):
        self.update_lt_status(self.handle.status())
        if self.finished_deferred_already_called:
            self._logger.warning("LibtorrentDownloadImpl: tried to repeat the call to finished_callback %s",
                                 self.tdef.get_name())
        else:
            self.finished_deferred.callback(self)
            self.finished_deferred_already_called = True

        progress = self.get_state().get_progress()
        if self.get_mode() == DLMODE_VOD:
            if progress == 1.0:
                self.handle.set_sequential_download(False)
                self.handle.set_priority(0)
                if self.get_vod_fileindex() >= 0:
                    self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)
            elif progress < 1.0:
                # If we are in VOD mode and still need to download pieces and libtorrent
                # says we are finished, reset the piece priorities to 1.
                def reset_priorities():
                    if not self:
                        return
                    if self.get_state().get_progress() == 1.0:
                        self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)

                self.register_anonymous_task("reset_priorities", reactor.callLater(5, reset_priorities))

            if self.endbuffsize:
                self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)
                self.endbuffsize = 0

    def update_lt_status(self, lt_status):
        """ Update libtorrent stats and check if the download should be stopped."""
        self.lt_status = lt_status
        self._stop_if_finished()

    def _stop_if_finished(self):
        state = self.get_state()
        if state.get_status() == DLSTATUS_SEEDING:
            mode = self.get_seeding_mode()
            if mode == 'never' \
                    or (mode == 'ratio' and state.get_seeding_ratio() >= self.get_seeding_ratio()) \
                    or (mode == 'time' and state.get_seeding_time() >= self.get_seeding_time()):
                self.stop()

    def set_corrected_infoname(self):
        # H4xor this so the 'name' field is safe
        self.correctedinfoname = fix_filebasename(self.tdef.get_name_as_unicode())

        # Allow correctedinfoname to be overwritten for multifile torrents only
        if self.get_corrected_filename() and self.get_corrected_filename() != '' and 'files' in \
                self.tdef.get_metainfo()['info']:
            self.correctedinfoname = self.get_corrected_filename()

    @property
    def swarmname(self):
        """
        Return the swarm name of the torrent.
        """
        is_multifile = len(self.orig_files) > 1
        commonprefix = os.path.commonprefix(self.orig_files) if is_multifile else u''
        return commonprefix.partition(os.path.sep)[0]

    @property
    def unwanted_directory_name(self):
        """
        Return the name of the directory containing the unwanted files (files with a priority of 0).
        """
        return os.path.join(self.swarmname, u'.unwanted')

    @checkHandleAndSynchronize()
    def set_selected_files(self, selected_files=None):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):

            if selected_files is None:
                selected_files = self.get_selected_files()
            else:
                DownloadConfigInterface.set_selected_files(self, selected_files)

            unwanteddir_abs = os.path.join(self.get_save_path().decode('utf-8'), self.unwanted_directory_name)
            torrent_info = get_info_from_handle(self.handle)
            if not torrent_info or not hasattr(torrent_info, 'files'):
                self._logger.error("File info not available for torrent [%s]", self.correctedinfoname)
                return

            filepriorities = []
            torrent_storage = torrent_info.files()

            for index, orig_path in enumerate(self.orig_files):
                filename = orig_path[len(self.swarmname) + 1:] if self.swarmname else orig_path

                if filename in selected_files or not selected_files:
                    filepriorities.append(1)
                    new_path = orig_path
                else:
                    filepriorities.append(0)
                    new_path = os.path.join(self.unwanted_directory_name,
                                            '%s%d' % (hexlify(self.tdef.get_infohash()), index))

                # as from libtorrent 1.0, files returning file_storage (lazy-iterable)
                if hasattr(lt, 'file_storage') and isinstance(torrent_storage, lt.file_storage):
                    cur_path = torrent_storage.at(index).path.decode('utf-8')
                else:
                    cur_path = torrent_storage[index].path.decode('utf-8')

                if cur_path != new_path:
                    if not os.path.exists(unwanteddir_abs) and self.unwanted_directory_name in new_path:
                        try:
                            os.makedirs(unwanteddir_abs)
                            if sys.platform == "win32":
                                ctypes.windll.kernel32.SetFileAttributesW(
                                    unwanteddir_abs, 2)  # 2 = FILE_ATTRIBUTE_HIDDEN
                        except OSError:
                            self._logger.error("LibtorrentDownloadImpl: could not create %s" % unwanteddir_abs)
                            # Note: If the destination directory can't be accessed, libtorrent will not be able to store the files.
                            # This will result in a DLSTATUS_STOPPED_ON_ERROR.

                    # Path should be unicode if Libtorrent is using std::wstring (on Windows),
                    # else we use str (on Linux).
                    try:
                        self.handle.rename_file(index, new_path)
                    except TypeError:
                        self.handle.rename_file(index, new_path.encode("utf-8"))

            # if in share mode, don't change priority of the file
            if not self.get_share_mode():
                self.handle.prioritize_files(filepriorities)

    @checkHandleAndSynchronize(False)
    def move_storage(self, new_dir):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            self.handle.move_storage(new_dir)
            self.set_dest_dir(new_dir)
            return True

    @checkHandleAndSynchronize()
    def get_save_path(self):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            # torrent_handle.save_path() is deprecated in newer versions of Libtorrent. We should use
            # self.handle.status().save_path to query the save path of a torrent. However, this attribute
            # is only included in libtorrent 1.0.9+
            status = self.handle.status()
            return status.save_path if hasattr(status, 'save_path') else self.handle.save_path()

    @checkHandleAndSynchronize()
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
               'vod_prebuf_frac_consec': self.calc_prebuf_frac(True)} if self.get_mode() == DLMODE_VOD else {}

        return DownloadState(self, self.lt_status, self.error, vod)

    def _on_resume_err(self, failure):
        failure.trap(CancelledError, SaveResumeDataError)
        self._logger.error("Resume data failed to save: %s", failure.getErrorMessage())

    def save_resume_data(self):
        """
        Save the resume data of a download. This method returns a deferred that fires when the resume data is available.
        Note that this method only calls save_resume_data once on subsequent calls.
        """
        if not self.deferreds_resume:
            self.get_handle().addCallback(lambda handle: handle.save_resume_data())

        defer_resume = Deferred()
        defer_resume.addErrback(self._on_resume_err)

        self.deferreds_resume.append(defer_resume)

        return defer_resume

    def set_moreinfo_stats(self, enable):
        """ Called by any thread """

        self.askmoreinfo = enable

    def calc_prebuf_frac(self, consecutive=False):
        if self.get_mode() == DLMODE_VOD and self.get_vod_fileindex() >= 0 and self.vod_seekpos is not None:
            if self.endbuffsize:
                return self.get_byte_progress(
                    [(self.get_vod_fileindex(), self.vod_seekpos, self.vod_seekpos + self.prebuffsize),
                     (self.get_vod_fileindex(), -self.endbuffsize - 1, -1)], consecutive=consecutive)
            else:
                return self.get_byte_progress(
                    [(self.get_vod_fileindex(), self.vod_seekpos, self.vod_seekpos + self.prebuffsize)],
                    consecutive=consecutive)
        else:
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
            peer_dict = {'id': hexlify(peer_info.pid.to_bytes()),
                         'extended_version': peer_info.client,
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

    @checkHandleAndSynchronize(default={})
    def get_tracker_status(self):
        # Make sure all trackers are in the tracker_status dict
        for announce_entry in self.handle.trackers():
            if announce_entry['url'] not in self.tracker_status:
                try:
                    url = six.text_type(announce_entry['url'])
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

        ltsession = self.ltmgr.get_session(self.get_hops())
        public = self.tdef and not self.tdef.is_private()

        result = self.tracker_status.copy()
        result['[DHT]'] = [dht_peers, 'Working' if ltsession.is_dht_running() and public else 'Disabled']
        result['[PeX]'] = [pex_peers, 'Working']
        return result

    def set_state_callback(self, usercallback):
        """ Called by any thread """
        with self.dllock:
            reactor.callFromThread(lambda: self.network_get_state(usercallback))

    def network_get_state(self, usercallback):
        """ Called by network thread """
        with self.dllock:
            ds = self.get_state()

            if usercallback:
                # Invoke the usercallback function via a new thread.
                # After the callback is invoked, the return values will be passed to the
                # returncallback for post-callback processing.
                if not self.done and not self.session.lm.shutdownstarttime:
                    when = usercallback(ds)
                    if when > 0.0 and not self.session.lm.shutdownstarttime:
                        # Schedule next invocation, either on general or DL specific
                        dc = reactor.callLater(when, lambda: self.network_get_state(usercallback))
                        self.register_anonymous_task("downloads_cb", dc)
            else:
                return ds

    def stop(self):
        self.set_user_stopped(True)
        return self.stop_remove(removestate=False, removecontent=False)

    def stop_remove(self, removestate=False, removecontent=False):
        """ Called by any thread. Called on Session.remove_download() """
        self.done = removestate
        return self.network_stop(removestate=removestate, removecontent=removecontent)

    def network_stop(self, removestate, removecontent):
        """ Called by network thread, but safe for any """
        self.shutdown_task_manager()

        out = None
        with self.dllock:
            self._logger.debug("LibtorrentDownloadImpl: network_stop %s", self.tdef.get_name())

            if self.handle is not None:
                self._logger.debug("LibtorrentDownloadImpl: network_stop: engineresumedata from torrent handle")
                self.pstate_for_restart = self.get_persistent_download_config()
                if removestate:
                    out = self.ltmgr.remove_torrent(self, removecontent)
                    self.handle = None
                else:
                    self.set_vod_mode(False)
                    self.handle.pause()
                    self.save_resume_data()
            else:
                self._logger.debug("LibtorrentDownloadImpl: network_stop: handle is None")
                self.cancel_pending_task("check_create_wrapper")

            if removestate:
                self.session.lm.remove_pstate(self.tdef.get_infohash())

        return out or succeed(None)

    def get_content_dest(self):
        """ Returns the file to which the downloaded content is saved. """
        return os.path.join(self.get_dest_dir(), self.correctedinfoname)

    def set_filepieceranges(self):
        """ Determine which file maps to which piece ranges for progress info """
        self._logger.debug("LibtorrentDownloadImpl: set_filepieceranges: %s", self.get_selected_files())

        metainfo = self.tdef.get_metainfo()
        self.filepieceranges = maketorrent.get_length_filepieceranges_from_metainfo(metainfo, [])[1]

    def restart(self):
        """ Restart the Download """
        self.set_user_stopped(False)
        self._logger.debug("LibtorrentDownloadImpl: restart: %s", self.tdef.get_name())

        # We stop a previous restart if it's active
        self.cancel_pending_task("check_create_wrapper")

        with self.dllock:
            if self.handle is None:
                self.cew_scheduled = True
                create_engine_wrapper_deferred = self.network_create_engine_wrapper(self.pstate_for_restart,
                                                                                    share_mode=self.get_share_mode(),
                                                                                    upload_mode=self.get_upload_mode())
                create_engine_wrapper_deferred.addCallback(self.session.lm.on_download_handle_created)
            else:
                self.handle.set_upload_mode(self.get_upload_mode())
                self.handle.resume()
                self.set_vod_mode(self.get_mode() == DLMODE_VOD)

    @checkHandleAndSynchronize([])
    def get_dest_files(self, exts=None):
        """
        You can give a list of extensions to return. If None: return all dest_files
        @return list of (torrent,disk) filename tuples.
        """

        dest_files = []

        for index, file_entry in enumerate(get_info_from_handle(self.handle).files()):
            if self.handle.file_priority(index) > 0:
                filename = file_entry.path
                ext = os.path.splitext(filename)[1].lstrip('.')
                if exts is None or ext in exts:
                    dest_files.append((filename, os.path.join(self.get_dest_dir(), filename.decode('utf-8'))))
        return dest_files

    def checkpoint(self):
        """
        Checkpoint this download. Returns a deferred that fires when the checkpointing is completed.
        """
        if self._checkpoint_disabled:
            self._logger.warning("Ignoring checkpoint() call as checkpointing is disabled for this download")
            return succeed(None)

        if not self.handle or not self.handle.is_valid():
            # Libtorrent hasn't received or initialized this download yet
            # 1. Check if we have data for this infohash already (don't overwrite it if we do!)
            basename = hexlify(self.tdef.get_infohash()) + '.state'
            filename = os.path.join(self.session.get_downloads_pstate_dir(), basename)
            if not os.path.isfile(filename):
                resume_data = self.pstate_for_restart.get('state', 'engineresumedata') \
                    if self.pstate_for_restart else None

                # 2. If there is no saved data for this infohash, checkpoint it without data so we do not
                #    lose it when we crash or restart before the download becomes known.
                resume_data = resume_data or {
                    'file-format': "libtorrent resume file",
                    'file-version': 1,
                    'info-hash': self.tdef.get_infohash()
                }
                alert = type('anonymous_alert', (object,), dict(resume_data=resume_data))
                self.on_save_resume_data_alert(alert)
            return succeed(None)

        return self.save_resume_data()

    def get_persistent_download_config(self):
        pstate = self.dlconfig.copy()

        pstate.set('download_defaults', 'mode', DLMODE_NORMAL)

        # Add state stuff
        if not pstate.has_section('state'):
            pstate.add_section('state')
        pstate.set('state', 'version', PERSISTENTSTATE_CURRENTVERSION)
        if isinstance(self.tdef, TorrentDefNoMetainfo):
            pstate.set('state', 'metainfo', {
                'infohash': self.tdef.get_infohash(), 'name': self.tdef.get_name_as_unicode(),
                'url': self.tdef.get_url()})
        else:
            pstate.set('state', 'metainfo', self.tdef.get_metainfo())

        if self.get_share_mode():
            pstate.set('state', 'share_mode', True)

        ds = self.get_state()
        dlstate = {'status': ds.get_status(), 'progress': ds.get_progress(), 'swarmcache': None}
        pstate.set('state', 'dlstate', dlstate)

        self._logger.debug("LibtorrentDownloadImpl: network_get_persistent_state: status %s progress %s",
                           dlstatus_strings[ds.get_status()], ds.get_progress())

        pstate.set('state', 'engineresumedata', None)
        return pstate

    def set_def(self, tdef):
        with self.dllock:
            self.tdef = tdef

    @checkHandleAndSynchronize()
    def add_trackers(self, trackers):
        if hasattr(self.handle, 'add_tracker'):
            for tracker in trackers:
                self.handle.add_tracker({'url': tracker, 'verified': False})

    @checkHandleAndSynchronize()
    def get_magnet_link(self):
        return lt.make_magnet_uri(self.handle)

    #
    # External addresses
    #
    def add_peer(self, addr):
        """ Add a peer address from 3rd source (not tracker, not DHT) to this download.
        @param (hostname_ip,port) tuple
        """
        self.get_handle().addCallback(lambda handle: handle.connect_peer(addr, 0))

    def set_priority(self, prio):
        self.get_handle().addCallback(lambda handle: handle.set_priority(prio))

    def dlconfig_changed_callback(self, section, name, new_value, old_value):
        if section == 'libtorrent' and name == 'max_upload_rate':
            self.get_handle().addCallback(lambda handle: handle.set_upload_limit(int(new_value * 1024)))
        elif section == 'libtorrent' and name == 'max_download_rate':
            self.get_handle().addCallback(lambda handle: handle.set_download_limit(int(new_value * 1024)))
        elif section == 'download_defaults' and name in ['correctedfilename', 'super_seeder']:
            return False
        return True

    @checkHandleAndSynchronize()
    def get_share_mode(self):
        return self.handle.status().share_mode

    def set_share_mode(self, share_mode):
        self.get_handle().addCallback(lambda handle: handle.set_share_mode(share_mode))

    @checkHandleAndSynchronize()
    def get_upload_mode(self):
        return self.handle.status().upload_mode

    def set_upload_mode(self, upload_mode):
        self.get_handle().addCallback(lambda handle: handle.set_upload_mode(upload_mode))

    def force_dht_announce(self):
        if self.handle:
            self.handle.force_dht_announce()
