# Based on SwiftDownloadImpl.py by Arno Bakker, modified by Egbert Bouman for the use with libtorrent

import sys
import copy
import time
import libtorrent as lt

from binascii import hexlify
from traceback import print_exc

from Tribler.Core import NoDispersyRLock
from Tribler.Core.simpledefs import *
from Tribler.Core.DownloadState import DownloadState
from Tribler.Core.APIImplementation.DownloadRuntimeConfig import DownloadRuntimeConfig
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.APIImplementation import maketorrent
from Tribler.Core.osutils import fix_filebasename
from Tribler.Core.APIImplementation.maketorrent import torrentfilerec2savefilename, savefilenames2finaldest
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo, TorrentDef
from Tribler.Core.exceptions import VODNoFileSelectedInMultifileTorrentException
from Tribler.Core.Utilities.Crypto import sha
from Tribler.Core.CacheDB.Notifier import Notifier

from Tribler.Video.VideoUtility import get_videoinfo

if sys.platform == "win32":
    try:
        import win32api
        import win32con
    except:
        pass

DEBUG = False


class VODFile(object):

    def __init__(self, f, d):
        self._file = f
        self._download = d

        pieces = self._download.tdef.get_pieces()
        self.pieces = [pieces[x:x + 20]for x in xrange(0, len(pieces), 20)]
        self.piecesize = self._download.tdef.get_piece_length()

        self.startpiece = self._download.handle.get_torrent_info().map_file(self._download.get_vod_fileindex(), 0, 0)
        self.endpiece = self._download.handle.get_torrent_info().map_file(self._download.get_vod_fileindex(), self._download.get_vod_filesize(), 0)

    def read(self, *args):
        oldpos = self._file.tell()

        if DEBUG:
            print >> sys.stderr, 'VODFile: get bytes', oldpos, '-', oldpos + args[0]

        while self._download.get_byte_progress([(self._download.get_vod_fileindex(), oldpos, oldpos + args[0])]) < 1:
            time.sleep(1)
        result = self._file.read(*args)

        newpos = self._file.tell()
        if self._download.vod_seekpos == oldpos:
            self._download.vod_seekpos = newpos

        if DEBUG:
            print >> sys.stderr, 'VODFile: got bytes', oldpos, '-', newpos
        # assert self.verify_pieces(result, oldpos, newpos)

        return result

    def seek(self, *args):
        self._file.seek(*args)
        newpos = self._file.tell()

        if DEBUG:
            print >> sys.stderr, 'VODFile: seek', newpos, args

        if self._download.vod_seekpos == None or abs(newpos - self._download.vod_seekpos) < 1024 * 1024:
            self._download.vod_seekpos = newpos
        self._download.set_byte_priority([(self._download.get_vod_fileindex(), 0, newpos)], 0)
        self._download.set_byte_priority([(self._download.get_vod_fileindex(), newpos, -1)], 1)

        if DEBUG:
            print >> sys.stderr, 'VODFile: seek, get pieces', self._download.handle.piece_priorities()
            print >> sys.stderr, 'VODFile: seek, got pieces', [int(piece) for piece in self._download.handle.status().pieces]

    def verify_pieces(self, original_data, frompos, topos):
        allpiecesok = True
        _frompos = frompos
        _topos = topos

        frompiece = self._download.handle.get_torrent_info().map_file(self._download.get_vod_fileindex(), frompos, 0)
        topiece = self._download.handle.get_torrent_info().map_file(self._download.get_vod_fileindex(), topos, 0)
        print >> sys.stderr, "VODFile: Libtorrent says we read pieces", frompiece.piece, topiece.piece

        if frompiece.start:
            if frompos - frompiece.start < 0:
                print >> sys.stderr, "VODFile: Cannot verify ", frompos, "-", frompos + self.piecesize - frompiece.start

                # cannot read partial piece, skipping first X bytes
                frompos += self.piecesize - frompiece.start
                frompiece = frompiece.piece + 1
            else:
                # need to read more than this partial piece, extending with X bytes
                frompos -= frompiece.start
                frompiece = frompiece.piece

        if topiece.piece == self.endpiece.piece:
            print >> sys.stderr, "VODFile: Cannot verify ", topos - topiece.start, "-", topos

            # cannot read partial piece, truncating last X bytes
            topos -= topiece.start
            topiece = topiece.piece - 1

        else:
            if topiece.start:
                topos += self.piecesize - topiece.start
            topiece = topiece.piece

        if topiece >= frompiece:
            oldpos = self._file.tell()
            self._file.seek(frompos)
            read_data = self._file.read(topos - frompos)
            self._file.seek(oldpos)

            assert len(read_data) == topos - frompos

            # align two arrays
            data_offsets = [0, len(read_data)]
            original_data_offsets = [0, (len(original_data))]

            if frompos > _frompos:
                original_data_offsets[0] = frompos - _frompos
            elif frompos < _frompos:
                data_offsets[0] = _frompos - frompos

            if topos > _topos:
                data_offsets[1] -= topos - _topos
            elif topos < _topos:
                original_data_offsets[1] -= _topos - topos

            assert data_offsets[1] - data_offsets[0] == original_data_offsets[1] - original_data_offsets[0], (data_offsets[1] - data_offsets[0], original_data_offsets[1] - original_data_offsets[0])
            assert read_data[data_offsets[0]:data_offsets[1]] == original_data[original_data_offsets[0]:original_data_offsets[1]]

            startindex = 0
            for piece in range(frompiece, topiece + 1):
                piecehash = sha(read_data[startindex:startindex + self.piecesize]).digest()

                if piecehash == self.pieces[piece]:
                    print >> sys.stderr, "VODFile: Correct piece read", piece
                else:
                    print >> sys.stderr, "VODFile: Incorrect piece read", piece, piecehash, self.pieces[piece]
                    allpiecesok = False
                startindex += self.piecesize

        return allpiecesok

    def close(self, *args):
        self._file.close(*args)


