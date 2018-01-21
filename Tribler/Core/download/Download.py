"""
All download objects.
"""
import base64
import logging
import os
import random
import sys
import time
from binascii import hexlify
from copy import deepcopy
from traceback import print_exc

import libtorrent
from twisted.internet import defer, reactor
from twisted.internet.defer import Deferred, CancelledError, succeed
from twisted.internet.task import LoopingCall

from Tribler.Core import NoDispersyRLock
from Tribler.Core.download import check_handle_and_synchronize
from Tribler.Core.download.DownloadConfig import DownloadConfig
from Tribler.Core.download.DownloadHandle import DownloadHandle
from Tribler.Core.download.DownloadPersistence import DownloadSnapshot, PERSISTENTSTATE_CURRENTVERSION
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo, TorrentDef
from Tribler.Core.Utilities import maketorrent
from Tribler.Core.download.DownloadPersistence import DownloadResumeInfo
from Tribler.Core.download.definitions import DownloadDirection, DownloadStatus, DownloadMode
from Tribler.Core.download.utilities import torrent_info, bencode, DANGEROUS_ALERT_CATEGORIES, bdecode
from Tribler.Core.exceptions import SaveResumeDataError
from Tribler.Core.osutils import fix_filebasename
from Tribler.dispersy.taskmanager import TaskManager

if sys.platform == "win32":
    try:
        import ctypes
    except ImportError:
        pass


class VODFile(object):
    """
    A file object used to read video from when live streaming.
    """
    def __init__(self, f, d):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._file = f
        self._download = d

        pieces = self._download.tdef.get_pieces()
        self.pieces = [pieces[x:x + 20]for x in xrange(0, len(pieces), 20)]
        self.piecesize = self._download.tdef.get_piece_length()

        self.startpiece = self._download.handle.get_info().map_file(
            self._download.get_vod_file_index(), 0, 0)
        self.endpiece = self._download.handle.get_info().map_file(
            self._download.get_vod_file_index(), self._download.get_vod_filesize(), 0)

    def read(self, *args):
        oldpos = self._file.tell()

        self._logger.debug('VODFile: get bytes %s - %s', oldpos, oldpos + args[0])

        while not self._file.closed and self._download.get_byte_progress([(self._download.get_vod_file_index(), oldpos, oldpos + args[0])]) < 1 and self._download.vod_seekpos is not None:
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
        self._download.set_byte_priority([(self._download.get_vod_file_index(), 0, newpos)], 0)
        self._download.set_byte_priority([(self._download.get_vod_file_index(), newpos, -1)], 1)

        self._logger.debug('VODFile: seek, get pieces %s', self._download.handle.piece_priorities())
        self._logger.debug('VODFile: seek, got pieces %s', [
                           int(piece) for piece in self._download.handle.get_status().pieces])

    def close(self, *args):
        self._file.close(*args)

    @property
    def closed(self):
        return self._file.closed


