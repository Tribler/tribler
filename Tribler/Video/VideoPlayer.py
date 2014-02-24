# Written by Arno Bakker
# Heavily modified by Egbert Bouman
# see LICENSE.txt for license information
import os
import sys
import logging

from binascii import hexlify
from traceback import print_exc
from collections import defaultdict
from multiprocessing.synchronize import RLock

from Tribler.Main.vwxGUI import forceWxThread
from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_VIDEO_BUFFER, NTFY_VIDEO_STARTED, DLMODE_NORMAL
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import VODFile

from Tribler.Video.utils import win32_retrieve_video_play_command, quote_program_path, escape_path, return_feasible_playback_modes
from Tribler.Video.defs import PLAYBACKMODE_INTERNAL, PLAYBACKMODE_EXTERNAL_MIME
from Tribler.Video.VideoUtility import get_videoinfo
from Tribler.Video.VideoServer import VideoServer
from Tribler.Video.VLCWrapper import VLCWrapper


logger = logging.getLogger(__name__)


class VideoPlayer:

    __single = None

    def __init__(self, utility, preferredplaybackmode=None, httpport=6880):
        if VideoPlayer.__single:
            raise RuntimeError("VideoPlayer is singleton")
        VideoPlayer.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        self.utility = utility
        self.session = utility.session
        self.videoframe = None
        self.vod_download = None
        self.vod_fileindex = None
        self.vod_playing = False
        self.vod_info = defaultdict(dict)

        feasible = return_feasible_playback_modes(self.utility.getPath())
        self.playbackmode = preferredplaybackmode if preferredplaybackmode in feasible else feasible[0]
        self.vlcwrap = VLCWrapper(self.utility.getPath()) if self.playbackmode == PLAYBACKMODE_INTERNAL else None

        # Start HTTP server for serving video
        self.videoserver = VideoServer.getInstance(httpport, self.utility.session)
        self.videoserver.start()

        self.notifier = Notifier.getInstance()

    def getInstance(*args, **kw):
        if VideoPlayer.__single is None:
            VideoPlayer(*args, **kw)
        return VideoPlayer.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        if VideoPlayer.__single and VideoPlayer.__single.videoserver:
            VideoPlayer.__single.videoserver.delInstance()
            VideoPlayer.__single = None
    delInstance = staticmethod(delInstance)

    def hasInstance():
        return VideoPlayer.__single and VideoPlayer.__single.vlcwrap and VideoPlayer.__single.vlcwrap.initialized
    hasInstance = staticmethod(hasInstance)

    def shutdown(self):
        if self.videoserver:
            self.videoserver.stop()

    def get_vlcwrap(self):
        return self.vlcwrap

    def set_videoframe(self, videoframe):
        self.videoframe = videoframe

    def play(self, download, fileindex):
        url = 'http://127.0.0.1:' + str(self.videoserver.port) + '/' + hexlify(download.get_def().get_id()) + '/' + str(fileindex)
        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            self.launch_video_player(url, download)
        else:
            self.launch_video_player(self.get_video_player(None, url))

    def monitor_vod(self, ds):
        dl = ds.get_download() if ds else None

        if dl != self.vod_download:
            return (0, False)

        bufferprogress = ds.get_vod_prebuffering_progress_consec()

        if bufferprogress >= 1 and not self.vod_playing:
            self.notifier.notify(NTFY_TORRENTS, NTFY_VIDEO_BUFFER, self.vod_download, self.vod_fileindex, True)
            self.vod_playing = True

        elif bufferprogress <= 0.1 and self.vod_playing:
            self.notifier.notify(NTFY_TORRENTS, NTFY_VIDEO_BUFFER, self.vod_download, self.vod_fileindex, False)
            self.vod_playing = False

        dl_def = dl.get_def()
        dl_hash = dl_def.get_id()

        if bufferprogress >= 1:
            if not self.vod_info[dl_hash].has_key('bitrate'):
                self.notifier.notify(NTFY_TORRENTS, NTFY_VIDEO_STARTED, (dl_hash, self.vod_fileindex))

                # Attempt to estimate the bitrate and duration of the videofile with ffmpeg.
                videofile = self.get_vod_filename(dl)
                videoanalyser = self.session.get_video_analyser_path()
                duration, bitrate, _ = get_videoinfo(videofile, videoanalyser)
                self.vod_info[dl_hash]['bitrate'] = bitrate
                self.vod_info[dl_hash]['duration'] = duration

        return (1, False)

    def get_vod_stream(self, dl_hash):
        if not self.vod_info[dl_hash].has_key('stream') and self.session.get_download(dl_hash):
            download = self.session.get_download(dl_hash)
            self.vod_info[dl_hash]['stream'] = (VODFile(open(self.get_vod_filename(download), 'rb'), download), RLock())

        if self.vod_info[dl_hash].has_key('stream'):
            return self.vod_info[dl_hash]['stream']
        return (None, None)

    def get_vod_duration(self, dl_hash):
        return self.vod_info.get(dl_hash, {}).get('duration', 0)

    def get_vod_download(self):
        return self.vod_download

    def set_vod_download(self, download):
        if self.vod_download:
            self.vod_download.set_mode(DLMODE_NORMAL)
            vi_dict = self.vod_info.pop(self.vod_download.get_def().get_id(), None)
            if vi_dict and vi_dict.has_key('stream'):
                vi_dict['stream'][0].close()

        self.vod_download = download
        self.vod_download.set_state_callback(self.monitor_vod)

    def get_vod_fileindex(self):
        return self.vod_fileindex

    def set_vod_fileindex(self, fileindex):
        self.vod_fileindex = fileindex

    def get_vod_filename(self, download):
        filename = download.get_selected_files()[0] if download.get_def().is_multifile_torrent() else download.get_def().get_name()
        filename = os.path.join(download.get_content_dest(), filename)
        return filename


    def launch_video_player(self, cmd, download=None):
        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            self.videoframe.get_videopanel().Load(cmd, download)
            self.videoframe.show_videoframe()
            self.videoframe.get_videopanel().StartPlay()
        else:
            # Launch an external player. Play URL from network or disk.
            try:
                self.player_out, self.player_in = os.popen2(cmd, 'b')
            except:
                print_exc()

    def get_video_player(self, ext, videourl):
        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            self._logger.debug("Videoplayer: using internal player")
            return videourl
        elif self.playbackmode == PLAYBACKMODE_EXTERNAL_MIME and sys.platform == 'win32':
            _, cmd = win32_retrieve_video_play_command(ext, videourl)
            if cmd:
                self._logger.debug("Videoplayer: win32 reg said cmd is %s", cmd)
                return 'start /B "TriblerVideo" ' + cmd

        qprogpath = quote_program_path(self.utility.read_config('videoplayerpath'))
        if not qprogpath:
            return None

        qvideourl = escape_path(videourl)
        if sys.platform == 'win32':
            cmd = 'start /B "TriblerVideo" ' + qprogpath + ' ' + qvideourl
        elif sys.platform == 'darwin':
            cmd = 'open -a ' + qprogpath + ' --args ' + qvideourl
        else:
            cmd = qprogpath + ' ' + qvideourl

        self._logger.debug("Videoplayer: using external user-defined player by executing %s", cmd)

        return cmd

    def stop_playback(self):
        """ Stop playback in current video window """
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe:
            self.videoframe.get_videopanel().Stop()
            self.videoframe.Stop()

    def recreate_videopanel(self):
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe:
            # Playing a video can cause a deadlock in libvlc_media_player_stop. Until we come up with something cleverer, we fix this by recreating the videopanel.
            self.videoframe.recreate_videopanel()

    @forceWxThread
    def set_player_status_and_progress(self, progress, progress_consec, pieces_complete, error=False):
        if self.videoframe is not None:
            self.videoframe.get_videopanel().UpdateStatus(progress, progress_consec, pieces_complete, error)