class LibtorrentDownloadImpl(DownloadRuntimeConfig):
    """ Download subclass that represents a libtorrent download."""

    def __init__(self, session, tdef):
        self.dllock = NoDispersyRLock()
        self.session = session
        self.tdef = tdef
        self.handle = None

        self.notifier = Notifier.getInstance()

        # Just enough so error saving and get_state() works
        self.error = None
        # To be able to return the progress of a stopped torrent, how far it got.
        self.progressbeforestop = 0.0
        self.filepieceranges = []

        # Libtorrent session manager, can be None at this point as the core could have
        # not been started. Will set in create_engine wrapper
        self.ltmgr = None

        # Libtorrent status
        self.dlstates = [DLSTATUS_WAITING4HASHCHECK, DLSTATUS_HASHCHECKING, DLSTATUS_METADATA, DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_SEEDING, DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_HASHCHECKING]
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
        self.queue_position = -1

        self.prebuffsize = 5 * 1024 * 1024
        self.endbuffsize = 0
        self.vod_seekpos = 0
        self.vod_status = ""
        self.videoinfo = {'status' : None}

        self.lm_network_vod_event_callback = None
        self.pstate_for_restart = None

        self.cew_scheduled = False
        self.askmoreinfo = False

    def get_def(self):
        return self.tdef

    def setup(self, dcfg=None, pstate=None, initialdlstatus=None, lm_network_engine_wrapper_created_callback=None, lm_network_vod_event_callback=None, wrapperDelay=0):
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
                self.dlconfig = copy.copy(cdcfg.dlconfig)

                # Things that only exist at runtime
                self.dlruntimeconfig = {}
                self.dlruntimeconfig['max_desired_upload_rate'] = 0
                self.dlruntimeconfig['max_desired_download_rate'] = 0

                if not isinstance(self.tdef, TorrentDefNoMetainfo):
                    self.set_files()

                if DEBUG:
                    print >> sys.stderr, "LibtorrentDownloadImpl: setup: initialdlstatus", self.tdef.get_infohash(), initialdlstatus

                self.create_engine_wrapper(lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus=initialdlstatus, wrapperDelay=wrapperDelay)

            self.pstate_for_restart = pstate

        except Exception as e:
            with self.dllock:
                self.error = e
                print_exc()

    def create_engine_wrapper(self, lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus=None, wrapperDelay=0):
        with self.dllock:
            if not self.cew_scheduled:
                self.ltmgr = self.session.lm.ltmgr
                if not self.ltmgr or (not self.tdef.has_trackers() and not self.ltmgr.is_dht_ready()):
                    print >> sys.stderr, "LibtorrentDownloadImpl: LTMGR or DHT not ready, rescheduling create_engine_wrapper"
                    create_engine_wrapper_lambda = lambda: self.create_engine_wrapper(lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus=initialdlstatus)
                    self.session.lm.rawserver.add_task(create_engine_wrapper_lambda, 5)
                    self.dlstate = DLSTATUS_METADATA
                else:
                    network_create_engine_wrapper_lambda = lambda: self.network_create_engine_wrapper(lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus)
                    self.session.lm.rawserver.add_task(network_create_engine_wrapper_lambda, wrapperDelay)
                    self.cew_scheduled = True

    def network_create_engine_wrapper(self, lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus=None):
        # Called by any thread, assume dllock already acquired
        if DEBUG:
            print >> sys.stderr, "LibtorrentDownloadImpl: create_engine_wrapper()"

        atp = {}
        atp["save_path"] = str(self.dlconfig['saveas'])
        atp["storage_mode"] = lt.storage_mode_t.storage_mode_sparse
        atp["paused"] = True
        atp["auto_managed"] = False
        atp["duplicate_is_error"] = True

        resume_data = pstate.get('engineresumedata', None) if pstate else None
        if not isinstance(self.tdef, TorrentDefNoMetainfo):
            metainfo = self.tdef.get_metainfo()
            torrentinfo = lt.torrent_info(metainfo)

            torrent_files = torrentinfo.files()
            is_multifile = len(self.tdef.get_files_as_unicode()) > 1
            commonprefix = os.path.commonprefix([file_entry.path for file_entry in torrent_files]) if is_multifile else ''
            swarmname = os.path.split(commonprefix)[0] or os.path.split(commonprefix)[1]

            if is_multifile and swarmname != self.correctedinfoname:
                for i, file_entry in enumerate(torrent_files):
                    filename = file_entry.path[len(swarmname) + 1:]
                    torrentinfo.rename_file(i, str(os.path.join(self.correctedinfoname, filename)))

            self.orig_files = [torrent_file.path for torrent_file in torrentinfo.files()]

            atp["ti"] = torrentinfo
            if resume_data:
                atp["resume_data"] = lt.bencode(resume_data)
            print >> sys.stderr, self.tdef.get_name_as_unicode(), \
                                 dict((k, v) for k, v in resume_data.iteritems() if k not in ['pieces', 'piece_priority', 'peers']) if resume_data else None
        else:
            if self.tdef.get_url():
                # We prefer to use an url, since it may contain trackers
                atp["url"] = self.tdef.get_url()
            else:
                atp["info_hash"] = lt.big_number(self.tdef.get_infohash())
            atp["name"] = str(self.tdef.get_name())

        self.handle = self.ltmgr.add_torrent(self, atp)
        self.lm_network_vod_event_callback = lm_network_vod_event_callback

        if self.handle:
            self.set_selected_files()
            if self.get_mode() == DLMODE_VOD:
                self.set_vod_mode(True)

            # If we lost resume_data always resume download in order to force checking
            if initialdlstatus != DLSTATUS_STOPPED or not resume_data:
                self.handle.resume()

                # If we only needed to perform checking, pause download after it is complete
                self.pause_after_next_hashcheck = initialdlstatus == DLSTATUS_STOPPED

            self.handle.resolve_countries(True)

        else:
            print >> sys.stderr, "Could not add torrent to LibtorrentManager", self.tdef.get_name_as_unicode()

        with self.dllock:
            self.cew_scheduled = False

        if lm_network_engine_wrapper_created_callback is not None:
            lm_network_engine_wrapper_created_callback(self, pstate)

    def set_vod_mode(self, enable=True):
        if DEBUG:
            print >> sys.stderr, "LibtorrentDownloadImpl: set_vod_mode for", self.handle.name(), '( enable =', enable, ')'

        if enable:
            self.vod_status = ""
            self.vod_seekpos = 0

            # Define which file to DL in VOD mode
            self.videoinfo = {'live': self.get_def().get_live()}

            if self.tdef.is_multifile_torrent():
                if len(self.dlconfig['selected_files']) == 0:
                    raise VODNoFileSelectedInMultifileTorrentException()
                filename = self.dlconfig['selected_files'][0]
                self.videoinfo['index'] = self.get_def().get_index_of_file_in_files(filename)
                self.videoinfo['inpath'] = filename
                self.videoinfo['bitrate'] = self.get_def().get_bitrate(filename)

            else:
                filename = self.get_def().get_name()
                self.videoinfo['index'] = 0
                self.videoinfo['inpath'] = filename
                self.videoinfo['bitrate'] = self.get_def().get_bitrate()

            self.videoinfo['outpath'] = self.files[self.videoinfo['index']]
            self.videoinfo['mimetype'] = self.get_mimetype(filename)
            self.videoinfo['usercallback'] = lambda event, params: self.session.uch.perform_vod_usercallback(self, self.dlconfig['vod_usercallback'], event, params)
            self.videoinfo['userevents'] = self.dlconfig['vod_userevents'][:]
            # TODO: Niels 06-05-2013 we need a status object reporting buffering etc. should be linked to test_vod
            self.videoinfo['status'] = None

            self.prebuffsize = max(int(self.videoinfo['outpath'][1] * 0.05), 5 * 1024 * 1024)
            self.endbuffsize = 1 * 1024 * 1024

            self.handle.set_sequential_download(True)
            self.handle.set_priority(255)
            self.set_byte_priority([(self.get_vod_fileindex(), self.prebuffsize, -self.endbuffsize)], 0)
            self.set_byte_priority([(self.get_vod_fileindex(), 0, self.prebuffsize)], 1)
            self.set_byte_priority([(self.get_vod_fileindex(), -self.endbuffsize, -1)], 1)

            self.progress = self.get_byte_progress([(self.get_vod_fileindex(), 0, -1)])
            if self.progress == 1.0:
                if DEBUG:
                    print >> sys.stderr, "LibtorrentDownloadImpl: VOD requested, but file complete on disk", self.videoinfo
                self.start_vod(complete=True)
            else:
                if DEBUG:
                    print >> sys.stderr, "LibtorrentDownloadImpl: going into VOD mode", self.videoinfo
                self.set_state_callback(self.monitor_vod, delay=1.0)
        else:
            self.handle.set_sequential_download(False)
            self.handle.set_priority(0)
            if self.get_vod_fileindex() >= 0:
                self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)

    def monitor_vod(self, ds):
        if not self.handle or self.handle.is_paused() or self.get_mode() != DLMODE_VOD:
            return (0, False)

        if self.endbuffsize and self.get_byte_progress([(self.get_vod_fileindex(), -self.endbuffsize - 1, -1)]) >= 1:
            self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)
            self.endbuffsize = 0

        bufferprogress = ds.get_vod_prebuffering_progress_consec()

        if DEBUG:
            print >> sys.stderr, 'LibtorrentDownloadImpl: bufferprogress = %.2f' % bufferprogress

        if bufferprogress >= 1:
            if not self.vod_status:
                self.start_vod(complete=False)
            else:
                self.resume_vod()

        elif bufferprogress <= 0.1 and self.vod_status:
            self.pause_vod()

        if bufferprogress >= 1 and not self.videoinfo.get('bitrate', None):
            # Attempt to estimate the bitrate of the videofile with ffmpeg
            videofile = self.videoinfo["outpath"][0]
            videoanalyser = self.session.get_video_analyser_path()
            duration, bitrate, _ = get_videoinfo(videofile, videoanalyser)
            self.videoinfo['bitrate'] = bitrate
            self.videoinfo['duration'] = duration

        return (1.0, False)

    def get_vod_duration(self):
        return self.videoinfo.get('duration', None)

    def get_vod_fileindex(self):
        if self.videoinfo and self.videoinfo.has_key('index'):
            return self.videoinfo['index']
        return -1

    def get_vod_filesize(self):
        fileindex = self.get_vod_fileindex()
        if fileindex >= 0:
            file_entry = self.handle.get_torrent_info().file_at(fileindex)
            return file_entry.size
        return 0

    def get_piece_progress(self, pieces, consecutive=False):
        if not pieces:
            return 1.0
        elif consecutive:
            pieces.sort()

        with self.dllock:
            if self.handle:
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

    def get_byte_progress(self, byteranges, consecutive=False):
        with self.dllock:
            if self.handle:
                pieces = []
                for fileindex, bytes_begin, bytes_end in byteranges:
                    if fileindex >= 0:
                        # Ensure the we remain within the file's boundaries
                        file_entry = self.handle.get_torrent_info().file_at(fileindex)
                        bytes_begin = min(file_entry.size, bytes_begin) if bytes_begin >= 0 else file_entry.size + (bytes_begin + 1)
                        bytes_end = min(file_entry.size, bytes_end) if bytes_end >= 0 else file_entry.size + (bytes_end + 1)

                        startpiece = self.handle.get_torrent_info().map_file(fileindex, bytes_begin, 0).piece
                        endpiece = self.handle.get_torrent_info().map_file(fileindex, bytes_end, 0).piece + 1
                        startpiece = max(startpiece, 0)
                        endpiece = min(endpiece, self.handle.get_torrent_info().num_pieces())

                        pieces += range(startpiece, endpiece)
                    else:
                        print >> sys.stderr, "LibtorrentDownloadImpl: could not get progress for incorrect fileindex"

                pieces = list(set(pieces))
                return self.get_piece_progress(pieces, consecutive)

    def set_piece_priority(self, pieces, priority):
        with self.dllock:
            if self.handle:
                piecepriorities = self.handle.piece_priorities()
                for piece in pieces:
                    if piece < len(piecepriorities):
                        piecepriorities[piece] = priority
                    else:
                        print >> sys.stderr, "LibtorrentDownloadImpl: could not set priority for non-existing piece %d / %d" % (piece, len(piecepriorities))
                self.handle.prioritize_pieces(piecepriorities)

    def set_byte_priority(self, byteranges, priority):
        with self.dllock:
            if self.handle:
                pieces = []
                for fileindex, bytes_begin, bytes_end in byteranges:
                    if fileindex >= 0:
                        if bytes_begin == 0 and bytes_end == -1:
                            # Set priority for entire file
                            filepriorities = self.handle.file_priorities()
                            filepriorities[fileindex] = priority
                            self.handle.prioritize_files(filepriorities)
                        else:
                            # Ensure the we remain within the file's boundaries
                            file_entry = self.handle.get_torrent_info().file_at(fileindex)
                            bytes_begin = min(file_entry.size, bytes_begin) if bytes_begin >= 0 else file_entry.size + (bytes_begin + 1)
                            bytes_end = min(file_entry.size, bytes_end) if bytes_end >= 0 else file_entry.size + (bytes_end + 1)

                            startpiece = self.handle.get_torrent_info().map_file(fileindex, bytes_begin, 0).piece
                            endpiece = self.handle.get_torrent_info().map_file(fileindex, bytes_end, 0).piece + 1
                            startpiece = max(startpiece, 0)
                            endpiece = min(endpiece, self.handle.get_torrent_info().num_pieces())

                            pieces += range(startpiece, endpiece)
                    else:
                        print >> sys.stderr, "LibtorrentDownloadImpl: could not set priority for incorrect fileindex"

                if pieces:
                    pieces = list(set(pieces))
                    self.set_piece_priority(pieces, priority)

    def start_vod(self, complete=False):
        if not self.vod_status:
            self.vod_status = "started"
            self.lm_network_vod_event_callback(self.videoinfo, VODEVENT_START,
                                              {"complete": complete,
                                               "filename": self.videoinfo["outpath"][0] if complete else None,
                                               "mimetype": self.videoinfo["mimetype"],
                                               "stream": None if complete else VODFile(open(self.videoinfo['outpath'][0], 'rb'), self),
                                               "length": self.videoinfo['outpath'][1],
                                               "bitrate": self.videoinfo["bitrate"]})

            if DEBUG:
                print >> sys.stderr, "LibtorrentDownloadImpl: VOD started", self.videoinfo['outpath'][0]

    def resume_vod(self):
        if self.vod_status == "paused":
            self.vod_status = "resumed"
            self.videoinfo["usercallback"](VODEVENT_RESUME, {})

            if DEBUG:
                print >> sys.stderr, "LibtorrentDownloadImpl: VOD resumed"

    def pause_vod(self):
        if self.vod_status != "paused":
            self.vod_status = "paused"
            self.videoinfo["usercallback"](VODEVENT_PAUSE, {})

            if DEBUG:
                print >> sys.stderr, "LibtorrentDownloadImpl: VOD paused"

    def get_vod_info(self):
        return self.videoinfo

    def process_alert(self, alert, alert_type):
        if DEBUG or alert.category() in [lt.alert.category_t.error_notification, lt.alert.category_t.performance_warning]:
            print >> sys.stderr, "LibtorrentDownloadImpl: alert %s with message %s" % (alert_type, alert)

        if self.handle and self.handle.is_valid():

            with self.dllock:

                if alert.category() == lt.alert.category_t.debug_notification:
                    if alert_type == 'peer_connect_alert':
                        self.on_peer_connect_alert(alert)
                elif alert_type == 'metadata_received_alert':
                    self.on_metadata_received_alert(alert)
                elif alert_type == 'file_renamed_alert':
                    self.on_file_renamed_alert(alert)
                elif alert_type == 'performance_alert':
                    self.on_performance_alert(alert)
                elif alert_type == 'torrent_checked_alert':
                    self.on_torrent_checked_alert(alert)
                elif alert_type == "torrent_finished_alert":
                    self.on_torrent_finished_alert(alert)
                else:
                    self.update_lt_stats()

    def on_peer_connect_alert(self, alert):
        self.notifier.notify(NTFY_ACTIVITIES, NTFY_INSERT, NTFY_ACT_MEET, "%s:%d" % (alert.ip[0], alert.ip[1]))

    def on_metadata_received_alert(self, alert):
        self.metadata = {'info': lt.bdecode(self.handle.get_torrent_info().metadata())}

        trackers = [tracker['url'] for tracker in self.handle.trackers()]
        if trackers:
            if len(trackers) > 1:
                self.metadata["announce-list"] = [trackers]
            else:
                self.metadata["announce"] = trackers[0]

        self.tdef = TorrentDef.load_from_dict(self.metadata)
        self.orig_files = [torrent_file.path for torrent_file in lt.torrent_info(self.metadata).files()]
        self.set_files()

        if self.session.lm.rtorrent_handler:
            self.session.lm.rtorrent_handler.save_torrent(self.tdef)
        elif self.session.lm.torrent_db:
            self.session.lm.torrent_db.addExternalTorrent(self.tdef, source='', extra_info={'status': 'good'}, commit=True)

        self.checkpoint()

    def on_file_renamed_alert(self, alert):
        if os.path.exists(self.unwanteddir_abs) and not os.listdir(self.unwanteddir_abs) and all(self.handle.file_priorities()):
            os.rmdir(self.unwanteddir_abs)

    def on_performance_alert(self, alert):
        # When the send buffer watermark is too low, double the buffer size to a maximum of 50MiB. This is the same mechanism as Deluge uses.
        if alert.message().endswith("send buffer watermark too low (upload rate will suffer)"):
            settings = self.ltmgr.ltsession.settings()
            if settings.send_buffer_watermark <= 26214400:
                print >> sys.stderr, "LibtorrentDownloadImpl: setting send_buffer_watermark to", 2 * settings.send_buffer_watermark
                settings.send_buffer_watermark = 2 * settings.send_buffer_watermark
                self.ltmgr.ltsession.set_settings(settings)
        # When the write cache is too small, double the buffer size to a maximum of 64MiB. Again, this is the same mechanism as Deluge uses.
        elif alert.message().endswith("max outstanding disk writes reached"):
            settings = self.ltmgr.ltsession.settings()
            if settings.max_queued_disk_bytes <= 33554432:
                print >> sys.stderr, "LibtorrentDownloadImpl: setting max_queued_disk_bytes to", 2 * settings.max_queued_disk_bytes
                settings.max_queued_disk_bytes = 2 * settings.max_queued_disk_bytes
                self.ltmgr.ltsession.set_settings(settings)

    def on_torrent_checked_alert(self, alert):
        if self.pause_after_next_hashcheck:
            self.pause_after_next_hashcheck = False
            self.handle.pause()
        if self.checkpoint_after_next_hashcheck:
            self.checkpoint_after_next_hashcheck = False
            self.checkpoint()

    def on_torrent_finished_alert(self, alert):
        self.update_lt_stats()
        if self.get_mode() == DLMODE_VOD:
            if self.progress == 1.0:
                self.set_vod_mode(False)
            elif self.progress < 1.0:
                # If we are in VOD mode and still need to download pieces and but libtorrent says we are finished, reset the piece priorities to 1.
                def reset_priorities():
                    if self.handle.status().progress == 1.0:
                        self.set_byte_priority([(self.get_vod_fileindex(), 0, -1)], 1)
                self.session.lm.rawserver.add_task(reset_priorities, 5)

    def update_lt_stats(self):
        status = self.handle.status()
        self.dlstate = self.dlstates[status.state] if not status.paused else DLSTATUS_STOPPED
        self.dlstate = DLSTATUS_STOPPED_ON_ERROR if self.dlstate == DLSTATUS_STOPPED and status.error else self.dlstate
        if self.get_mode() == DLMODE_VOD:
            self.progress = self.get_byte_progress([(self.get_vod_fileindex(), 0, -1)])
            self.dlstate = (DLSTATUS_SEEDING if self.progress == 1.0 else self.dlstate) if not status.paused else DLSTATUS_STOPPED
        else:
            self.progress = status.progress
        self.error = unicode(status.error) if status.error else None
        self.length = float(status.total_wanted)
        self.curspeeds[DOWNLOAD] = float(status.download_payload_rate) if self.dlstate not in [DLSTATUS_STOPPED, DLSTATUS_STOPPED] else 0.0
        self.curspeeds[UPLOAD] = float(status.upload_payload_rate) if self.dlstate not in [DLSTATUS_STOPPED, DLSTATUS_STOPPED] else 0.0
        self.all_time_upload = status.all_time_upload
        self.all_time_download = status.all_time_download
        self.finished_time = status.finished_time

    def set_files(self):
        # H4xor this so the 'name' field is safe
        self.correctedinfoname = fix_filebasename(self.tdef.get_name_as_unicode())

        metainfo = self.tdef.get_metainfo()
        self.set_filepieceranges(metainfo)

        # Allow correctinfoname to be overwritten for multifile torrents only
        if 'files' in metainfo['info'] and self.dlconfig['correctedfilename'] and self.dlconfig['correctedfilename'] != '':
            self.correctedinfoname = self.dlconfig['correctedfilename']

        self.files = []
        if 'files' in metainfo['info']:
            for x in metainfo['info']['files']:
                savepath = torrentfilerec2savefilename(x)
                full = savefilenames2finaldest(self.get_content_dest(), savepath)
                # Arno: TODO: this sometimes gives too long filenames for
                # Windows. When fixing this take into account that
                # Download.get_dest_files() should still produce the same
                # filenames as your modifications here.
                self.files.append((full, x['length']))
        else:
            self.files.append((self.get_content_dest(), metainfo['info']['length']))

    def set_selected_files(self, selected_files=None):
        with self.dllock:

            if self.handle is not None and not isinstance(self.tdef, TorrentDefNoMetainfo):

                if selected_files is None:
                    selected_files = self.dlconfig['selected_files']
                else:
                    self.dlconfig['selected_files'] = selected_files

                is_multifile = len(self.tdef.get_files_as_unicode()) > 1
                commonprefix = os.path.commonprefix([path for path in self.orig_files]) if is_multifile else ''
                swarmname = os.path.split(commonprefix)[0] or os.path.split(commonprefix)[1]
                unwanteddir = os.path.join(swarmname, '.unwanted')
                unwanteddir_abs = os.path.join(self.handle.save_path(), unwanteddir)

                filepriorities = []
                for index, orig_path in enumerate(self.orig_files):
                    filename = orig_path[len(swarmname) + 1:]

                    if filename in selected_files or not selected_files:
                        filepriorities.append(1)
                        new_path = orig_path
                    else:
                        filepriorities.append(0)
                        new_path = os.path.join(unwanteddir, '%s%d' % (hexlify(self.tdef.get_infohash()), index))

                    cur_path = self.handle.get_torrent_info().files()[index].path
                    if cur_path != new_path:
                        if not os.path.exists(unwanteddir_abs) and unwanteddir in new_path:
                            os.makedirs(unwanteddir_abs)
                            if sys.platform == "win32":
                                win32api.SetFileAttributes(unwanteddir_abs, win32con.FILE_ATTRIBUTE_HIDDEN)

                        self.handle.rename_file(index, new_path)

                self.handle.prioritize_files(filepriorities)

                self.unwanteddir_abs = unwanteddir_abs

    def move_storage(self, new_dir):
        with self.dllock:
            if self.handle is not None and not isinstance(self.tdef, TorrentDefNoMetainfo):
                self.handle.move_storage(new_dir)
                self.dlconfig['saveas'] = new_dir
                return True
        return False

    def get_save_path(self):
        with self.dllock:
            if self.handle is not None and not isinstance(self.tdef, TorrentDefNoMetainfo):
                return self.handle.save_path()

    def force_recheck(self):
        with self.dllock:
            if self.handle is not None and not isinstance(self.tdef, TorrentDefNoMetainfo):
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
        """ Return last reported speed in KB/s
        @return float
        """
        with self.dllock:
            return self.curspeeds[dir] / 1024.0

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
        stats['vod_playable'] = self.progress == 1.0 or (stats['vod_prebuf_frac'] == 1.0 and self.curspeeds[DOWNLOAD] > 0.0)
        stats['vod_playable_after'] = self.network_calc_prebuf_eta()
        stats['vod_stats'] = self.network_get_vod_stats()
        stats['spew'] = self.network_create_spew_from_peerlist() if getpeerlist or self.askmoreinfo else None

        seeding_stats = {}
        seeding_stats['total_up'] = self.all_time_upload
        seeding_stats['total_down'] = self.all_time_download
        seeding_stats['time_seeding'] = self.finished_time

        logmsgs = []

        if DEBUG:
            print >> sys.stderr, "Torrent", self.handle.name(), "PROGRESS", self.progress, "QUEUEPOS", self.queue_position, "DLSTATE", self.dlstate, "SEEDTIME", self.finished_time

        return (self.dlstate, stats, seeding_stats, logmsgs)

    def network_create_statistics_reponse(self):
        if self.handle:
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
        if self.get_mode() == DLMODE_VOD and self.get_vod_fileindex() >= 0 and self.vod_seekpos != None:
            if self.endbuffsize:
                return self.get_byte_progress([(self.get_vod_fileindex(), self.vod_seekpos, self.vod_seekpos + self.prebuffsize), \
                                               (self.get_vod_fileindex(), -self.endbuffsize - 1, -1)])
            else:
                return self.get_byte_progress([(self.get_vod_fileindex(), self.vod_seekpos, self.vod_seekpos + self.prebuffsize)])
        else:
            return 0.0

    def network_calc_prebuf_frac_consec(self):
        if self.get_mode() == DLMODE_VOD and self.get_vod_fileindex() >= 0 and self.vod_seekpos != None:
            if self.endbuffsize:
                return self.get_byte_progress([(self.get_vod_fileindex(), self.vod_seekpos, self.vod_seekpos + self.prebuffsize), \
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
        d['status'] = self.vod_status
        return d

    def network_create_spew_from_peerlist(self):
        plist = []
        with self.dllock:
            peer_infos = self.handle.get_peer_info()
        for peer_info in peer_infos:
            peer_dict = {}
            peer_dict['id'] = peer_info.pid
            peer_dict['extended_version'] = peer_info.client
            peer_dict['ip'] = peer_info.ip[0]
            peer_dict['port'] = peer_info.ip[1]
            peer_dict['optimistic'] = bool(peer_info.flags & 2048)  # optimistic_unchoke = 0x800 seems unavailable in python bindings
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
            plist.append(peer_dict)

        return plist

    def set_state_callback(self, usercallback, getpeerlist=False, delay=0.0):
        """ Called by any thread """
        with self.dllock:
            network_get_state_lambda = lambda: self.network_get_state(usercallback, getpeerlist)
            self.session.lm.rawserver.add_task(network_get_state_lambda, delay)

    def network_get_state(self, usercallback, getpeerlist, sessioncalling=False):
        """ Called by network thread """
        with self.dllock:
            if self.handle is None:
                if DEBUG:
                    print >> sys.stderr, "LibtorrentDownloadImpl: network_get_state: Download not running"
                ds = DownloadState(self, DLSTATUS_WAITING4HASHCHECK, self.error, self.progressbeforestop)
            else:
                (status, stats, seeding_stats, logmsgs) = self.network_get_stats(getpeerlist)
                ds = DownloadState(self, status, self.error, self.get_progress(), stats=stats, seeding_stats=seeding_stats, filepieceranges=self.filepieceranges, logmsgs=logmsgs)
                self.progressbeforestop = ds.get_progress()

            if sessioncalling:
                return ds

            # Invoke the usercallback function via a new thread.
            # After the callback is invoked, the return values will be passed to the returncallback for post-callback processing.
            if not self.done:
                self.session.uch.perform_getstate_usercallback(usercallback, ds, self.sesscb_get_state_returncallback)

    def sesscb_get_state_returncallback(self, usercallback, when, newgetpeerlist):
        """ Called by SessionCallbackThread """
        with self.dllock:
            if when > 0.0:
                # Schedule next invocation, either on general or DL specific
                network_get_state_lambda = lambda: self.network_get_state(usercallback, newgetpeerlist)
                self.session.lm.rawserver.add_task(network_get_state_lambda, when)

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
            if DEBUG:
                print >> sys.stderr, "LibtorrentDownloadImpl: network_stop", self.tdef.get_name()

            pstate = self.network_get_persistent_state()
            if self.handle is not None:
                if DEBUG:
                    print >> sys.stderr, "LibtorrentDownloadImpl: network_stop: engineresumedata from torrent handle"
                if removestate:
                    self.ltmgr.remove_torrent(self, removecontent)
                    self.handle = None
                else:
                    self.set_vod_mode(False)
                    self.handle.pause()
                    pstate['engineresumedata'] = self.handle.write_resume_data() if isinstance(self.tdef, TorrentDef) else None
                self.pstate_for_restart = pstate
            else:
                # This method is also called at Session shutdown, where one may
                # choose to checkpoint its Download. If the Download was
                # stopped before, pstate_for_restart contains its resumedata.
                # and that should be written into the checkpoint.
                #
                if self.pstate_for_restart is not None:
                    if DEBUG:
                        print >> sys.stderr, "LibtorrentDownloadImpl: network_stop: Reusing previously saved engineresume data for checkpoint"
                    # Don't copy full pstate_for_restart, as the torrent
                    # may have gone from e.g. HASHCHECK at startup to STOPPED
                    # now, at shutdown. In other words, it was never active
                    # in this session and the pstate_for_restart still says
                    # HASHCHECK.
                    pstate['engineresumedata'] = self.pstate_for_restart['engineresumedata']
                elif DEBUG:
                    print >> sys.stderr, "LibtorrentDownloadImpl: network_stop: Could not reuse engineresumedata as pstart_for_restart is None"

            # Offload the removal of the dlcheckpoint to another thread
            if removestate:
                self.session.uch.perform_removestate_callback(self.tdef.get_infohash(), None, False)

            return (self.tdef.get_infohash(), pstate)

    def get_content_dest(self):
        """ Returns the file to which the downloaded content is saved. """
        return os.path.join(self.get_dest_dir(), self.correctedinfoname)

    def set_filepieceranges(self, metainfo):
        """ Determine which file maps to which piece ranges for progress info """
        if DEBUG:
            print >> sys.stderr, "LibtorrentDownloadImpl: set_filepieceranges:", self.dlconfig['selected_files']

        self.filepieceranges = maketorrent.get_length_filepieceranges_from_metainfo(metainfo, [])[1]

        # dlconfig['priority'] will propagate the selected files to Storage
        # self.dlconfig["priority"] = maketorrent.get_length_priority_from_metainfo(metainfo, self.dlconfig['selected_files'])[1]

    def restart(self, initialdlstatus=None):
        """ Restart the Download """
        # Called by any thread
        if DEBUG:
            print >> sys.stderr, "LibtorrentDownloadImpl: restart:", self.tdef.get_name()

        with self.dllock:
            if self.handle is None:
                self.error = None
                self.create_engine_wrapper(self.session.lm.network_engine_wrapper_created_callback, self.pstate_for_restart, self.session.lm.network_vod_event_callback, initialdlstatus=initialdlstatus)
            else:
                self.handle.resume()
                self.set_vod_mode(self.get_mode() == DLMODE_VOD)

    def set_max_desired_speed(self, direct, speed):
        if DEBUG:
            print >> sys.stderr, "LibtorrentDownloadImpl: set_max_desired_speed", direct, speed

        with self.dllock:
            if direct == UPLOAD:
                self.dlruntimeconfig['max_desired_upload_rate'] = speed
            else:
                self.dlruntimeconfig['max_desired_download_rate'] = speed

    def get_max_desired_speed(self, direct):
        with self.dllock:
            if direct == UPLOAD:
                return self.dlruntimeconfig['max_desired_upload_rate']
            else:
                return self.dlruntimeconfig['max_desired_download_rate']

    def get_dest_files(self, exts=None):
        """
        You can give a list of extensions to return. If None: return all dest_files
        @return list of (torrent,disk) filename tuples.
        """

        def get_ext(filename):
            _, ext = os.path.splitext(filename)
            if ext != '' and ext[0] == '.':
                ext = ext[1:]
            return ext

        with self.dllock:
            f2dlist = []
            metainfo = self.tdef.get_metainfo()
            if metainfo:
                if 'files' not in metainfo['info']:
                    # single-file torrent
                    diskfn = self.get_content_dest()
                    _, filename = os.path.split(diskfn)
                    f2dtuple = (filename, diskfn)
                    ext = get_ext(diskfn)
                    if exts is None or ext in exts:
                        f2dlist.append(f2dtuple)
                else:
                    # multi-file torrent
                    if len(self.dlconfig['selected_files']) > 0:
                        fnlist = self.dlconfig['selected_files']
                    else:
                        fnlist = self.tdef.get_files(exts=exts)

                    for filename in fnlist:
                        filerec = maketorrent.get_torrentfilerec_from_metainfo(filename, metainfo)
                        savepath = maketorrent.torrentfilerec2savefilename(filerec)
                        diskfn = maketorrent.savefilenames2finaldest(self.get_content_dest(), savepath)
                        ext = get_ext(diskfn)
                        if exts is None or ext in exts:
                            f2dtuple = (filename, diskfn)
                            f2dlist.append(f2dtuple)
            return f2dlist

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
            if self.handle == None:
                if self.pstate_for_restart is not None:
                    resdata = self.pstate_for_restart['engineresumedata']
            elif isinstance(self.tdef, TorrentDef):
                resdata = self.handle.write_resume_data()
            pstate['engineresumedata'] = resdata
            return (self.tdef.get_infohash(), pstate)

    def network_get_persistent_state(self):
        # Assume sessionlock is held
        pstate = {}
        pstate['version'] = PERSISTENTSTATE_CURRENTVERSION
        if isinstance(self.tdef, TorrentDefNoMetainfo):
            pstate['metainfo'] = {'infohash': self.tdef.get_infohash(), 'name': self.tdef.get_name_as_unicode()}
        else:
            pstate['metainfo'] = self.tdef.get_metainfo()

        dlconfig = copy.copy(self.dlconfig)
        # Reset unpicklable params
        dlconfig['vod_usercallback'] = None
        dlconfig['mode'] = DLMODE_NORMAL
        pstate['dlconfig'] = dlconfig

        pstate['dlstate'] = {}
        ds = self.network_get_state(None, False, sessioncalling=True)
        pstate['dlstate']['status'] = ds.get_status()
        pstate['dlstate']['progress'] = ds.get_progress()
        pstate['dlstate']['swarmcache'] = None

        if DEBUG:
            print >> sys.stderr, "LibtorrentDownloadImpl: network_get_persistent_state: status", dlstatus_strings[ds.get_status()], "progress", ds.get_progress()

        pstate['engineresumedata'] = None
        return pstate

    def get_coopdl_role_object(self, role):
        """ Called by network thread """
        return None

    def recontact_tracker(self):
        """ Called by any thread """
        pass

    def set_def(self, tdef):
        with self.dllock:
            self.tdef = tdef

    def add_trackers(self, trackers):
        with self.dllock:
            if self.handle:
                for tracker in trackers:
                    self.handle.add_tracker({'url': tracker, 'verified': False})

    #
    # External addresses
    #
    def add_peer(self, addr):
        """ Add a peer address from 3rd source (not tracker, not DHT) to this
        Download.
        @param (hostname_ip,port) tuple
        """
        if self.handle is not None:
            self.handle.connect_peer(addr, 0)

    # ARNOCOMMENT: better if we removed this from Core, user knows which
    # file he selected to play, let him figure out MIME type
    def get_mimetype(self, file):
        (prefix, ext) = os.path.splitext(file)
        ext = ext.lower()
        mimetype = None
        if sys.platform == 'win32':
            # TODO: Use Python's mailcap facility on Linux to find player
            try:
                from Tribler.Video.utils import win32_retrieve_video_play_command

                [mimetype, playcmd] = win32_retrieve_video_play_command(ext, file)
                if DEBUG:
                    print >> sys.stderr, "LibtorrentDownloadImpl: Win32 reg said MIME type is", mimetype
            except:
                if DEBUG:
                    print_exc()
                pass
        else:
            try:
                import mimetypes
                # homedir = os.path.expandvars('${HOME}')
                from Tribler.Core.osutils import get_home_dir
                homedir = get_home_dir()
                homemapfile = os.path.join(homedir, '.mimetypes')
                mapfiles = [homemapfile] + mimetypes.knownfiles
                mimetypes.init(mapfiles)
                (mimetype, encoding) = mimetypes.guess_type(file)

                if DEBUG:
                    print >> sys.stderr, "LibtorrentDownloadImpl: /etc/mimetypes+ said MIME type is", mimetype, file
            except:
                print_exc()

        # if auto detect fails
        if mimetype is None:
            if ext == '.avi':
                # Arno, 2010-01-08: Hmmm... video/avi is not official registered at IANA
                mimetype = 'video/avi'
            elif ext == '.mpegts' or ext == '.ts':
                mimetype = 'video/mp2t'
            elif ext == '.mkv':
                mimetype = 'video/x-matroska'
            elif ext in ('.ogg', '.ogv'):
                mimetype = 'video/ogg'
            elif ext in ('.oga'):
                mimetype = 'audio/ogg'
            elif ext == '.webm':
                mimetype = 'video/webm'
            else:
                mimetype = 'video/mpeg'
        return mimetype


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
