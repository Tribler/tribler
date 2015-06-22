# Based on SwiftDownloadImpl.py by Arno Bakker, modified by Egbert Bouman for the use with libtorrent
import logging
import os
import sys
import time
from binascii import hexlify
from traceback import print_exc

import libtorrent as lt

from Tribler.Core import NoDispersyRLock
from Tribler.Core.APIImplementation import maketorrent
from Tribler.Core.DownloadConfig import DownloadStartupConfig, DownloadConfigInterface
from Tribler.Core.DownloadState import DownloadState
from Tribler.Core.Libtorrent import checkHandleAndSynchronize, waitForHandleAndSynchronize
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo, TorrentDef
from Tribler.Core.osutils import fix_filebasename
from Tribler.Core.simpledefs import (DLSTATUS_WAITING4HASHCHECK, DLSTATUS_HASHCHECKING, DLSTATUS_METADATA,
                                     DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_ALLOCATING_DISKSPACE,
                                     DLSTATUS_CIRCUITS, DLSTATUS_STOPPED, DLMODE_VOD, DLSTATUS_STOPPED_ON_ERROR,
                                     UPLOAD, DOWNLOAD, DLMODE_NORMAL, PERSISTENTSTATE_CURRENTVERSION, dlstatus_strings)


if sys.platform == "win32":
    try:
        import ctypes
    except:
        pass


class VODFile(object):

    def __init__(self, f, d):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._file = f
        self._download = d

        pieces = self._download.tdef.get_pieces()
        self.pieces = [pieces[x:x + 20]for x in xrange(0, len(pieces), 20)]
        self.piecesize = self._download.tdef.get_piece_length()

        self.startpiece = self._download.handle.get_torrent_info().map_file(self._download.get_vod_fileindex(), 0, 0)
        self.endpiece = self._download.handle.get_torrent_info().map_file(
            self._download.get_vod_fileindex(), self._download.get_vod_filesize(), 0)

    def read(self, *args):
        oldpos = self._file.tell()

        self._logger.debug('VODFile: get bytes %s - %s', oldpos, oldpos + args[0])

        while not self._file.closed and self._download.get_byte_progress([(self._download.get_vod_fileindex(), oldpos, oldpos + args[0])]) < 1 and self._download.vod_seekpos is not None:
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


