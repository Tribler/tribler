# Written by Arno Bakker
# see LICENSE.txt for license information
import wx
import sys
import urllib
import urlparse
import logging

from binascii import hexlify
from traceback import print_exc
from threading import currentThread

from Tribler.Video.defs import *
from Tribler.Video.VideoServer import VideoServer
from Tribler.Video.utils import win32_retrieve_video_play_command, quote_program_path, escape_path, videoextdefaults
from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.unicode import bin2unicode

from Tribler.Main.vwxGUI import forceWxThread
from Tribler.Core.CacheDB.Notifier import Notifier

logger = logging.getLogger(__name__)


class VideoPlayer:

    __single = None

    def __init__(self, httpport=6880):
        if VideoPlayer.__single:
            raise RuntimeError("VideoPlayer is singleton")
        VideoPlayer.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        self.videoframe = None
        self.vod_download = None
        self.vod_fileindex = None
        self.playbackmode = None

        self.videoserverport = httpport
        self.videoserver = None

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

    def register(self, utility, preferredplaybackmode=None):
        self.utility = utility
        feasible = return_feasible_playback_modes(self.utility.getPath())
        self.playbackmode = preferredplaybackmode if preferredplaybackmode in feasible else feasible[0]

        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            from Tribler.Video.VLCWrapper import VLCWrapper
            self.vlcwrap = VLCWrapper(self.utility.getPath())
        else:
            self.vlcwrap = None

        # Start HTTP server for serving video
        self.videoserver = VideoServer.getInstance(self.videoserverport, self.utility.session)
        self.videoserver.start()

    def shutdown(self):
        if self.videoserver:
            self.videoserver.stop()

    def get_vlcwrap(self):
        return self.vlcwrap

    def set_videoframe(self, videoframe):
        self.videoframe = videoframe

    def stop_playback(self):
        """ Stop playback in current video window """
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe:
            self.videoframe.get_videopanel().Stop()
            self.videoframe.Stop()
        self.set_vod_download(None)

    def pause_playback(self):
        """ Pause playback in current video window """
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe:
            self.videoframe.get_videopanel().Pause()

    def resume_playback(self):
        """ Resume playback in current video window """
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe:
            self.videoframe.get_videopanel().Resume()

    def show_loading(self):
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe:
            self.videoframe.get_videopanel().ShowLoading()
            self.videoframe.ShowLoading()

    def recreate_videopanel(self):
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe:
            # Playing a video can cause a deadlock in libvlc_media_player_stop. Until we come up with something cleverer, we fix this by recreating the videopanel.
            self.videoframe.recreate_videopanel()

    def play(self, ds, selectedinfilename):
        download = ds.get_download()
        cdef = download.get_def()
        videofiles = download.get_dest_files(exts=videoextdefaults)

        # If the user didn't select a file to play, select if there is a single, or ask
        if selectedinfilename is None:
            if len(videofiles) == 0:
                self._logger.error("Videoplayer: no video files found!")
                return
            elif len(videofiles) > 1:
                selectedinfilename = self.ask_user_to_select_video([infilename for infilename, _ in videofiles])
                if selectedinfilename is None:
                    self._logger.error("Videoplayer: user did not select a video")
                    return
            else:
                selectedinfilename = videofiles[0][0]
        elif selectedinfilename not in cdef.get_files():
            self._logger.error("Videoplayer: unknown video file!")
            return

        self._logger.info("Videoplayer: play: PROGRESS %s", ds.get_progress())
        complete = ds.get_progress() == 1.0 or ds.get_status() == DLSTATUS_SEEDING
        selectedoutfilenames = [outfilename for infilename, outfilename in videofiles if selectedinfilename == infilename]
        selectedoutfilename = selectedoutfilenames[0] if selectedoutfilenames else None

        if cdef.get_def_type() == 'swift' or not complete or not selectedoutfilename:
            self._logger.info("Videoplayer: enabling VOD on torrent %s", cdef.get_name())
            download.set_video_event_callback(self.sesscb_vod_event_callback)
            if cdef.get_def_type() != "torrent" or download.get_def().is_multifile_torrent():
                download.set_selected_files([selectedinfilename])
            download.set_mode(DLMODE_VOD)
            download.restart()
        else:
            self._logger.debug("Videoplayer: playing file from disk %s", selectedoutfilename)
            cmd = self.get_video_player(os.path.splitext(selectedoutfilename)[1], selectedoutfilename)
            self.launch_video_player(cmd)

        files = download.get_def().get_files()
        fileindex = files.index(selectedinfilename) if selectedinfilename in files else None
        self.set_vod_download(download, fileindex)

    def launch_video_player(self, cmd):
        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            self.videoframe.get_videopanel().Load(cmd)
            self.videoframe.show_videoframe()
            self.videoframe.get_videopanel().StartPlay()
        else:
            # Launch an external player. Play URL from network or disk
            self.exec_video_player(cmd)

    def sesscb_vod_event_callback(self, d, event, params):
        """ Called by the Session when the content of the Download is ready.  Called by Session thread """

        self._logger.info("Videoplayer: sesscb_vod_event_callback called %s", currentThread().getName())
        wx.CallAfter(self.gui_vod_event_callback, d, event, params)

    def gui_vod_event_callback(self, d, event, params):
        self._logger.info("Videoplayer: gui_vod_event: %s", event)
        if event == VODEVENT_START:

            if params["filename"]:
                cmd = self.get_video_player(os.path.splitext(params["filename"])[1], params["filename"])
                self.launch_video_player(cmd)
            else:
                if self.playbackmode == PLAYBACKMODE_INTERNAL:
                    if 'url' in params:
                        self.launch_video_player(params['url'])
                    else:
                        # Play via internal HTTP server
                        url = 'http://127.0.0.1:' + str(self.videoserver.port) + '/' + hexlify(d.get_def().get_id()) + '/' + str(d.get_vod_fileindex())
                        self.launch_video_player(url)

                else:
                    # External player, play stream via internal HTTP server
                    url = 'http://127.0.0.1:' + str(self.videoserver.port) + '/' + hexlify(d.get_def().get_id()) + '/' + str(d.get_vod_fileindex())
                    self.launch_video_player(self.get_video_player(None, url))

        elif event == VODEVENT_PAUSE:
            if self.videoframe is not None:
                self.videoframe.get_videopanel().Pause(gui_vod_event=True)
        elif event == VODEVENT_RESUME:
            if self.videoframe is not None:
                self.videoframe.get_videopanel().Resume()

    def ask_user_to_select_video(self, videofiles, selected_file=None):
        if len(videofiles) > 1:
            videofiles.sort()
            dialog = wx.SingleChoiceDialog(None, 'Tribler currently only supports playing one file at a time.\nSelect the file you want to play.', 'Which file do you want to play?', videofiles)
            if selected_file in videofiles:
                dialog.SetSelection(videofiles.index(selected_file))

            selected_file = dialog.GetStringSelection() if dialog.ShowModal() == wx.ID_OK else None
            dialog.Destroy()
            return selected_file
        elif len(videofiles) == 1:
            return videofiles[0]

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

    def exec_video_player(self, cmd):
        self._logger.debug("Videoplayer: player command is " + cmd)
        try:
            self.player_out, self.player_in = os.popen2(cmd, 'b')
        except:
            print_exc()
            dlg = wx.MessageDialog(None, 'Could not execute player using command: ' + cmd, self.utility.lang.get('videoplayererrortitle'), wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()

    def set_vod_download(self, download, fileindex=None):
        old_download = self.vod_download
        old_fileindex = self.vod_fileindex

        if download != self.vod_download:
            if self.vod_download:
                self.vod_download.set_mode(DLMODE_NORMAL)
                if self.vod_download.get_def().get_def_type() == 'torrent':
                    self.vod_download.set_vod_mode(False)
            self.vod_download = download
        self.vod_fileindex = fileindex

        if old_download and old_download.get_def().get_def_type() == 'torrent':
            self.notifier.notify(NTFY_TORRENTS, NTFY_VIDEO_STOPPED, (old_download.get_def().get_id(), old_fileindex))

        if download and download.get_def().get_def_type() == 'torrent':
            self.notifier.notify(NTFY_TORRENTS, NTFY_VIDEO_STARTED, (download.get_def().get_id(), fileindex))

    def get_vod_download(self, include_fileindex=False):
        return (self.vod_download, self.vod_fileindex) if include_fileindex else self.vod_download

    @forceWxThread
    def set_player_status_and_progress(self, progress, progress_consec, pieces_complete, error=False):
        if self.videoframe is not None:
            self.videoframe.get_videopanel().UpdateStatus(progress, progress_consec, pieces_complete, error)

    def get_playbackmode(self):
        return self.playbackmode


def return_feasible_playback_modes(syspath):
    if sys.platform == 'darwin':
        return [PLAYBACKMODE_EXTERNAL_DEFAULT]

    l = []
    try:
        import Tribler.vlc as vlc

        # Niels: check version of vlc
        version = vlc.libvlc_get_version()
        subversions = version.split(".")
        if len(subversions) > 2:
            version = subversions[0] + "." + subversions[1]
        version = float(version)
        if version < 0.9:
            raise Exception("Incorrect vlc version. We require at least version 0.9, this is %s" % version)

        l.append(PLAYBACKMODE_INTERNAL)
    except Exception:
        print_exc()

    if sys.platform == 'win32':
        l.append(PLAYBACKMODE_EXTERNAL_MIME)
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    else:
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    return l
