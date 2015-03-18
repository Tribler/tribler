# Written by Arno Bakker
# Heavily modified by Egbert Bouman
# see LICENSE.txt for license information
import os
import sys
import time
import logging

from binascii import hexlify
from traceback import print_exc
from collections import defaultdict
from threading import RLock

from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_VIDEO_STARTED, DLMODE_NORMAL, NTFY_VIDEO_BUFFERING
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import VODFile

from Tribler.Core.Video.utils import (win32_retrieve_video_play_command, quote_program_path, escape_path,
                                      return_feasible_playback_modes)
from Tribler.Core.Video.defs import PLAYBACKMODE_INTERNAL, PLAYBACKMODE_EXTERNAL_MIME
from Tribler.Core.Video.VideoUtility import get_videoinfo
from Tribler.Core.Video.VideoServer import VideoServer
from Tribler.Core.Video.VLCWrapper import VLCWrapper


class VideoPlayer(object):

    __single = None

    def __init__(self, session, httpport=None):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.session = session
        self.videoplayerpath = self.session.get_videoplayer_path()
        self.internalplayer_callback = None
        self.vod_download = None
        self.vod_fileindex = None
        self.vod_playing = None
        self.vod_info = defaultdict(dict)

        feasible = return_feasible_playback_modes()
        preferredplaybackmode = self.session.get_preferred_playback_mode()
        self.playbackmode = preferredplaybackmode if preferredplaybackmode in feasible else feasible[0]
        self.vlcwrap = VLCWrapper() if self.playbackmode == PLAYBACKMODE_INTERNAL else None

        # Start HTTP server for serving video
        self.videoserver = VideoServer(httpport or self.session.get_videoplayer_port(), self.session, self)
        self.videoserver.start()

        self.notifier = Notifier.getInstance()

        self.player_out = None
        self.player_in = None

    def shutdown(self):
        if self.videoserver:
            self.videoserver.shutdown()
            self.videoserver.server_close()
        if self.vlcwrap:
            self.vlcwrap.shutdown()
            self.vlcwrap = None
        self.set_vod_download(None)

    def get_vlcwrap(self):
        return self.vlcwrap

    def set_internalplayer_callback(self, callback):
        self.internalplayer_callback = callback

    def play(self, download, fileindex):
        url = 'http://127.0.0.1:' + str(self.videoserver.port) + '/'\
              + hexlify(download.get_def().get_infohash()) + '/' + str(fileindex)
        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            self.launch_video_player(url, download)
        else:
            self.launch_video_player(self.get_video_player(None, url))
        self.vod_playing = None

    def seek(self, pos):
        if self.vod_download:
            self.vod_download.vod_seekpos = None
            self.vod_playing = None

    def monitor_vod(self, ds):
        dl = ds.get_download() if ds else None

        if dl != self.vod_download:
            return 0, False

        bufferprogress = ds.get_vod_prebuffering_progress_consec()

        dl_def = dl.get_def()
        dl_hash = dl_def.get_infohash()

        if (bufferprogress >= 1.0 and not self.vod_playing) or (bufferprogress >= 1.0 and self.vod_playing is None):
            self.vod_playing = True
            self.notifier.notify(NTFY_TORRENTS, NTFY_VIDEO_BUFFERING, (dl_hash, self.vod_fileindex, False))
        elif (bufferprogress <= 0.1 and self.vod_playing) or (bufferprogress < 1.0 and self.vod_playing is None):
            self.vod_playing = False
            self.notifier.notify(NTFY_TORRENTS, NTFY_VIDEO_BUFFERING, (dl_hash, self.vod_fileindex, True))

        if bufferprogress >= 1 and not self.vod_info[dl_hash].has_key('bitrate'):
            self.notifier.notify(NTFY_TORRENTS, NTFY_VIDEO_STARTED, (dl_hash, self.vod_fileindex))

            # Attempt to estimate the bitrate and duration of the videofile with ffmpeg.
            videofile = self.get_vod_filename(dl)
            videoanalyser = self.session.get_video_analyser_path()
            duration, bitrate, _ = get_videoinfo(videofile, videoanalyser)
            self.vod_info[dl_hash]['bitrate'] = bitrate
            self.vod_info[dl_hash]['duration'] = duration

        return 1, False

    def get_vod_stream(self, dl_hash, wait=False):
        if 'stream' not in self.vod_info[dl_hash] and self.session.get_download(dl_hash):
            download = self.session.get_download(dl_hash)
            vod_filename = self.get_vod_filename(download)
            while wait and not os.path.exists(vod_filename):
                time.sleep(1)
            self.vod_info[dl_hash]['stream'] = (VODFile(open(vod_filename, 'rb'), download), RLock())

        if self.vod_info[dl_hash].has_key('stream'):
            return self.vod_info[dl_hash]['stream']
        return None, None

    def get_vod_duration(self, dl_hash):
        return self.vod_info.get(dl_hash, {}).get('duration', 0)

    def get_vod_download(self):
        return self.vod_download

    def set_vod_download(self, download):
        if self.vod_download:
            self.vod_download.set_mode(DLMODE_NORMAL)
            vi_dict = self.vod_info.pop(self.vod_download.get_def().get_infohash(), None)
            if vi_dict and 'stream' in vi_dict:
                vi_dict['stream'][0].close()

        self.vod_download = download
        if self.vod_download:
            self.vod_download.set_state_callback(self.monitor_vod)

    def get_vod_fileindex(self):
        return self.vod_fileindex

    def set_vod_fileindex(self, fileindex):
        self.vod_fileindex = fileindex

    def get_vod_filename(self, download):
        if download.get_def().is_multifile_torrent():
            return os.path.join(download.get_content_dest(), download.get_selected_files()[0])
        else:
            return download.get_content_dest()

    def launch_video_player(self, cmd, download=None):
        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            if self.internalplayer_callback:
                self.internalplayer_callback(cmd, download)
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

        qprogpath = quote_program_path(self.videoplayerpath)
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
