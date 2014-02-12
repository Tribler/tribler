# Written by Arno Bakker
# see LICENSE.txt for license information
from threading import currentThread
from traceback import print_exc
import inspect
import os
import re
import sys
import urllib
import urlparse
import wx
import copy
import logging

from Tribler.Video.defs import *
from Tribler.Video.VideoServer import VideoHTTPServer, VideoRawVLCServer
from Tribler.Video.utils import win32_retrieve_video_play_command, win32_retrieve_playcmd_from_mimetype, quote_program_path, videoextdefaults

from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.unicode import unicode2str, bin2unicode

from Tribler.Video.CachingStream import SmartCachingStream
from Tribler.Video.Ogg import is_ogg, OggMagicLiveStream
from Tribler.Main.vwxGUI import forceWxThread
from Tribler.Core.CacheDB.Notifier import Notifier

if sys.platform == "linux2" or sys.platform == "darwin":
    USE_VLC_RAW_INTERFACE = False
else:
    USE_VLC_RAW_INTERFACE = False  # False for Next-Share

logger = logging.getLogger(__name__)


class VideoPlayer:

    __single = None

    def __init__(self, httpport=6880):
        if VideoPlayer.__single:
            raise RuntimeError("VideoPlayer is singleton")
        VideoPlayer.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        self.videoframe = None
        self.extprogress = None
        self.vod_download = None
        self.playbackmode = None
        self.preferredplaybackmode = None
        self.closeextplayercallback = None

        self.videohttpservport = httpport
        self.videohttpserv = None
        # Must create the instance here, such that it won't get garbage collected
        self.videorawserv = VideoRawVLCServer.getInstance()

        self.resume_by_system = 0
        self.user_download_choice = None

        self.notifier = Notifier.getInstance()

    def getInstance(*args, **kw):
        if VideoPlayer.__single is None:
            VideoPlayer(*args, **kw)
        return VideoPlayer.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        if VideoPlayer.__single and VideoPlayer.__single.videohttpserv:
            VideoPlayer.__single.videohttpserv.delInstance()
            VideoPlayer.__single = None
    delInstance = staticmethod(delInstance)

    def hasInstance():
        return VideoPlayer.__single and VideoPlayer.__single.vlcwrap and VideoPlayer.__single.vlcwrap.initialized
    hasInstance = staticmethod(hasInstance)

    def register(self, utility, preferredplaybackmode=None, closeextplayercallback=None):

        self.utility = utility  # TEMPARNO: make sure only used for language strings

        self.preferredplaybackmode = preferredplaybackmode
        self.determine_playbackmode()

        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            # The python-vlc bindings. Created only once at the moment,
            # as using MediaControl.exit() more than once with the raw interface
            # blows up the GUI.
            #
            from Tribler.Video.VLCWrapper import VLCWrapper
            self.vlcwrap = VLCWrapper(self.utility.getPath())
        else:
            self.vlcwrap = None

        if self.playbackmode != PLAYBACKMODE_INTERNAL or not USE_VLC_RAW_INTERFACE:
            # Start HTTP server for serving video to external player
            self.videohttpserv = VideoHTTPServer.getInstance(self.videohttpservport)  # create
            self.videohttpserv.background_serve()

        if closeextplayercallback is not None:
            self.closeextplayercallback = closeextplayercallback

    def shutdown(self):
        if self.videohttpserv:
            self.videohttpserv.shutdown()
            self.videohttpserv.server_close()

    def get_vlcwrap(self):
        return self.vlcwrap

    def set_videoframe(self, videoframe):
        self.videoframe = videoframe

    def play_file(self, dest):
        """ Play video file from disk """
        self._logger.debug("videoplay: Playing file from disk %s", dest)

        (prefix, ext) = os.path.splitext(dest)
        [mimetype, cmd] = self.get_video_player(ext, dest)

        self._logger.debug("videoplay: play_file: cmd is %s", cmd)

        self.launch_video_player(cmd)

    def play_file_via_httpserv(self, dest):
        """ Play a file via our internal HTTP server. Needed when the user
        selected embedded VLC as player and the filename contains Unicode
        characters.
        """
        self._logger.debug("videoplay: Playing file with Unicode filename via HTTP")

        (prefix, ext) = os.path.splitext(dest)
        videourl = self.create_url(self.videohttpserv, '/' + os.path.basename(prefix + ext))
        [mimetype, cmd] = self.get_video_player(ext, videourl)

        stream = open(dest, "rb")
        stats = os.stat(dest)
        length = stats.st_size
        streaminfo = {'mimetype': mimetype, 'stream': stream, 'length':length}
        self.videohttpserv.set_inputstream(streaminfo)

        self.launch_video_player(cmd)

    def play_url(self, url):
        """ Play video file from network or disk """
        self._logger.debug("videoplay: Playing file from url %s", url)

        self.determine_playbackmode()

        t = urlparse.urlsplit(url)
        dest = t[2]

        # VLC will play .flv files, but doesn't like the URLs that YouTube uses,
        # so quote them
        if self.playbackmode != PLAYBACKMODE_INTERNAL:
            if sys.platform == 'win32':
                x = [t[0], t[1], t[2], t[3], t[4]]
                n = urllib.quote(x[2])
                self._logger.debug("videoplay: play_url: OLD PATH WAS %s NEW PATH %s", x[2], n)
                x[2] = n
                n = urllib.quote(x[3])
                self._logger.debug("videoplay: play_url: OLD QUERY WAS %s NEW PATH %s", x[3], n)
                x[3] = n
                url = urlparse.urlunsplit(x)
            elif url[0] != '"' and url[0] != "'":
                # to prevent shell escape problems
                # TODO: handle this case in escape_path() that now just covers spaces
                url = "'" + url + "'"

        (prefix, ext) = os.path.splitext(dest)
        [mimetype, cmd] = self.get_video_player(ext, url)

        self._logger.debug("videoplay: play_url: cmd is %s", cmd)

        self.launch_video_player(cmd)

    def play_stream(self, streaminfo):
        self._logger.debug("videoplay: play_stream")

        self.determine_playbackmode()

        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            if USE_VLC_RAW_INTERFACE:
                # Play using direct callbacks from the VLC C-code
                self.launch_video_player(None, streaminfo=streaminfo)
            else:
                if 'url' in streaminfo:
                    url = streaminfo['url']
                    self.launch_video_player(url, streaminfo=streaminfo)
                else:
                    # Play via internal HTTP server
                    self.videohttpserv.set_inputstream(streaminfo, '/')
                    url = self.create_url(self.videohttpserv, '/')

                    self.launch_video_player(url, streaminfo=streaminfo)
        else:
            # External player, play stream via internal HTTP server
            path = '/'
            self.videohttpserv.set_inputstream(streaminfo, path)
            url = self.create_url(self.videohttpserv, path)

            [mimetype, cmd] = self.get_video_player(None, url, mimetype=streaminfo['mimetype'])
            self.launch_video_player(cmd)

    def launch_video_player(self, cmd, streaminfo=None):
        if self.playbackmode == PLAYBACKMODE_INTERNAL:

            if cmd is not None:
                # Play URL from network or disk
                self.videoframe.get_videopanel().Load(cmd, streaminfo=streaminfo)
            else:
                # Play using direct callbacks from the VLC C-code
                self.videoframe.get_videopanel().Load(cmd, streaminfo=streaminfo)

            self.videoframe.show_videoframe()
            self.videoframe.get_videopanel().StartPlay()
        else:
            # Launch an external player
            # Play URL from network or disk
            self.exec_video_player(cmd)

    def stop_playback(self, reset=False):
        """ Stop playback in current video window """
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe is not None:
            self.videoframe.get_videopanel().Stop()
            self.videoframe.Stop()
            if reset:
                self.videoframe.get_videopanel().Reset()
        self.set_vod_download(None)

    def pause_playback(self):
        """ Pause playback in current video window """
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe is not None:
            self.videoframe.get_videopanel().Pause()

    def resume_playback(self):
        """ Resume playback in current video window """
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe is not None:
            self.videoframe.get_videopanel().Resume()

    def show_loading(self):
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe is not None:
            self.videoframe.get_videopanel().ShowLoading()
            self.videoframe.ShowLoading()

    def recreate_videopanel(self):
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe is not None:
            # Playing a video can cause a deadlock in libvlc_media_player_stop. Until we come up with something cleverer, we fix this by recreating the videopanel.
            self.videoframe.recreate_videopanel()

    def close(self):
        """ Stop playback and close current video window """
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe is not None:
            self.videoframe.hide_videoframe()
        self.set_vod_download(None)

    def play(self, ds, selectedinfilename=None):
        """ Used by Tribler Main """
        self.determine_playbackmode()

        d = ds.get_download()
        cdef = d.get_def()

        if selectedinfilename is None:
            # User didn't select file to play, select if there is a single, or ask
            videofiles = d.get_dest_files(exts=videoextdefaults)
            if len(videofiles) == 0:
                self._logger.info("videoplay: play: No video files found! Let user select")
                # Let user choose any file
                videofiles = d.get_dest_files(exts=None)

            if len(videofiles) > 1:
                infilenames = []
                for infilename, diskfilename in videofiles:
                    infilenames.append(infilename)

                selectedinfilename = self.ask_user_to_select_video(infilenames)
                self._logger.info("selectedinfilename == None %s %s", selectedinfilename, len(selectedinfilename))

                if selectedinfilename is None:
                    self._logger.info("videoplay: play: User selected no video")
                    return
            else:
                selectedinfilename = videofiles[0][0]

        self._logger.info("videoplay: play: PROGRESS %s", ds.get_progress())
        complete = ds.get_progress() == 1.0 or ds.get_status() == DLSTATUS_SEEDING

        if cdef.get_def_type() == 'swift' or not complete:
            self._logger.info('videoplay: play: not complete')
            self.play_vod(ds, selectedinfilename)

        else:
            videofiles = d.get_dest_files(exts=videoextdefaults)
            if len(videofiles) == 0:
                self._logger.info("videoplay: play: No video files found! Let user select")
                # Let user choose any file
                videofiles = d.get_dest_files(exts=None)

            selectedoutfilename = None
            for infilename, diskfilename in videofiles:
                if infilename == selectedinfilename:
                    selectedoutfilename = diskfilename

            # 23/02/10 Boudewijn: This Download does not contain the
            # selectedinfilename in the available files.  It is likely
            # that this is a multifile torrent and that another file was
            # previously selected for download.
            if selectedoutfilename is None:
                return self.play_vod(ds, selectedinfilename)

            self._logger.info('videoplay: play: complete')
            flag = self.playbackmode == PLAYBACKMODE_INTERNAL and not self.is_ascii_filename(selectedoutfilename)
            if flag:
                self.play_file_via_httpserv(selectedoutfilename)
            else:
                self.play_file(selectedoutfilename)

            self.set_vod_download(d)

    def play_vod(self, ds, infilename):
        """ Called by GUI thread when clicking "Play ASAP" button """

        d = ds.get_download()
        cdef = d.get_def()

        self._logger.debug("videoplay: play_vod: Enabling VOD on torrent %s", cdef.get_name())

        # Restart download
        d.set_video_event_callback(self.sesscb_vod_event_callback)
        if cdef.get_def_type() != "torrent" or d.get_def().is_multifile_torrent():
            d.set_selected_files([infilename])

        self._logger.info("videoplay: play_vod: Restarting existing Download %s", cdef.get_id())
        self.set_vod_download(d)
        d.set_mode(DLMODE_VOD)
        d.restart()

    def start_and_play(self, cdef, dscfg, selectedinfilename=None):
        """ Called by GUI thread when Tribler started with live or video torrent on cmdline """

        # ARNO50: > Preview1: TODO: make sure this works better when Download already existed.
        if selectedinfilename == None and cdef.get_def_type() == "torrent":
            if not cdef.get_live():
                videofiles = cdef.get_files(exts=videoextdefaults)
                if len(videofiles) == 1:
                    selectedinfilename = videofiles[0]

                elif len(videofiles) > 1:
                    selectedinfilename = self.ask_user_to_select_video(videofiles)

        if selectedinfilename or cdef.get_live():
            if cdef.get_def_type() != "torrent" or cdef.is_multifile_torrent():
                dscfg.set_selected_files([selectedinfilename])

            # Restart download
            dscfg.set_video_event_callback(self.sesscb_vod_event_callback)
            dscfg.set_mode(DLMODE_VOD)
            self._logger.info("videoplay: Starting new VOD/live Download %s", repr(cdef.get_name()))

            download = self.utility.session.start_download(cdef, dscfg)

            self.set_vod_download(download)
            return download

        else:
            return None

    def sesscb_vod_event_callback(self, d, event, params):
        """ Called by the Session when the content of the Download is ready

        Called by Session thread """

        self._logger.info("videoplay: sesscb_vod_event_callback called %s ###########################################################", currentThread().getName())
        wx.CallAfter(self.gui_vod_event_callback, d, event, params)

    def gui_vod_event_callback(self, d, event, params):
        """ Also called by SwarmPlayer """

        self._logger.info("videoplay: gui_vod_event: %s", event)
        if event == VODEVENT_START:
            filename = params["filename"]
            mimetype = params["mimetype"]
            stream = params["stream"]
            length = params["length"]

            if filename:
                self.play_file(filename)
            else:
                if d.get_def().get_live():
                    cachestream = stream
                    blocksize = d.get_def().get_piece_length()
                else:
                    if d.get_def().get_def_type() == "swift":
                        piecelen = 2 ** 16
                    else:
                        piecelen = d.get_def().get_piece_length()

                    if False and piecelen > 2 ** 17:
                        # Arno, 2010-01-21:
                        # Workaround for streams with really large piece
                        # sizes. For some content/containers, VLC can do
                        # GET X-, GET X+10K-, GET X+20K HTTP requests
                        # and we would answer these by putting megabytes
                        # into the stream buffer, of which only 10K would be
                        # used. This kills performance. Hence I add a caching
                        # stream that tries to resolve answers from its internal
                        # buffer, before reading the engine's stream.
                        # This works, but only if the HTTP server doesn't
                        # read too aggressively, i.e., uses small blocksize.
                        #
                        cachestream = SmartCachingStream(stream)

                        blocksize = max(32768, piecelen / 8)
                    else:
                        cachestream = stream
                        blocksize = piecelen

                if d.get_def().get_live() and is_ogg(d.get_def().get_name_as_unicode()):
                    # Live Ogg stream. To support this we need to do
                    # two things:
                    # 1. Write Ogg headers (stored in .tstream)
                    # 2. Find first Ogg page in stream.
                    cachestream = OggMagicLiveStream(d.get_def(), stream)

                # Estimate duration. Video player (e.g. VLC) often can't tell
                # when streaming.
                estduration = None
                if d.get_def().get_def_type() == "torrent":
                    if d.get_def().get_live():
                        # Set correct Ogg MIME type
                        if is_ogg(d.get_def().get_name_as_unicode()):
                            mimetype = 'application/ogg'
                    else:
                        file = None
                        if d.get_def().is_multifile_torrent():
                            file = d.get_selected_files()[0]
                        bitrate = d.get_def().get_bitrate(file)
                        if bitrate is not None:
                            estduration = float(length) / float(bitrate)

                        # Set correct Ogg MIME type
                        if file is None:
                            if is_ogg(d.get_def().get_name_as_unicode()):
                                mimetype = 'application/ogg'
                        else:
                            if is_ogg(file):
                                mimetype = 'application/ogg'


                streaminfo = {'mimetype': mimetype, 'stream': cachestream, 'length':length, 'blocksize':blocksize, 'estduration':estduration}

                if d.get_def().get_def_type() == "swift":
                    streaminfo['url'] = params['url']

                self.play_stream(streaminfo)

        elif event == VODEVENT_PAUSE:
            if self.videoframe is not None:
                self.videoframe.get_videopanel().Pause(gui_vod_event=True)
        elif event == VODEVENT_RESUME:
            if self.videoframe is not None:
                self.videoframe.get_videopanel().Resume()

    def ask_user_to_select_video(self, videofiles):
        dlg = VideoChooser(None, self.utility, videofiles, title='Tribler', expl='Select which file to play')
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            index = dlg.getChosenIndex()
            filename = videofiles[index]
        else:
            filename = None
        dlg.Destroy()
        return filename

    def is_ascii_filename(self, filename):
        if isinstance(filename, str):
            return True
        try:
            filename.encode('ascii', 'strict')
            return True
        except:
            print_exc()
            return False

    def create_url(self, videoserver, upath):
        schemeserv = 'http://127.0.0.1:' + str(videoserver.get_port())
        asciipath = unicode2str(upath)
        return schemeserv + urllib.quote(asciipath)



    def get_video_player(self, ext, videourl, mimetype=None):

        video_player_path = self.utility.read_config('videoplayerpath')
        self._logger.debug("videoplay: Default player is %s", video_player_path)

        if mimetype is None:
            if sys.platform == 'win32':
                # TODO: Use Python's mailcap facility on Linux to find player
                [mimetype, playcmd] = win32_retrieve_video_play_command(ext, videourl)
                self._logger.debug("videoplay: Win32 reg said playcmd is %s", playcmd)

            if mimetype is None:
                if ext == '.avi':
                    # Arno, 2010-01-08: Hmmm... video/avi is not official registered at IANA
                    mimetype = 'video/avi'
                elif ext == '.mpegts' or ext == '.ts':
                    mimetype = 'video/mp2t'
                else:
                    mimetype = 'video/mpeg'
        else:
            if sys.platform == 'win32':
                [mimetype, playcmd] = win32_retrieve_playcmd_from_mimetype(mimetype, videourl)

        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            self._logger.debug("videoplay: using internal player")
            return [mimetype, videourl]
        elif self.playbackmode == PLAYBACKMODE_EXTERNAL_MIME and sys.platform == 'win32':
            if playcmd is not None:
                cmd = 'start /B "TriblerVideo" ' + playcmd
                return [mimetype, cmd]

        self._logger.debug("videoplay: Defaulting to default player %s", video_player_path)
        qprogpath = quote_program_path(video_player_path)
        # print >>sys.stderr,"videoplay: Defaulting to quoted prog",qprogpath
        if qprogpath is None:
            return [None, None]
        qvideourl = self.escape_path(videourl)
        playcmd = qprogpath + ' ' + qvideourl
        if sys.platform == 'win32':
            cmd = 'start /B "TriblerVideo" ' + playcmd
        elif sys.platform == 'darwin':
            playcmd = qprogpath + ' --args ' + qvideourl
            cmd = 'open -a ' + playcmd
        else:
            cmd = playcmd
        self._logger.debug("videoplay: using external user-defined player by executing %s", cmd)
        return [mimetype, cmd]

    def exec_video_player(self, cmd):
        self._logger.debug("videoplay: Command is @" + cmd + "@")
        # I get a weird problem on Linux. When doing a
        # os.popen2("vlc /tmp/file.wmv") I get the following error:
        # [00000259] main interface error: no suitable interface module
        # [00000001] main private error: interface "(null)" initialization failed
        #
        # The only thing that appears to work is
        # os.system("vlc /tmp/file.wmv")
        # but that halts Tribler, as it waits for the created shell to
        # finish. Hmmmm....
        #
        try:
            if sys.platform == 'win32':
                # os.system(cmd)
                (self.player_out, self.player_in) = os.popen2(cmd, 'b')
            else:
                (self.player_out, self.player_in) = os.popen2(cmd, 'b')
        except Exception as e:
            print_exc()
            self.onError(self.utility.lang.get('videoplayerstartfailure'), cmd, str(e.__class__) + ':' + str(e))

    def escape_path(self, path):
        if path[0] != '"' and path[0] != "'" and path.find(' ') != -1:
            if sys.platform == 'win32':
                # Add double quotes
                path = "\"" + path + "\""
            else:
                path = "\'" + path + "\'"
        return path


    def onError(self, action, value, errmsg=u''):
        self.onMessage(wx.ICON_ERROR, action, value, errmsg)

    def onWarning(self, action, value, errmsg=u''):
        self.onMessage(wx.ICON_INFORMATION, action, value, errmsg)

    def onMessage(self, icon, action, value, errmsg=u''):
        # Don't use language independence stuff, self.utility may not be
        # valid.
        msg = action
        msg += '\n'
        msg += value
        msg += '\n'
        msg += errmsg
        msg += '\n'
        dlg = wx.MessageDialog(None, msg, self.utility.lang.get('videoplayererrortitle'), wx.OK | icon)
        result = dlg.ShowModal()
        dlg.Destroy()

    def set_vod_download(self, d):
        old_download = self.vod_download
        new_download = d

        if d != self.vod_download:
            if self.vod_download:
                self.vod_download.set_mode(DLMODE_NORMAL)
                if self.vod_download.get_def().get_def_type() == 'torrent':
                    self.vod_download.set_vod_mode(False)

            self.vod_download = d

        if old_download and old_download.get_def().get_def_type() == 'torrent':
            selected_files = old_download.get_selected_files()
            fileindex = old_download.get_def().get_index_of_file_in_files(selected_files[0]) if old_download.get_def().is_multifile_torrent() and selected_files else 0
            self.notifier.notify(NTFY_TORRENTS, NTFY_VIDEO_STOPPED, (old_download.get_def().get_id(), fileindex))

        if new_download and new_download.get_def().get_def_type() == 'torrent':
            selected_files = new_download.get_selected_files()
            fileindex = new_download.get_def().get_index_of_file_in_files(selected_files[0]) if new_download.get_def().is_multifile_torrent() and selected_files else 0
            self.notifier.notify(NTFY_TORRENTS, NTFY_VIDEO_STARTED, (new_download.get_def().get_id(), fileindex))

    def get_vod_download(self):
        return self.vod_download

    #
    # Set information about video playback progress that is displayed
    # to the user.
    #
    @forceWxThread
    def set_player_status_and_progress(self, progress, progress_consec, pieces_complete, error=False):
        if self.videoframe is not None:
            self.videoframe.get_videopanel().UpdateStatus(progress, progress_consec, pieces_complete, error)

    @forceWxThread
    def set_save_button(self, enable, savebutteneventhandler):
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe is not None:
            self.videoframe.get_videopanel().EnableSaveButton(enable, savebutteneventhandler)

    def get_state(self):
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe is not None:
            return self.videoframe.get_videopanel().GetState()
        else:
            return MEDIASTATE_PLAYING

    def determine_playbackmode(self):
        feasible = return_feasible_playback_modes(self.utility.getPath())
        if self.preferredplaybackmode in feasible:
            self.playbackmode = self.preferredplaybackmode
        else:
            self.playbackmode = feasible[0]

    def get_playbackmode(self):
        return self.playbackmode

    # def set_preferredplaybackmode(self,mode):
    #    This is a bit complex: If there is no int. player avail we change
    #    the VideoFrame to contain some minimal info. Would have to dynamically
    #    change that back if we allow dynamic switching of video player.
    #    self.preferredplaybackmode = mode