class LibtorrentDownloadImpl(DownloadConfigInterface):

    """ Download subclass that represents a libtorrent download."""

    def __init__(self, session, tdef):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.dllock = NoDispersyRLock()
        self.session = session
        self.tdef = tdef
        self.handle = None
        self.vod_index = None

        # Just enough so error saving and get_state() works
        self.error = None
        # To be able to return the progress of a stopped torrent, how far it got.
        self.progressbeforestop = 0.0
        self.filepieceranges = []

        # Libtorrent session manager, can be None at this point as the core could have
        # not been started. Will set in create_engine wrapper
        self.ltmgr = None

        # Libtorrent status
        self.dlstates = [DLSTATUS_WAITING4HASHCHECK, DLSTATUS_HASHCHECKING, DLSTATUS_METADATA, DLSTATUS_DOWNLOADING,
                         DLSTATUS_SEEDING, DLSTATUS_SEEDING, DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_HASHCHECKING]
        self.dlstate = DLSTATUS_WAITING4HASHCHECK
        self.length = 0
        self.progress = 0.0
        self.bufferprogress = 0.0
        self.curspeeds = {DOWNLOAD: 0.0, UPLOAD: 0.0}  # bytes/s
        self.all_time_upload = 0.0
        self.all_time_download = 0.0
        self.finished_time = 0.0
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

    def get_def(self):
        return self.tdef

    def setup(self, dcfg=None, pstate=None, initialdlstatus=None, lm_network_engine_wrapper_created_callback=None, wrapperDelay=0):
        """
        Create a Download object. Used internally by Session.
        @param dcfg DownloadStartupConfig or None (in which case
        a new DownloadConfig() is created and the result
        becomes the runtime config of this Download.
        """
        # Called by any thread, assume sessionlock is held
        try:
            with self.dllock:
                # Copy dlconfig, from default if not specified
                if dcfg is None:
                    cdcfg = DownloadStartupConfig()
                else:
                    cdcfg = dcfg
                self.dlconfig = cdcfg.dlconfig.copy()
                self.dlconfig.lock = self.dllock
                self.dlconfig.set_callback(self.dlconfig_changed_callback)

                if not isinstance(self.tdef, TorrentDefNoMetainfo):
                    self.set_corrected_infoname()
                    self.set_filepieceranges()

                self.dlstate = DLSTATUS_CIRCUITS if self.get_hops() > 0 else self.dlstate

                self._logger.debug(u"setup: initialdlstatus %s %s", hexlify(self.tdef.get_infohash()), initialdlstatus)

                self.create_engine_wrapper(lm_network_engine_wrapper_created_callback, pstate,
                                           initialdlstatus=initialdlstatus, wrapperDelay=wrapperDelay)

            self.pstate_for_restart = pstate

        except Exception as e:
            with self.dllock:
                self.error = e
                print_exc()

    def create_engine_wrapper(self, lm_network_engine_wrapper_created_callback, pstate, initialdlstatus=None, wrapperDelay=0):
        with self.dllock:
            if not self.cew_scheduled:
                self.ltmgr = self.session.lm.ltmgr
                dht_ok = not isinstance(self.tdef, TorrentDefNoMetainfo) or self.ltmgr.is_dht_ready()
                tunnel_community = self.ltmgr.trsession.lm.tunnel_community
                tunnels_ready = tunnel_community.tunnels_ready(self.get_hops()) if tunnel_community else 1

                session_ok = tunnels_ready == 1

                if not self.ltmgr or not dht_ok or not session_ok:
                    self._logger.info(u"LTMGR/DHT/session not ready, rescheduling create_engine_wrapper")
                    create_engine_wrapper_lambda = lambda: self.create_engine_wrapper(
                        lm_network_engine_wrapper_created_callback, pstate, initialdlstatus=initialdlstatus)
                    self.session.lm.rawserver.add_task(create_engine_wrapper_lambda, 5)
                    self.dlstate = DLSTATUS_CIRCUITS if not session_ok else DLSTATUS_METADATA
                else:
                    network_create_engine_wrapper_lambda = lambda: self.network_create_engine_wrapper(
                        lm_network_engine_wrapper_created_callback, pstate, initialdlstatus)
                    self.session.lm.rawserver.add_task(network_create_engine_wrapper_lambda, wrapperDelay)
                    self.cew_scheduled = True

    def network_create_engine_wrapper(self, lm_network_engine_wrapper_created_callback, pstate, initialdlstatus=None):
        # Called by any thread, assume dllock already acquired
        self._logger.debug("LibtorrentDownloadImpl: create_engine_wrapper()")

        atp = {}
        atp["save_path"] = os.path.abspath(self.get_dest_dir())
        atp["storage_mode"] = lt.storage_mode_t.storage_mode_sparse
        atp["paused"] = True
        atp["auto_managed"] = False
        atp["duplicate_is_error"] = True
        atp["hops"] = self.get_hops()

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
            has_resume_data = resume_data and isinstance(resume_data, dict)
            if has_resume_data:
                atp["resume_data"] = lt.bencode(resume_data)
            self._logger.info("%s %s", self.tdef.get_name_as_unicode(), dict((k, v)
                              for k, v in resume_data.iteritems() if k not in ['pieces', 'piece_priority', 'peers']) if has_resume_data else None)
        else:
            atp["url"] = self.tdef.get_url() or "magnet:?xt=urn:btih:" + hexlify(self.tdef.get_infohash())
            atp["name"] = self.tdef.get_name_as_unicode()

        self.handle = self.ltmgr.add_torrent(self, atp)

        if self.handle:
            self.set_selected_files()

            # If we lost resume_data always resume download in order to force checking
            if initialdlstatus != DLSTATUS_STOPPED or not resume_data:
                self.handle.resume()

                # If we only needed to perform checking, pause download after it is complete
                self.pause_after_next_hashcheck = initialdlstatus == DLSTATUS_STOPPED

            if self.get_mode() == DLMODE_VOD:
                self.set_vod_mode(True)

            self.handle.resolve_countries(True)

        else:
            self._logger.info("Could not add torrent to LibtorrentManager %s", self.tdef.get_name_as_unicode())

        with self.dllock:
            self.cew_scheduled = False

        if lm_network_engine_wrapper_created_callback is not None:
            lm_network_engine_wrapper_created_callback(self, pstate)

    def get_anon_mode(self):
        return self.get_hops() > 0

    def set_vod_mode(self, enable=True):
        self._logger.debug("LibtorrentDownloadImpl: set_vod_mode for %s (enable = %s)", self.handle.name(), enable)

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

            self.progress = self.get_byte_progress([(self.get_vod_fileindex(), 0, -1)])
            self._logger.debug("LibtorrentDownloadImpl: going into VOD mode %s", filename)
        else:
            self.handle.set_sequential_download(False)
            self.handle.set_priority(0)
            if self.get_vod_fileindex() >= 0:
                self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)

    def get_vod_fileindex(self):
        if self.vod_index is not None:
            return self.vod_index
        return -1

    @checkHandleAndSynchronize(0)
    def get_vod_filesize(self):
        fileindex = self.get_vod_fileindex()
        if fileindex >= 0:
            file_entry = self.handle.get_torrent_info().file_at(fileindex)
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

    @checkHandleAndSynchronize(0.0)
    def get_byte_progress(self, byteranges, consecutive=False):
        pieces = []
        for fileindex, bytes_begin, bytes_end in byteranges:
            if fileindex >= 0:
                # Ensure the we remain within the file's boundaries
                file_entry = self.handle.get_torrent_info().file_at(fileindex)
                bytes_begin = min(
                    file_entry.size, bytes_begin) if bytes_begin >= 0 else file_entry.size + (bytes_begin + 1)
                bytes_end = min(file_entry.size, bytes_end) if bytes_end >= 0 else file_entry.size + (bytes_end + 1)

                startpiece = self.handle.get_torrent_info().map_file(fileindex, bytes_begin, 0).piece
                endpiece = self.handle.get_torrent_info().map_file(fileindex, bytes_end, 0).piece + 1
                startpiece = max(startpiece, 0)
                endpiece = min(endpiece, self.handle.get_torrent_info().num_pieces())

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
                    "LibtorrentDownloadImpl: could not set priority for non-existing piece %d / %d", piece, len(piecepriorities))
        if do_prio:
            self.handle.prioritize_pieces(piecepriorities)
        else:
            self._logger.info("LibtorrentDownloadImpl: skipping set_piece_priority")

    @checkHandleAndSynchronize()
    def set_byte_priority(self, byteranges, priority):
        pieces = []
        for fileindex, bytes_begin, bytes_end in byteranges:
            if fileindex >= 0:
                # Ensure the we remain within the file's boundaries
                file_entry = self.handle.get_torrent_info().file_at(fileindex)
                bytes_begin = min(
                    file_entry.size, bytes_begin) if bytes_begin >= 0 else file_entry.size + (bytes_begin + 1)
                bytes_end = min(file_entry.size, bytes_end) if bytes_end >= 0 else file_entry.size + (bytes_end + 1)

                startpiece = self.handle.get_torrent_info().map_file(fileindex, bytes_begin, 0).piece
                endpiece = self.handle.get_torrent_info().map_file(fileindex, bytes_end, 0).piece + 1
                startpiece = max(startpiece, 0)
                endpiece = min(endpiece, self.handle.get_torrent_info().num_pieces())

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
                       'file_renamed_alert', 'performance_alert', 'torrent_checked_alert', 'torrent_finished_alert')

        if alert_type in alert_types:
            getattr(self, 'on_' + alert_type)(alert)
        else:
            self.update_lt_stats()

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
        self.metadata = {'info': lt.bdecode(self.handle.get_torrent_info().metadata())}

        trackers = [tracker['url'] for tracker in self.handle.trackers()]
        if trackers:
            if len(trackers) > 1:
                self.metadata["announce-list"] = [trackers]
            else:
                self.metadata["announce"] = trackers[0]

        self.tdef = TorrentDef.load_from_dict(self.metadata)
        self.orig_files = [torrent_file.path.decode('utf-8') for torrent_file in lt.torrent_info(self.metadata).files()]
        self.set_corrected_infoname()
        self.set_filepieceranges()

        if self.session.lm.rtorrent_handler:
            self.session.lm.rtorrent_handler.save_torrent(self.tdef)
        elif self.session.lm.torrent_db:
            self.session.lm.torrent_db.addExternalTorrent(self.tdef, extra_info={'status': 'good'})

        self.checkpoint()

    def on_file_renamed_alert(self, alert):
        if os.path.exists(self.unwanteddir_abs) and not os.listdir(self.unwanteddir_abs) and all(self.handle.file_priorities()):
            os.rmdir(self.unwanteddir_abs)

    def on_performance_alert(self, alert):
        if self.get_anon_mode():
            return

        # When the send buffer watermark is too low, double the buffer size to a
        # maximum of 50MiB. This is the same mechanism as Deluge uses.
        if alert.message().endswith("send buffer watermark too low (upload rate will suffer)"):
            settings = self.ltmgr.get_session().settings()
            if settings.send_buffer_watermark <= 26214400:
                self._logger.info(
                    "LibtorrentDownloadImpl: setting send_buffer_watermark to %s", 2 * settings.send_buffer_watermark)
                settings.send_buffer_watermark = 2 * settings.send_buffer_watermark
                self.ltmgr.get_session().set_settings(settings)
        # When the write cache is too small, double the buffer size to a maximum
        # of 64MiB. Again, this is the same mechanism as Deluge uses.
        elif alert.message().endswith("max outstanding disk writes reached"):
            settings = self.ltmgr.get_session().settings()
            if settings.max_queued_disk_bytes <= 33554432:
                self._logger.info(
                    "LibtorrentDownloadImpl: setting max_queued_disk_bytes to %s", 2 * settings.max_queued_disk_bytes)
                settings.max_queued_disk_bytes = 2 * settings.max_queued_disk_bytes
                self.ltmgr.get_session().set_settings(settings)

    def on_torrent_checked_alert(self, alert):
        if self.pause_after_next_hashcheck:
            self.pause_after_next_hashcheck = False
            self.handle.pause()
        if self.checkpoint_after_next_hashcheck:
            self.checkpoint_after_next_hashcheck = False
            self.checkpoint()

    @checkHandleAndSynchronize()
    def on_torrent_finished_alert(self, alert):
        self.update_lt_stats()
        if self.get_mode() == DLMODE_VOD:
            if self.progress == 1.0:
                self.handle.set_sequential_download(False)
                self.handle.set_priority(0)
                if self.get_vod_fileindex() >= 0:
                    self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)
            elif self.progress < 1.0:
                # If we are in VOD mode and still need to download pieces and libtorrent
                # says we are finished, reset the piece priorities to 1.
                def reset_priorities():
                    if not self:
                        return
                    if self.handle.status().progress == 1.0:
                        self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)
                self.session.lm.rawserver.add_task(reset_priorities, 5)

            if self.endbuffsize:
                self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)
                self.endbuffsize = 0

    def update_lt_stats(self):
        status = self.handle.status()
        self.dlstate = self.dlstates[status.state] if not status.paused else DLSTATUS_STOPPED
        self.dlstate = DLSTATUS_STOPPED_ON_ERROR if self.dlstate == DLSTATUS_STOPPED and status.error else self.dlstate
        if self.get_mode() == DLMODE_VOD:
            self.progress = self.get_byte_progress([(self.get_vod_fileindex(), 0, -1)])
            self.dlstate = (
                DLSTATUS_SEEDING if self.progress == 1.0 else self.dlstate) if not status.paused else DLSTATUS_STOPPED
        else:
            self.progress = status.progress
        self.error = status.error.decode('utf-8') if status.error else None
        self.length = float(status.total_wanted)
        self.curspeeds[DOWNLOAD] = float(status.download_payload_rate) if self.dlstate not in [
            DLSTATUS_STOPPED, DLSTATUS_STOPPED] else 0.0
        self.curspeeds[UPLOAD] = float(status.upload_payload_rate) if self.dlstate not in [
            DLSTATUS_STOPPED, DLSTATUS_STOPPED] else 0.0
        self.all_time_upload = status.all_time_upload
        self.all_time_download = status.all_time_download
        self.finished_time = status.finished_time

    def set_corrected_infoname(self):
        # H4xor this so the 'name' field is safe
        self.correctedinfoname = fix_filebasename(self.tdef.get_name_as_unicode())

        # Allow correctedinfoname to be overwritten for multifile torrents only
        if self.get_corrected_filename() and self.get_corrected_filename() != '' and 'files' in self.tdef.get_metainfo()['info']:
            self.correctedinfoname = self.get_corrected_filename()

    @checkHandleAndSynchronize()
    def set_selected_files(self, selected_files=None):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):

            if selected_files is None:
                selected_files = self.get_selected_files()
            else:
                DownloadConfigInterface.set_selected_files(self, selected_files)

            is_multifile = len(self.orig_files) > 1
            commonprefix = os.path.commonprefix(self.orig_files) if is_multifile else u''
            swarmname = commonprefix.partition(os.path.sep)[0]
            unwanteddir = os.path.join(swarmname, u'.unwanted')
            unwanteddir_abs = os.path.join(self.handle.save_path().decode('utf-8'), unwanteddir)

            filepriorities = []
            for index, orig_path in enumerate(self.orig_files):
                filename = orig_path[len(swarmname) + 1:] if swarmname else orig_path

                if filename in selected_files or not selected_files:
                    filepriorities.append(1)
                    new_path = orig_path
                else:
                    filepriorities.append(0)
                    new_path = os.path.join(unwanteddir, '%s%d' % (hexlify(self.tdef.get_infohash()), index))

                cur_path = self.handle.get_torrent_info().files()[index].path.decode('utf-8')
                if cur_path != new_path:
                    if not os.path.exists(unwanteddir_abs) and unwanteddir in new_path:
                        try:
                            os.makedirs(unwanteddir_abs)
                            if sys.platform == "win32":
                                ctypes.windll.kernel32.SetFileAttributesW(
                                    unwanteddir_abs, 2)  # 2 = FILE_ATTRIBUTE_HIDDEN
                        except:
                            self._logger.error("LibtorrentDownloadImpl: could not create %s" % unwanteddir_abs)
                            # Note: If the destination directory can't be accessed, libtorrent will not be able to store the files.
                            # This will result in a DLSTATUS_STOPPED_ON_ERROR.

                    # Path should be unicode if Libtorrent is using std::wstring (on Windows),
                    # else we use str (on Linux).
                    try:
                        self.handle.rename_file(index, new_path)
                    except TypeError:
                        self.handle.rename_file(index, new_path.encode("utf-8"))

            self.handle.prioritize_files(filepriorities)

            self.unwanteddir_abs = unwanteddir_abs

    @checkHandleAndSynchronize(False)
    def move_storage(self, new_dir):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            self.handle.move_storage(new_dir)
            self.set_dest_dir(new_dir)
            return True

    @checkHandleAndSynchronize()
    def get_save_path(self):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            return self.handle.save_path()

    @checkHandleAndSynchronize()
    def force_recheck(self):
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            if self.dlstate == DLSTATUS_STOPPED:
                self.pause_after_next_hashcheck = True
            self.checkpoint_after_next_hashcheck = True
            self.handle.resume()
            self.handle.force_recheck()

    def get_status(self):
        """ Returns the status of the download.
        @return DLSTATUS_*
        """
        with self.dllock:
            return self.dlstate

    def get_length(self):
        """ Returns the size of the torrent content.
        @return float
        """
        with self.dllock:
            return self.length

    def get_progress(self):
        """ Return fraction of content downloaded.
        @return float 0..1
        """
        with self.dllock:
            return self.progress

    def get_current_speed(self, dir):
        """ Return last reported speed in bytes/s
        @return float
        """
        with self.dllock:
            return self.curspeeds[dir]

    def set_moreinfo_stats(self, enable):
        """ Called by any thread """

        self.askmoreinfo = enable

    def network_get_stats(self, getpeerlist):
        """
        @return (status, stats, seeding_stats, logmsgs, coopdl_helpers, coopdl_coordinator)
        """
        # Called by any thread, assume dllock already acquired

        stats = {}
        stats['down'] = self.curspeeds[DOWNLOAD]
        stats['up'] = self.curspeeds[UPLOAD]
        stats['frac'] = self.progress
        stats['wanted'] = self.length
        stats['stats'] = self.network_create_statistics_reponse()
        stats['time'] = self.network_calc_eta()
        stats['vod_prebuf_frac'] = self.network_calc_prebuf_frac()
        stats['vod_prebuf_frac_consec'] = self.network_calc_prebuf_frac_consec()
        stats['vod'] = self.get_mode()
        stats['vod_playable'] = self.progress == 1.0 or (
            stats['vod_prebuf_frac'] == 1.0 and self.curspeeds[DOWNLOAD] > 0.0)
        stats['vod_playable_after'] = self.network_calc_prebuf_eta()
        stats['vod_stats'] = self.network_get_vod_stats()
        stats['spew'] = self.network_create_spew_from_peerlist() if getpeerlist or self.askmoreinfo else None
        stats['tracker_status'] = self.network_tracker_status() if getpeerlist or self.askmoreinfo else None

        seeding_stats = {}
        seeding_stats['total_up'] = self.all_time_upload
        seeding_stats['total_down'] = self.all_time_download
        seeding_stats['time_seeding'] = self.finished_time

        logmsgs = []

        self._logger.debug("Torrent %s PROGRESS %s DLSTATE %s SEEDTIME %s",
                           self.handle.name(), self.progress, self.dlstate, self.finished_time)

        return (self.dlstate, stats, seeding_stats, logmsgs)

    @checkHandleAndSynchronize()
    def network_create_statistics_reponse(self):
        status = self.handle.status()
        numTotSeeds = status.num_complete if status.num_complete >= 0 else status.list_seeds
        numTotPeers = status.num_incomplete if status.num_incomplete >= 0 else status.list_peers
        numleech = status.num_peers - status.num_seeds
        numseeds = status.num_seeds
        pieces = status.pieces
        upTotal = status.all_time_upload
        downTotal = status.all_time_download
        return LibtorrentStatisticsResponse(numTotSeeds, numTotPeers, numseeds, numleech, pieces, upTotal, downTotal)

    def network_calc_eta(self):
        bytestogof = (1.0 - self.progress) * float(self.length)
        dlspeed = max(0.000001, self.curspeeds[DOWNLOAD])
        return bytestogof / dlspeed

    def network_calc_prebuf_frac(self):
        if self.get_mode() == DLMODE_VOD and self.get_vod_fileindex() >= 0 and self.vod_seekpos is not None:
            if self.endbuffsize:
                return self.get_byte_progress(
                    [(self.get_vod_fileindex(), self.vod_seekpos, self.vod_seekpos + self.prebuffsize),
                     (self.get_vod_fileindex(), -self.endbuffsize - 1, -1)])
            else:
                return self.get_byte_progress([(self.get_vod_fileindex(), self.vod_seekpos, self.vod_seekpos + self.prebuffsize)])
        else:
            return 0.0

    def network_calc_prebuf_frac_consec(self):
        if self.get_mode() == DLMODE_VOD and self.get_vod_fileindex() >= 0 and self.vod_seekpos is not None:
            if self.endbuffsize:
                return self.get_byte_progress(
                    [(self.get_vod_fileindex(), self.vod_seekpos, self.vod_seekpos + self.prebuffsize),
                     (self.get_vod_fileindex(), -self.endbuffsize - 1, -1)], consecutive=True)
            else:
                return self.get_byte_progress([(self.get_vod_fileindex(), self.vod_seekpos, self.vod_seekpos + self.prebuffsize)], consecutive=True)
        else:
            return 0.0

    def network_calc_prebuf_eta(self):
        bytestogof = (1.0 - self.network_calc_prebuf_frac()) * float(self.prebuffsize)
        dlspeed = max(0.000001, self.curspeeds[DOWNLOAD])
        return bytestogof / dlspeed

    def network_get_vod_stats(self):
        d = {}
        d['played'] = None
        d['late'] = None
        d['dropped'] = None
        d['stall'] = None
        d['pos'] = None
        d['prebuf'] = None
        d['firstpiece'] = 0
        d['npieces'] = ((self.length + 1023) / 1024)
        return d

    def network_create_spew_from_peerlist(self):
        plist = []
        with self.dllock:
            peer_infos = self.handle.get_peer_info()
        for peer_info in peer_infos:

            # Only consider fully connected peers.
            # Disabling for now, to avoid presenting the user with conflicting information
            # (partially connected peers are included in seeder/leecher stats).
            # if peer_info.flags & peer_info.connecting or peer_info.flags & peer_info.handshake:
            #     continue

            peer_dict = {}
            peer_dict['id'] = peer_info.pid
            peer_dict['extended_version'] = peer_info.client
            peer_dict['ip'] = peer_info.ip[0]
            peer_dict['port'] = peer_info.ip[1]
            # optimistic_unchoke = 0x800 seems unavailable in python bindings
            peer_dict['optimistic'] = bool(peer_info.flags & 2048)
            peer_dict['direction'] = 'L' if bool(peer_info.flags & peer_info.local_connection) else 'R'
            peer_dict['uprate'] = peer_info.payload_up_speed
            peer_dict['uinterested'] = bool(peer_info.flags & peer_info.remote_interested)
            peer_dict['uchoked'] = bool(peer_info.flags & peer_info.remote_choked)
            peer_dict['uhasqueries'] = peer_info.upload_queue_length > 0
            peer_dict['uflushed'] = peer_info.used_send_buffer > 0
            peer_dict['downrate'] = peer_info.payload_down_speed
            peer_dict['dinterested'] = bool(peer_info.flags & peer_info.interesting)
            peer_dict['dchoked'] = bool(peer_info.flags & peer_info.choked)
            peer_dict['snubbed'] = bool(peer_info.flags & 4096)  # snubbed = 0x1000 seems unavailable in python bindings
            peer_dict['utotal'] = peer_info.total_upload
            peer_dict['dtotal'] = peer_info.total_download
            peer_dict['completed'] = peer_info.progress
            peer_dict['have'] = peer_info.pieces
            peer_dict['speed'] = peer_info.remote_dl_rate
            peer_dict['country'] = peer_info.country
            peer_dict['connection_type'] = peer_info.connection_type
            plist.append(peer_dict)

        return plist

    @checkHandleAndSynchronize()
    def network_tracker_status(self):
        # Make sure all trackers are in the tracker_status dict
        for announce_entry in self.handle.trackers():
            if announce_entry['url'] not in self.tracker_status:
                try:
                    url = unicode(announce_entry['url'])
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
        public = self.tdef and not isinstance(self.tdef, TorrentDefNoMetainfo) and not self.tdef.is_private()

        result = self.tracker_status.copy()
        result['[DHT]'] = [dht_peers, 'Working' if ltsession.is_dht_running() and public else 'Disabled']
        result['[PeX]'] = [pex_peers, 'Working' if not self.get_anon_mode() else 'Disabled']
        return result

    def set_state_callback(self, usercallback, getpeerlist=False, delay=0.0):
        """ Called by any thread """
        with self.dllock:
            network_get_state_lambda = lambda: self.network_get_state(usercallback, getpeerlist)
            self.session.lm.rawserver.add_task(network_get_state_lambda, delay)

    def network_get_state(self, usercallback, getpeerlist):
        """ Called by network thread """
        with self.dllock:
            if self.handle is None:
                self._logger.debug("LibtorrentDownloadImpl: network_get_state: Download not running")
                if self.dlstate != DLSTATUS_CIRCUITS:
                    progress = self.progressbeforestop
                else:
                    tunnel_community = self.ltmgr.trsession.lm.tunnel_community
                    progress = tunnel_community.tunnels_ready(self.get_hops()) if tunnel_community else 1

                ds = DownloadState(self, self.dlstate, self.error, progress)
            else:
                (status, stats, seeding_stats, logmsgs) = self.network_get_stats(getpeerlist)
                ds = DownloadState(self, status, self.error, self.get_progress(), stats=stats,
                                   seeding_stats=seeding_stats, filepieceranges=self.filepieceranges, logmsgs=logmsgs)
                self.progressbeforestop = ds.get_progress()

            if usercallback:
                # Invoke the usercallback function via a new thread.
                # After the callback is invoked, the return values will be passed to the
                # returncallback for post-callback processing.
                if not self.done:
                    # runs on the reactor
                    def session_getstate_usercallback_target():
                        when, getpeerlist = usercallback(ds)
                        if when > 0.0:
                            # Schedule next invocation, either on general or DL specific
                            self.session.lm.rawserver.add_task(lambda: self.network_get_state(usercallback, getpeerlist), when)

                    self.session.lm.rawserver.add_task_in_thread(session_getstate_usercallback_target)
            else:
                return ds

    def stop(self):
        """ Called by any thread """
        self.stop_remove(removestate=False, removecontent=False)

    def stop_remove(self, removestate=False, removecontent=False):
        """ Called by any thread. Called on Session.remove_download() """
        self.done = removestate
        self.network_stop(removestate=removestate, removecontent=removecontent)

    def network_stop(self, removestate, removecontent):
        """ Called by network thread, but safe for any """
        with self.dllock:
            self._logger.debug("LibtorrentDownloadImpl: network_stop %s", self.tdef.get_name())

            pstate = self.network_get_persistent_state()
            if self.handle is not None:
                self._logger.debug("LibtorrentDownloadImpl: network_stop: engineresumedata from torrent handle")
                if removestate:
                    self.ltmgr.remove_torrent(self, removecontent)
                    self.handle = None
                else:
                    self.set_vod_mode(False)
                    self.handle.pause()
                    pstate.set('state', 'engineresumedata', self.handle.write_resume_data()
                               if isinstance(self.tdef, TorrentDef) else None)
                self.pstate_for_restart = pstate
            else:
                # This method is also called at Session shutdown, where one may
                # choose to checkpoint its Download. If the Download was
                # stopped before, pstate_for_restart contains its resumedata.
                # and that should be written into the checkpoint.
                #
                if self.pstate_for_restart is not None:
                    self._logger.debug(
                        "LibtorrentDownloadImpl: network_stop: Reusing previously saved engineresume data for checkpoint")
                    # Don't copy full pstate_for_restart, as the torrent
                    # may have gone from e.g. HASHCHECK at startup to STOPPED
                    # now, at shutdown. In other words, it was never active
                    # in this session and the pstate_for_restart still says
                    # HASHCHECK.
                    pstate.set('state', 'engineresumedata', self.pstate_for_restart.get('state', 'engineresumedata'))
                else:
                    self._logger.debug(
                        "LibtorrentDownloadImpl: network_stop: Could not reuse engineresumedata as pstart_for_restart is None")

            # Offload the removal of the dlcheckpoint to another thread
            if removestate:
                self.session.lm.remove_pstate(self.tdef.get_infohash())

            return (self.tdef.get_infohash(), pstate)

    def get_content_dest(self):
        """ Returns the file to which the downloaded content is saved. """
        return os.path.join(self.get_dest_dir(), self.correctedinfoname)

    def set_filepieceranges(self):
        """ Determine which file maps to which piece ranges for progress info """
        self._logger.debug("LibtorrentDownloadImpl: set_filepieceranges: %s", self.get_selected_files())

        metainfo = self.tdef.get_metainfo()
        self.filepieceranges = maketorrent.get_length_filepieceranges_from_metainfo(metainfo, [])[1]

    def restart(self, initialdlstatus=None):
        """ Restart the Download """
        # Called by any thread
        self._logger.debug("LibtorrentDownloadImpl: restart: %s", self.tdef.get_name())

        with self.dllock:
            if self.handle is None:
                self.error = None
                self.create_engine_wrapper(
                    self.session.lm.network_engine_wrapper_created_callback, self.pstate_for_restart, initialdlstatus=initialdlstatus)
            else:
                self.handle.resume()
                self.set_vod_mode(self.get_mode() == DLMODE_VOD)

    @checkHandleAndSynchronize([])
    def get_dest_files(self, exts=None):
        """
        You can give a list of extensions to return. If None: return all dest_files
        @return list of (torrent,disk) filename tuples.
        """

        dest_files = []
        for index, file_entry in enumerate(self.handle.get_torrent_info().files()):
            if self.handle.file_priority(index) > 0:
                filename = file_entry.path
                ext = os.path.splitext(filename)[1].lstrip('.')
                if exts is None or ext in exts:
                    dest_files.append((filename, os.path.join(self.get_dest_dir(), filename.decode('utf-8'))))
        return dest_files

    def checkpoint(self):
        """ Called by any thread """
        (infohash, pstate) = self.network_checkpoint()
        checkpoint = lambda: self.session.lm.save_download_pstate(infohash, pstate)
        self.session.lm.rawserver.add_task(checkpoint, 0)

    def network_checkpoint(self):
        """ Called by network thread """
        with self.dllock:
            pstate = self.network_get_persistent_state()
            resdata = None
            if self.handle is None:
                if self.pstate_for_restart is not None:
                    resdata = self.pstate_for_restart.get('state', 'engineresumedata')
            elif isinstance(self.tdef, TorrentDef):
                resdata = self.handle.write_resume_data()
            pstate.set('state', 'engineresumedata', resdata)
            return (self.tdef.get_infohash(), pstate)

    def network_get_persistent_state(self):
        # Assume sessionlock is held

        pstate = self.dlconfig.copy()

        # Reset unpicklable params
        pstate.set('downloadconfig', 'mode', DLMODE_NORMAL)

        # Add state stuff
        if not pstate.has_section('state'):
            pstate.add_section('state')
        pstate.set('state', 'version', PERSISTENTSTATE_CURRENTVERSION)
        if isinstance(self.tdef, TorrentDefNoMetainfo):
            pstate.set('state', 'metainfo', {
                       'infohash': self.tdef.get_infohash(), 'name': self.tdef.get_name_as_unicode(), 'url': self.tdef.get_url()})
        else:
            pstate.set('state', 'metainfo', self.tdef.get_metainfo())

        ds = self.network_get_state(None, False)
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
    @waitForHandleAndSynchronize()
    def add_peer(self, addr):
        """ Add a peer address from 3rd source (not tracker, not DHT) to this download.
        @param (hostname_ip,port) tuple
        """
        self.handle.connect_peer(addr, 0)

    @waitForHandleAndSynchronize(True)
    def dlconfig_changed_callback(self, section, name, new_value, old_value):
        if section == 'downloadconfig' and name == 'max_upload_rate':
            self.handle.set_upload_limit(int(new_value * 1024))
        elif section == 'downloadconfig' and name == 'max_download_rate':
            self.handle.set_download_limit(int(new_value * 1024))
        elif section == 'downloadconfig' and name in ['correctedfilename', 'super_seeder']:
            return False
        return True


class LibtorrentStatisticsResponse:

    def __init__(self, numTotSeeds, numTotPeers, numseeds, numleech, have, upTotal, downTotal):
        self.numTotSeeds = numTotSeeds
        self.numTotPeers = numTotPeers
        self.numSeeds = numseeds
        self.numPeers = numleech
        self.have = have
        self.upTotal = upTotal
        self.downTotal = downTotal
        self.numConCandidates = 0
        self.numConInitiated = 0