class Download(TaskManager):
    """
    A download in Tribler.
    """
    def __init__(self, download_manager, torrent, config=None):
        super(Download, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        self.download_manager = download_manager
        self.torrent = torrent
        self.config = config or DownloadConfig()

        self.lock = NoDispersyRLock()

        # Libtorrent session manager, can be None at this point as the core could have
        # not been started. Will set in create_engine wrapper
        self.session_manager = None
        self.handle = None
        self.vod_index = None
        self.orig_files = None

        # Just enough so error saving and get_state() works
        self.error = None
        # To be able to return the progress of a stopped torrent, how far it got.
        self.progressbeforestop = 0.0
        self.filepieceranges = []

        # Libtorrent status
        self.download_state = DownloadStatus.WAITING_FOR_HASH_CHECK
        self.done = False
        self.pause_after_next_hashcheck = False
        self.checkpoint_after_next_hashcheck = False
        self.tracker_status = {}  # {url: [num_peers, status_str]}

        self.prebuffsize = 5 * 1024 * 1024
        self.endbuffsize = 0
        self.vod_seekpos = 0

        self.max_prebuffsize = 5 * 1024 * 1024

        self.cew_scheduled = False

        self.correctedinfoname = u""

        self.deferreds_resume = []
        self.deferreds_handle = []
        self.deferred_removed = Deferred()

        self.handle_check_lc = self.register_task("handle_check", LoopingCall(self.check_handle))

    def __str__(self):
        return "LibtorrentDownloadImpl <name: '%s' hops: %d>" % \
               (self.correctedinfoname, self.config.get_number_hops())

    def __repr__(self):
        return self.__str__()

    def get_torrent(self):
        return self.torrent

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

    def setup(self, config, wrapper_delay=0, share_mode=False):
        """
        Create a download object. Used internally by Session.
        @param config DownloadStartupConfig or None (in which case
        a new DownloadConfig() is created and the result
        becomes the runtime config of this download.
        :returns a Deferred to which a callback can be added which returns the result of
        create_engine_wrapper.
        """
        # Called by any thread, assume sessionlock is held
        self.handle_check_lc.start(1, now=False)

        try:
            # The deferred to be returned
            deferred = Deferred()
            with self.lock:
                # Copy config, from default if not specified
                self.config = config

                if not isinstance(self.torrent, TorrentDefNoMetainfo):
                    self.set_corrected_infoname()
                    self.set_filepieceranges()

                if self.config.get_number_hops() > 0:
                    self.download_state = DownloadStatus.CIRCUITS

                self._logger.debug(u"setup: %s", hexlify(self.torrent.get_infohash()))

                def schedule_create_engine_call(_):
                    self.register_task("schedule_create_engine",
                                       reactor.callLater(wrapper_delay, schedule_create_engine))

                def schedule_create_engine():
                    self.cew_scheduled = True
                    create_engine_wrapper_deferred = self.create_engine_wrapper(share_mode)
                    create_engine_wrapper_deferred.chainDeferred(deferred)

                # Add a lambda callback that ignored the parameter of the callback which schedules
                # a task using the taskmanager with wrapperDelay as delay.
                self.can_create_engine_wrapper().addCallback(schedule_create_engine_call)

            self.checkpoint()
            return deferred

        except Exception as e:
            with self.lock:
                self.error = e
                print_exc()

    def can_create_engine_wrapper(self):
        """
        Periodically checks whether the engine wrapper can be created.
        Notifies when it's ready by calling the callback of the deferred being returned.
        :return: A deferred that will be called when you can create the engine wrapper.
        """
        can_create_deferred = Deferred()
        
        def do_check():
            with self.lock:
                if not self.cew_scheduled:
                    self.session_manager = self.download_manager.session_manager
                    dht_ok = not isinstance(self.torrent, TorrentDefNoMetainfo) or self.session_manager.is_dht_ready()
                    tunnel_community = self.session_manager.tribler_session.download_manager.tunnel_community
                    if tunnel_community:
                        tunnels_ready = tunnel_community.tunnels_ready(self.config.get_number_hops())
                    else:
                        tunnels_ready = 1

                    if not self.session_manager or not dht_ok or tunnels_ready < 1:
                        self._logger.info(u"DownloadSessionHandler/DHT/session not ready, rescheduling create_engine_wrapper")

                        if tunnels_ready < 1:
                            self.download_state = DownloadStatus.CIRCUITS
                            tunnel_community.build_tunnels(self.config.get_number_hops())
                        else:
                            self.download_state = DownloadStatus.METADATA

                        # Schedule this function call to be called again in 5 seconds
                        self.register_task("check_create_wrapper", reactor.callLater(5, do_check))
                    else:
                        can_create_deferred.callback(True)
                else:
                    # Schedule this function call to be called again in 5 seconds
                    self.register_task("check_create_wrapper", reactor.callLater(5, do_check))

        do_check()
        return can_create_deferred

    def create_engine_wrapper(self, share_mode=False):
        with self.lock:
            self._logger.debug("LibtorrentDownloadImpl: create_engine_wrapper()")

            resume_info = DownloadResumeInfo.read_from_directory(self.download_manager.get_downloads_resume_info_directory(), )
            resume_data = resume_info.get_resume_data() if resume_info else None

            atp = self._create_atp(resume_data, share_mode)
            self.handle = self.session_manager.add_torrent(self, atp)

            if self.handle.is_valid():
                self.set_selected_files()

                user_stopped = resume_info.state['user_stopped'] if resume_info else False

                # If we lost resume_data always resume download in order to force checking
                if not user_stopped or not resume_data:
                    self.handle.resume()

                    # If we only needed to perform checking, pause download after it is complete
                    self.pause_after_next_hashcheck = user_stopped

                if self.config.get_mode() == DownloadMode.VOD:
                    self.set_vod_mode(True)

                # Limit the amount of connections if we have specified that
                max_conn_download = self.download_manager.config.get_downloading_max_connections_per_download()
                if max_conn_download != -1:
                    self.handle.set_max_connections(max(2, max_conn_download))
            else:
                self._logger.error("Could not add torrent to DownloadSessionManager %s", self.torrent.get_name_as_unicode())

                self.cew_scheduled = False

                # Return a deferred with the errback already being called
                return defer.fail((self, resume_info))

            self.cew_scheduled = False

            # Return a deferred with the callback already being called
            return defer.succeed(self)

    def _create_atp(self, resume_data, share_mode):
        atp = DownloadHandle.default_atp(share_mode)
        atp.update({
            'save_path': os.path.abspath(self.config.get_destination_dir()),
            'hops': self.config.get_number_hops(),
        })


        if not isinstance(self.torrent, TorrentDefNoMetainfo):
            metainfo = self.torrent.get_meta_info()
            torrentinfo = torrent_info(metainfo)

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
                atp["resume_data"] = bencode(resume_data)
        else:
            atp["url"] = self.torrent.get_url() or "magnet:?xt=urn:btih:" + hexlify(self.torrent.get_infohash())
            atp["name"] = self.torrent.get_name_as_unicode()

        return atp

    def get_anon_mode(self):
        return self.config.get_number_hops() > 0

    def set_vod_mode(self, enable=True):
        self._logger.debug("LibtorrentDownloadImpl: set_vod_mode for %s (enable = %s)", self.torrent.get_name(), enable)

        if enable:
            self.vod_seekpos = 0

            filename = self.config.get_selected_files()[0] if self.torrent.is_multifile_torrent() else self.torrent.get_name()

            self.prebuffsize = max(int(self.get_vod_filesize() * 0.05), self.max_prebuffsize)
            self.endbuffsize = 1 * 1024 * 1024

            self.handle.set_sequential_download(True)
            self.handle.set_priority(255)
            self.set_byte_priority([(self.get_vod_file_index(), self.prebuffsize, -self.endbuffsize)], 0)
            self.set_byte_priority([(self.get_vod_file_index(), 0, self.prebuffsize)], 1)
            self.set_byte_priority([(self.get_vod_file_index(), -self.endbuffsize, -1)], 1)

            self._logger.debug("LibtorrentDownloadImpl: going into VOD mode %s", filename)
        else:
            self.handle.set_sequential_download(False)
            self.handle.set_priority(0)
            if self.get_vod_file_index() >= 0:
                self.set_byte_priority([(self.get_vod_file_index(), 0, -1)], 1)

    def get_vod_file_index(self):
        filename = self.config.get_selected_files()[0] if self.torrent.is_multifile_torrent() else self.torrent.get_name()
        vod_index = self.torrent.get_index_of_file_in_files(filename) if self.torrent.is_multifile_torrent() else 0
        return vod_index

    @check_handle_and_synchronize(0)
    def get_vod_filesize(self):
        fileindex = self.get_vod_file_index()
        if fileindex >= 0:
            file_entry = self.handle.get_info().file_at(fileindex)
            return file_entry.size
        return 0

    @check_handle_and_synchronize('')
    def get_pieces_base64(self):
        """
        Returns a base64 encoded bitmask of the pieces that we have.
        """
        bitstr = ""
        for bit in self.handle.get_status().pieces:
            bitstr += '1' if bit else '0'

        encoded_str = ""
        for i in range(0, len(bitstr), 8):
            encoded_str += chr(int(bitstr[i:i+8].ljust(8, '0'), 2))
        return base64.b64encode(encoded_str)

    @check_handle_and_synchronize(0)
    def get_num_pieces(self):
        """
        Return the total number of pieces
        """
        info = self.handle.get_info()
        if info:
            return info.num_pieces()

    @check_handle_and_synchronize()
    def set_piece_priority(self, pieces_need, priority):
        do_prio = False
        pieces_have = self.handle.get_status().pieces
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

    @check_handle_and_synchronize()
    def set_byte_priority(self, byteranges, priority):
        pieces = []
        for fileindex, bytes_begin, bytes_end in byteranges:
            if fileindex >= 0:
                # Ensure the we remain within the file's boundaries
                file_entry = self.handle.get_info().file_at(fileindex)
                bytes_begin = min(
                    file_entry.size, bytes_begin) if bytes_begin >= 0 else file_entry.size + (bytes_begin + 1)
                bytes_end = min(file_entry.size, bytes_end) if bytes_end >= 0 else file_entry.size + (bytes_end + 1)

                startpiece = self.handle.get_info().map_file(fileindex, bytes_begin, 0).piece
                endpiece = self.handle.get_info().map_file(fileindex, bytes_end, 0).piece + 1
                startpiece = max(startpiece, 0)
                endpiece = min(endpiece, self.handle.get_info().num_pieces())

                pieces += range(startpiece, endpiece)
            else:
                self._logger.info("LibtorrentDownloadImpl: could not set priority for incorrect fileindex")

        if pieces:
            pieces = list(set(pieces))
            self.set_piece_priority(pieces, priority)

    @check_handle_and_synchronize()
    def process_alert(self, alert, alert_type):
        if alert.category() in DANGEROUS_ALERT_CATEGORIES:
            self._logger.debug("LibtorrentDownloadImpl: alert %s with message %s", alert_type, alert)

        alert_types = ('tracker_reply_alert', 'tracker_error_alert', 'tracker_warning_alert', 'metadata_received_alert',
                       'file_renamed_alert', 'performance_alert', 'torrent_checked_alert', 'torrent_finished_alert',
                       'save_resume_data_alert', 'save_resume_data_failed_alert')

        if alert_type in alert_types:
            getattr(self, 'on_' + alert_type)(alert)
        else:
            self._stop_if_finished()

    def on_save_resume_data_alert(self, alert):
        """
        Callback for the alert that contains the resume data of a specific download.
        This resume data will be written to a file on disk.
        """
        resume_data = alert.resume_data

        self._logger.debug("%s get resume data %s", hexlify(resume_data['info-hash']), resume_data)

        self.get_resume_info().write_to_directory(self.download_manager.get_downloads_resume_info_directory())

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
        torrent_info = self.handle.get_info()
        if not torrent_info:
            return

        metadata = {'info': bdecode(torrent_info.metadata())}

        trackers = [tracker['url'] for tracker in self.handle.trackers()]
        if trackers:
            if len(trackers) > 1:
                metadata["announce-list"] = [trackers]
            else:
                metadata["announce"] = trackers[0]

        self.torrent = TorrentDef.load_from_dict(metadata)
        self.orig_files = [torrent_file.path.decode('utf-8') for torrent_file in torrent_info(metadata).files()]
        self.set_corrected_infoname()
        self.set_filepieceranges()
        self.set_selected_files()

        if self.download_manager.rtorrent_handler:
            self.download_manager.rtorrent_handler.save_torrent(self.torrent)
        elif self.download_manager.torrent_db:
            self.download_manager.torrent_db.addExternalTorrent(self.torrent, extra_info={'status': 'good'})

        self.checkpoint()

    def on_performance_alert(self, alert):
        if self.get_anon_mode() or self.session_manager.ltsessions is None:
            return

        # When the send buffer watermark is too low, double the buffer size to a
        # maximum of 50MiB. This is the same mechanism as Deluge uses.
        if alert.message().endswith("send buffer watermark too low (upload rate will suffer)"):
            settings = self.session_manager.get_settings()
            if settings['send_buffer_watermark'] <= 26214400:
                self._logger.info(
                    "LibtorrentDownloadImpl: setting send_buffer_watermark to %s",
                    2 * settings['send_buffer_watermark'])
                settings['send_buffer_watermark'] *= 2
                self.session_manager.get_session().set_settings(settings)
        # When the write cache is too small, double the buffer size to a maximum
        # of 64MiB. Again, this is the same mechanism as Deluge uses.
        elif alert.message().endswith("max outstanding disk writes reached"):
            settings = self.session_manager.get_settings()
            if settings['max_queued_disk_bytes'] <= 33554432:
                self._logger.info(
                    "LibtorrentDownloadImpl: setting max_queued_disk_bytes to %s",
                    2 * settings['max_queued_disk_bytes'])
                settings['max_queued_disk_bytes'] *= 2
                self.session_manager.get_session().set_settings(settings)

    def on_torrent_checked_alert(self, alert):
        if self.pause_after_next_hashcheck:
            self.pause_after_next_hashcheck = False
            self.handle.pause()
        if self.checkpoint_after_next_hashcheck:
            self.checkpoint_after_next_hashcheck = False
            self.checkpoint()

    @check_handle_and_synchronize()
    def on_torrent_finished_alert(self, alert):
        self._stop_if_finished()
        if self.config.get_mode() == DownloadMode.VOD:
            if self.get_progress() == 1.0:
                self.handle.set_sequential_download(False)
                self.handle.set_priority(0)
                if self.get_vod_file_index() >= 0:
                    self.set_byte_priority([(self.get_vod_file_index(), 0, -1)], 1)
            elif self.get_progress() < 1.0:
                # If we are in VOD mode and still need to download pieces and libtorrent
                # says we are finished, reset the piece priorities to 1.
                def reset_priorities():
                    if not self:
                        return
                    if self.handle.get_status().progress == 1.0:
                        self.set_byte_priority([(self.get_vod_file_index(), 0, -1)], 1)
                random_id = ''.join(random.choice('0123456789abcdef') for _ in xrange(30))
                self.register_task("reset_priorities_%s" % random_id, reactor.callLater(5, reset_priorities))

            if self.endbuffsize:
                self.set_byte_priority([(self.get_vod_file_index(), 0, -1)], 1)
                self.endbuffsize = 0

    def _stop_if_finished(self):
        if self.download_state == DownloadStatus.SEEDING:
            mode = self.config.get_seeding_mode()
            if mode == 'never':
                self.stop()
            if mode == 'ratio' and self.handle.get_seeding_statistics['ratio'] >= self.config.get_seeding_ratio():
                self.stop()
            if mode == 'time' and self.handle.get_seeding_statistics['time_seeding'] >= self.config.get_seeding_time():
                self.stop()

    def set_corrected_infoname(self):
        # H4xor this so the 'name' field is safe
        self.correctedinfoname = fix_filebasename(self.torrent.get_name_as_unicode())

        # Allow correctedinfoname to be overwritten for multifile torrents only
        if self.config.has_corrected_filename() and 'files' in self.torrent.get_meta_info()['info']:
            self.correctedinfoname = self.config.get_corrected_filename()

    @check_handle_and_synchronize()
    def set_selected_files(self, selected_files=None):
        if not isinstance(self.torrent, TorrentDefNoMetainfo):

            if selected_files is None:
                selected_files = self.config.get_selected_files()
            else:
                self.config.set_selected_files(selected_files)

            is_multifile = len(self.orig_files) > 1
            commonprefix = os.path.commonprefix(self.orig_files) if is_multifile else u''
            swarmname = commonprefix.partition(os.path.sep)[0]
            unwanted_directory = os.path.join(swarmname, u'.unwanted')

            filepriorities = []
            torrent_storage = self.handle.get_info().files()

            for index, orig_path in enumerate(self.orig_files):
                filename = orig_path[len(swarmname) + 1:] if swarmname else orig_path

                if filename in selected_files or not selected_files:
                    filepriorities.append(1)
                    new_path = orig_path
                else:
                    filepriorities.append(0)
                    new_path = os.path.join(unwanted_directory, '%s%d' % (hexlify(self.torrent.get_infohash()), index))

                # as from libtorrent 1.0, files returning file_storage (lazy-iterable)
                if hasattr(libtorrent, 'file_storage') and isinstance(torrent_storage, libtorrent.file_storage):
                    cur_path = torrent_storage.at(index).path.decode('utf-8')
                else:
                    cur_path = torrent_storage[index].path.decode('utf-8')

                if cur_path != new_path:
                    try:
                        self.handle.update_path(index, self.get_save_path(), unwanted_directory, new_path)
                    except OSError:
                        self._logger.error("LibtorrentDownloadImpl: could not create %s" % unwanted_directory)
                        # Note: If the destination directory can't be accessed, libtorrent will not be able to store the files.
                        # This will result in a DLSTATUS_STOPPED_ON_ERROR.

            # if in share mode, don't change priority of the file
            if not self.get_share_mode():
                self.handle.prioritize_files(filepriorities)

    @check_handle_and_synchronize(False)
    def move_storage(self, new_dir):
        self.handle.move_storage(new_dir)
        self.config.set_destination_dir(new_dir)

    @check_handle_and_synchronize()
    def get_save_path(self):
        self.handle.get_save_path()

    @check_handle_and_synchronize()
    def force_recheck(self):
        if self.download_state == DownloadStatus.STOPPED:
            self.pause_after_next_hashcheck = True
        self.checkpoint_after_next_hashcheck = True
        self.handle.force_recheck()

    def get_status(self):
        """ Returns the status of the download.
        @return DLSTATUS_*
        """
        with self.lock:
            return self.download_state

    def get_length(self):
        """ Returns the size of the torrent content.
        @return float
        """
        with self.lock:
            return self.handle.get_length()

    def get_progress(self):
        """ Return fraction of content downloaded.
        @return float 0..1
        """
        with self.lock:
            return self.handle.get_byte_progress([(self.get_vod_file_index(), 0, -1)])

    def get_current_speed(self, direction):
        """ Return last reported speed in bytes/s
        @return float
        """
        with self.lock:
            if direction == DownloadDirection.UP:
                return self.handle.get_current_up_bytes()
            elif direction == DownloadDirection.DOWN:
                return self.handle.get_current_up_bytes()

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

    def get_statistics(self, get_peer_list):
        """
        @return (status, stats, seeding_stats, logmsgs, coopdl_helpers, coopdl_coordinator)
        """
        # Called by any thread, assume lock already acquired
        download_state = self.handle.get_download_state()
        statistics = self.handle.get_statistics(get_peer_list or self.config.get_more_info())
        statistics.update({
            'time': self.calculate_eta(),
            'vod': self.config.get_mode(),
            'vod_prebuf_frac': self.network_calc_prebuf_frac(),
            'vod_prebuf_frac_consec': self.network_calc_prebuf_frac(consecutive=True)
        })
        if self.config.get_mode() == DownloadMode.VOD:
            statistics['frac'] = self.get_progress()
        if get_peer_list:
            statistics['tracker_status'] = self.network_tracker_status()

        seeding_statistics = self.handle.get_seeding_statistics()

        return download_state, statistics, seeding_statistics

    @check_handle_and_synchronize()
    def network_statistics(self):
        return self.handle.get_network_statistics()

    def calculate_eta(self):
        bytes_to_go = (1.0 - self.get_progress()) * self.get_length()
        dlspeed = max(0.000001, self.handle.get_current_down_bytes())
        return float(bytes_to_go) / dlspeed

    def network_calc_prebuf_frac(self, consecutive=False):
        if self.config.get_mode() == DownloadMode.VOD and self.get_vod_file_index() >= 0 and self.vod_seekpos is not None:
            if self.endbuffsize:
                return self.get_byte_progress(
                    [(self.get_vod_file_index(), self.vod_seekpos, self.vod_seekpos + self.prebuffsize),
                     (self.get_vod_file_index(), -self.endbuffsize - 1, -1)], consecutive=consecutive)
            else:
                return self.get_byte_progress([(self.get_vod_file_index(), self.vod_seekpos, self.vod_seekpos + self.prebuffsize)],
                                              consecutive=consecutive)
        else:
            return 0.0

    @check_handle_and_synchronize(default={})
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

        ltsession = self.session_manager.get_session(self.config.get_number_hops())
        public = self.torrent and not self.torrent.is_private()

        result = self.tracker_status.copy()
        result['[DHT]'] = [dht_peers, 'Working' if ltsession.is_dht_running() and public else 'Disabled']
        result['[PeX]'] = [pex_peers, 'Working' if not self.get_anon_mode() else 'Disabled']
        return result

    def set_state_callback(self, usercallback, getpeerlist=False):
        """ Called by any thread """
        with self.lock:
            reactor.callFromThread(lambda: self.network_get_state(usercallback, getpeerlist))

    def network_get_state(self, usercallback, getpeerlist):
        """ Called by network thread """
        with self.lock:
            if self.handle is None:
                self._logger.debug("LibtorrentDownloadImpl: network_get_state: download not running")
                if self.download_state != DownloadStatus.CIRCUITS:
                    progress = self.progressbeforestop
                else:
                    tunnel_community = self.session_manager.tribler_session.download_manager.tunnel_community
                    progress = tunnel_community.tunnels_ready(self.config.get_number_hops()) if tunnel_community else 1

                download_state = DownloadSnapshot(self, self.download_state, self.error, progress)
            else:
                (status, stats, seeding_stats) = self.get_statistics(getpeerlist)
                download_state = DownloadSnapshot(self, status, self.error, self.get_progress(), stats=stats,
                                                  seeding_stats=seeding_stats, filepieceranges=self.filepieceranges)
                self.progressbeforestop = download_state.get_progress()

            if usercallback:
                # Invoke the usercallback function via a new thread.
                # After the callback is invoked, the return values will be passed to the
                # returncallback for post-callback processing.
                if not self.done and not self.download_manager.shutdownstarttime:
                    # runs on the reactor
                    def session_getstate_usercallback_target():
                        when, getpeerlist = usercallback(download_state)
                        if when > 0.0 and not self.download_manager.shutdownstarttime:
                            # Schedule next invocation, either on general or DL specific
                            def reschedule_cb():
                                dc = reactor.callLater(when, lambda: self.network_get_state(usercallback, getpeerlist))
                                random_id = ''.join(random.choice('0123456789abcdef') for _ in xrange(30))
                                self.register_task("downloads_cb_%s" % random_id, dc)

                            reactor.callFromThread(reschedule_cb)

                    reactor.callInThread(session_getstate_usercallback_target)
            else:
                return download_state

    def stop(self):
        self.user_stopped = True
        return self.stop_remove(removestate=False, removecontent=False)

    def stop_remove(self, removestate=False, removecontent=False):
        """ Called by any thread. Called on Session.remove_download() """
        self.done = removestate
        return self.network_stop(removestate=removestate, removecontent=removecontent)

    def network_stop(self, removestate, removecontent):
        """ Called by network thread, but safe for any """
        self.cancel_all_pending_tasks()

        out = None
        with self.lock:
            self._logger.debug("LibtorrentDownloadImpl: network_stop %s", self.torrent.get_name())

            self.get_resume_info().write_to_directory(self.download_manager.get_downloads_resume_info_directory())

            if self.handle is not None:
                self._logger.debug("LibtorrentDownloadImpl: network_stop: engineresumedata from torrent handle")
                if removestate:
                    out = self.session_manager.remove_torrent(self, removecontent)
                    self.handle = None
                else:
                    self.set_vod_mode(False)
                    self.handle.pause()
                    self.save_resume_data()
            else:
                self._logger.debug("LibtorrentDownloadImpl: network_stop: handle is None")
                self.cancel_pending_task("check_create_wrapper")
                if self.download_state == DownloadStatus.CIRCUITS:
                    self.download_state = DownloadStatus.STOPPED

            if removestate:
                self.download_manager.remove_pstate(self.torrent.get_infohash())

        return out or succeed(None)

    def get_content_dest(self):
        """ Returns the file to which the downloaded content is saved. """
        return os.path.join(self.config.get_destination_dir(), self.correctedinfoname)

    def set_filepieceranges(self):
        """ Determine which file maps to which piece ranges for progress info """
        self._logger.debug("LibtorrentDownloadImpl: set_filepieceranges: %s", self.config.get_selected_files())

        metainfo = self.torrent.get_meta_info()
        self.filepieceranges = maketorrent.get_length_filepieceranges_from_metainfo(metainfo, [])[1]

    def restart(self):
        """ Restart the download """
        self.user_stopped = False
        self._logger.debug("LibtorrentDownloadImpl: restart: %s", self.torrent.get_name())

        # We stop a previous restart if it's active
        self.cancel_pending_task("check_create_wrapper")

        with self.lock:
            if self.handle is None:
                self.error = None

                def schedule_create_engine(_):
                    self.cew_scheduled = True
                    create_engine_wrapper_deferred = self.create_engine_wrapper(share_mode=self.get_share_mode())
                    create_engine_wrapper_deferred.addCallback(self.download_manager.on_download_handle_created)

                can_create_engine_deferred = self.can_create_engine_wrapper()
                can_create_engine_deferred.addCallback(schedule_create_engine)
            else:
                self.handle.resume()
                self.set_vod_mode(self.config.get_mode() == DownloadMode.VOD)

    @check_handle_and_synchronize([])
    def get_destination_files(self, exts=None):
        """
        You can give a list of extensions to return. If None: return all destination_files
        @return list of (torrent,disk) filename tuples.
        """
        destination_files = list()
        for index, file_entry in enumerate(self.handle.get_info().files()):
            if self.handle.get_file_priority(index) > 0:
                filename = file_entry.path
                ext = os.path.splitext(filename)[1].lstrip('.')
                if exts is None or ext in exts:
                    pathname = os.path.join(self.config.get_destination_dir(), filename.decode('utf-8'))
                    destination_files.append((filename, pathname))
        return destination_files

    def checkpoint(self):
        """
        Checkpoint this download. Returns a deferred that fires when the checkpointing is completed.
        """
        if not self.handle or not self.handle.is_valid():
            # Libtorrent hasn't received or initialized this download yet
            # 1. Check if we have data for this info_hash already (don't overwrite it if we do!)
            basename = hexlify(self.torrent.get_infohash()) + '.state'
            filename = os.path.join(self.download_manager.get_downloads_resume_info_directory(), basename)
            if not os.path.isfile(filename):
                # 2. If there is no saved data for this info_hash, checkpoint it without data so we do not
                #    lose it when we crash or restart before the download becomes known.
                resume_data = {
                    'file-format': "libtorrent resume file",
                    'file-version': 1,
                    'info-hash': self.torrent.get_infohash()
                }
                alert = type('anonymous_alert', (object, ), dict(resume_data=resume_data))
                self.on_save_resume_data_alert(alert)
            return succeed(None)

        return self.save_resume_data()

    def get_resume_info(self):
        config = dict(deepcopy(self.config.config))
        state = {
            'mode': DownloadMode.NORMAL,
            'version': PERSISTENTSTATE_CURRENTVERSION,
            'share_mode': True if self.get_share_mode() else False,
            'download': {
                'status': self.network_get_state(None, False).get_status(),
                'progress': self.network_get_state(None, False).get_progress(),
                'swarmcache': None
            },
            'user_stopped': self.user_stopped,
        }
        if isinstance(self.torrent, TorrentDefNoMetainfo):
            state['meta_info'] = {'info_hash': self.torrent.get_infohash(),
                                  'name': self.torrent.get_name_as_unicode(),
                                  'url': self.torrent.get_url()}
        else:
            state['meta_info'] = self.torrent.get_meta_info()

        id = self.torrent.get_infohash()
        resume_data = self.handle.get_
        return DownloadResumeInfo(id, config, state, resume_data)

    def set_torrent(self, torrent):
        with self.lock:
            self.torrent = torrent

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

    @check_handle_and_synchronize()
    def get_share_mode(self):
        return self.handle.get_status().share_mode

    def set_share_mode(self, share_mode):
        self.get_handle().addCallback(lambda handle: handle.set_share_mode(share_mode))