class VideoChooser(wx.Dialog):

    def __init__(self, parent, utility, filelist, title=None, expl=None):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.utility = utility
        self.filelist = []

        # Convert to Unicode for display
        for file in filelist:
            u = bin2unicode(file)
            self.filelist.append(u)

        self._logger.debug("VideoChooser: filelist %s", self.filelist)

        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        if title is None:
            title = self.utility.lang.get('selectvideofiletitle')
        wx.Dialog.__init__(self, parent, -1, title, style=style)

        sizer = wx.BoxSizer(wx.VERTICAL)
        filebox = wx.BoxSizer(wx.VERTICAL)
        self.file_chooser = wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(300, -1), self.filelist)
        self.file_chooser.SetSelection(0)

        if expl is None:
            self.utility.lang.get('selectvideofile')
        filebox.Add(wx.StaticText(self, -1, expl), 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        filebox.Add(self.file_chooser)
        sizer.Add(filebox, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        okbtn = wx.Button(self, wx.ID_OK, label=self.utility.lang.get('ok'), style=wx.BU_EXACTFIT)
        buttonbox.Add(okbtn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 5)
        cancelbtn = wx.Button(self, wx.ID_CANCEL, label=self.utility.lang.get('cancel'), style=wx.BU_EXACTFIT)
        buttonbox.Add(cancelbtn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 5)
        sizer.Add(buttonbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        self.SetSizerAndFit(sizer)

    def getChosenIndex(self):
        return self.file_chooser.GetSelection()


def parse_playtime_to_secs(hhmmss):
    logger.debug("videoplay: Playtime is %s", hhmmss)
    r = re.compile("([0-9]+):*")
    occ = r.findall(hhmmss)
    t = None
    if len(occ) > 0:
        if len(occ) == 3:
            # hours as well
            t = int(occ[0]) * 3600 + int(occ[1]) * 60 + int(occ[2])
        elif len(occ) == 2:
            # minutes and seconds
            t = int(occ[0]) * 60 + int(occ[1])
        elif len(occ) == 1:
            # seconds
            t = int(occ[0])
    return t


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

        if USE_VLC_RAW_INTERFACE:
            # check if the special raw interface is available
            # pylint: disable-msg=E1101
            if not inspect.ismethoddescriptor(vlc.MediaControl.set_raw_callbacks):
                raise Exception("Incorrect vlc plugin. This does not provide the set_raw_callbacks method")
            # pylint: enable-msg=E1101
        l.append(PLAYBACKMODE_INTERNAL)
    except Exception:
        print_exc()

    if sys.platform == 'win32':
        l.append(PLAYBACKMODE_EXTERNAL_MIME)
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    else:
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    return l
