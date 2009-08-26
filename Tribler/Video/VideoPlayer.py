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

from Tribler.Video.defs import *
from Tribler.Video.VideoServer import VideoHTTPServer,VideoRawVLCServer
from Tribler.Video.utils import win32_retrieve_video_play_command,win32_retrieve_playcmd_from_mimetype,quote_program_path,videoextdefaults

from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.unicode import unicode2str,bin2unicode

DEBUG = True


if sys.platform == "linux2" or sys.platform == "darwin":
    USE_VLC_RAW_INTERFACE = False
else:
    USE_VLC_RAW_INTERFACE = False # False for Next-Share
    

class VideoPlayer:
    
    __single = None
    
    def __init__(self,httpport=6880):
        if VideoPlayer.__single:
            raise RuntimeError, "VideoPlayer is singleton"
        VideoPlayer.__single = self
        self.videoframe = None
        self.extprogress = None
        self.vod_download = None
        self.playbackmode = None
        self.preferredplaybackmode = None
        self.vod_postponed_downloads = []
        self.other_downloads = None
        self.closeextplayercallback = None

        self.videohttpservport = httpport
        self.videohttpserv = None
        # Must create the instance here, such that it won't get garbage collected
        self.videorawserv = VideoRawVLCServer.getInstance()

        
    def getInstance(*args, **kw):
        if VideoPlayer.__single is None:
            VideoPlayer(*args, **kw)
        return VideoPlayer.__single
    getInstance = staticmethod(getInstance)
        
    def register(self,utility,preferredplaybackmode=None,closeextplayercallback=None):
        
        self.utility = utility # TEMPARNO: make sure only used for language strings

        self.preferredplaybackmode = preferredplaybackmode
        self.determine_playbackmode()

        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            # The python-vlc bindings. Created only once at the moment,
            # as using MediaControl.exit() more than once with the raw interface
            # blows up the GUI.
            #
            from Tribler.Video.VLCWrapper import VLCWrapper
            self.vlcwrap = VLCWrapper(self.utility.getPath())
            self.supportedvodevents = [VODEVENT_START,VODEVENT_PAUSE,VODEVENT_RESUME]
        else:
            self.vlcwrap = None
            # Can't pause when external player
            self.supportedvodevents = [VODEVENT_START]
            
        if self.playbackmode != PLAYBACKMODE_INTERNAL or not USE_VLC_RAW_INTERFACE:
            # Start HTTP server for serving video to external player
            self.videohttpserv = VideoHTTPServer.getInstance(self.videohttpservport) # create
            self.videohttpserv.background_serve()
            self.videohttpserv.register(self.videohttpserver_error_callback,self.videohttpserver_set_status_callback)
            
        if closeextplayercallback is not None:
            self.closeextplayercallback = closeextplayercallback

    def set_other_downloads(self, other_downloads):
        """A boolean indicating whether there are other downloads running at this time"""
        self.other_downloads = other_downloads

    def get_vlcwrap(self):
        return self.vlcwrap
    
    def get_supported_vod_events(self):
        return self.supportedvodevents

    def set_videoframe(self,videoframe):
        self.videoframe = videoframe


    def play_file(self,dest): 
        """ Play video file from disk """
        if DEBUG:
            print >>sys.stderr,"videoplay: Playing file from disk",dest

        (prefix,ext) = os.path.splitext(dest)
        [mimetype,cmd] = self.get_video_player(ext,dest)
        
        if DEBUG:
            print >>sys.stderr,"videoplay: play_file: cmd is",cmd
 
        self.launch_video_player(cmd)

    def play_file_via_httpserv(self,dest):
        """ Play a file via our internal HTTP server. Needed when the user
        selected embedded VLC as player and the filename contains Unicode
        characters.
        """ 
        if DEBUG:
            print >>sys.stderr,"videoplay: Playing file with Unicode filename via HTTP"

        (prefix,ext) = os.path.splitext(dest)
        videourl = self.create_url(self.videohttpserv,'/'+os.path.basename(prefix+ext))
        [mimetype,cmd] = self.get_video_player(ext,videourl)

        stream = open(dest,"rb")
        stats = os.stat(dest)
        length = stats.st_size
        streaminfo = {'mimetype':mimetype,'stream':stream,'length':length}
        self.videohttpserv.set_inputstream(streaminfo)
        
        self.launch_video_player(cmd)


 
    def play_url(self,url):
        """ Play video file from network or disk """
        if DEBUG:
            print >>sys.stderr,"videoplay: Playing file from url",url
        
        self.determine_playbackmode()
        
        t = urlparse.urlsplit(url)
        dest = t[2]
        
        # VLC will play .flv files, but doesn't like the URLs that YouTube uses,
        # so quote them
        if self.playbackmode != PLAYBACKMODE_INTERNAL:
            if sys.platform == 'win32':
                x = [t[0],t[1],t[2],t[3],t[4]]
                n = urllib.quote(x[2])
                if DEBUG:
                    print >>sys.stderr,"videoplay: play_url: OLD PATH WAS",x[2],"NEW PATH",n
                x[2] = n
                n = urllib.quote(x[3])
                if DEBUG:
                    print >>sys.stderr,"videoplay: play_url: OLD QUERY WAS",x[3],"NEW PATH",n
                x[3] = n
                url = urlparse.urlunsplit(x)
            elif url[0] != '"' and url[0] != "'":
                # to prevent shell escape problems
                # TODO: handle this case in escape_path() that now just covers spaces
                url = "'"+url+"'" 

        (prefix,ext) = os.path.splitext(dest)
        [mimetype,cmd] = self.get_video_player(ext,url)
        
        if DEBUG:
            print >>sys.stderr,"videoplay: play_url: cmd is",cmd
        
        self.launch_video_player(cmd)


    def play_stream(self,streaminfo):
        if DEBUG:
            print >>sys.stderr,"videoplay: play_stream"

        self.determine_playbackmode()

        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            if USE_VLC_RAW_INTERFACE:
                # Play using direct callbacks from the VLC C-code
                self.launch_video_player(None,streaminfo=streaminfo)
            else:
                # Play via internal HTTP server
                self.videohttpserv.set_inputstream(streaminfo,'/')
                url = self.create_url(self.videohttpserv,'/')

                self.launch_video_player(url,streaminfo=streaminfo)
        else:
            # External player, play stream via internal HTTP server
            path = '/'
            self.videohttpserv.set_inputstream(streaminfo,path)
            url = self.create_url(self.videohttpserv,path)

            [mimetype,cmd] = self.get_video_player(None,url,mimetype=streaminfo['mimetype'])
            self.launch_video_player(cmd)


    def launch_video_player(self,cmd,streaminfo=None):
        if self.playbackmode == PLAYBACKMODE_INTERNAL:

            if cmd is not None:
                # Play URL from network or disk
                self.videoframe.get_videopanel().Load(cmd,streaminfo=streaminfo)
            else:
                # Play using direct callbacks from the VLC C-code
                self.videoframe.get_videopanel().Load(cmd,streaminfo=streaminfo)

            self.videoframe.show_videoframe()
            self.videoframe.get_videopanel().StartPlay()
        else:
            # Launch an external player
            # Play URL from network or disk
            self.exec_video_player(cmd)


    def stop_playback(self,reset=False):
        """ Stop playback in current video window """
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe is not None:
            self.videoframe.get_videopanel().Stop()
            if reset:
                self.videoframe.get_videopanel().Reset()

    def show_loading(self):
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe is not None:
            self.videoframe.get_videopanel().ShowLoading()

    def close(self):
        """ Stop playback and close current video window """
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe is not None:
            self.videoframe.hide_videoframe()


    def play(self,ds):
        """ Used by Tribler Main """
        self.determine_playbackmode()
        
        d = ds.get_download()
        tdef = d.get_def()
        videofiles = d.get_dest_files(exts=videoextdefaults)
        
        if len(videofiles) == 0:
            print >>sys.stderr,"videoplay: play: No video files found! Let user select"
            # Let user choose any file
            videofiles = d.get_dest_files(exts=None)
            
        print >>sys.stderr,"videoplay: play: videofiles",videofiles
            
        selectedinfilename = None
        selectedoutfilename= None
        if len(videofiles) > 1:
            infilenames = []
            for infilename,diskfilename in videofiles:
                infilenames.append(infilename)
            selectedinfilename = self.ask_user_to_select_video(infilenames)
            if selectedinfilename is None:
                print >>sys.stderr,"videoplay: play: User selected no video"
                return
            for infilename,diskfilename in videofiles:
                if infilename == selectedinfilename:
                    selectedoutfilename = diskfilename
        else:
            selectedinfilename = videofiles[0][0]
            selectedoutfilename = videofiles[0][1]

        complete = ds.get_progress() == 1.0 or ds.get_status() == DLSTATUS_SEEDING

        bitrate = tdef.get_bitrate(selectedinfilename)
        if bitrate is None and not complete:
            video_analyser_path = self.utility.config.Read('videoanalyserpath')
            if not os.access(video_analyser_path,os.F_OK):
                self.onError(self.utility.lang.get('videoanalysernotfound'),video_analyser_path,self.utility.lang.get('videoanalyserwhereset'))
                return

        # The VLC MediaControl API's playlist_add_item() doesn't accept unicode filenames.
        # So if the file to play is unicode we play it via HTTP. The alternative is to make
        # Tribler save the data in non-unicode filenames.
        #
        flag = self.playbackmode == PLAYBACKMODE_INTERNAL and not self.is_ascii_filename(selectedoutfilename)
        
        if complete:
            print >> sys.stderr, 'videoplay: play: complete'
            if flag:
                self.play_file_via_httpserv(selectedoutfilename)
            else:
                self.play_file(selectedoutfilename)
            
            self.manage_others_when_playing_from_file(d)
            # Fake it, to get DL status reporting for right Download
            self.set_vod_download(d)
        else:
            print >> sys.stderr, 'videoplay: play: not complete'
            self.play_vod(ds,selectedinfilename)


    def play_vod(self,ds,infilename):
        """ Called by GUI thread when clicking "Play ASAP" button """

        d = ds.get_download()
        tdef = d.get_def()
        # For multi-file torrent: when the user selects a different file, play that
        oldselectedfile = None
        if not tdef.get_live() and ds.is_vod() and tdef.is_multifile_torrent():
            oldselectedfiles = d.get_selected_files()
            oldselectedfile = oldselectedfiles[0] # Should be just one
        
        # 1. (Re)Start torrent in VOD mode
        switchfile = (oldselectedfile is not None and oldselectedfile != infilename) 

        print >> sys.stderr, ds.is_vod() , switchfile , tdef.get_live()
        if not ds.is_vod() or switchfile or tdef.get_live():

            
            if switchfile:
                if self.playbackmode == PLAYBACKMODE_INTERNAL:
                    self.videoframe.get_videopanel().Reset()
            
            #[proceed,othertorrentspolicy] = self.warn_user(ds,infilename)
            proceed = True
            othertorrentspolicy = OTHERTORRENTS_STOP_RESTART
            
            if not proceed:
                # User bailing out
                return

            if DEBUG:
                print >>sys.stderr,"videoplay: play_vod: Enabling VOD on torrent",`d.get_def().get_name()`

            self.manage_other_downloads(othertorrentspolicy,targetd = d)

            # Restart download
            d.set_video_event_callback(self.sesscb_vod_event_callback)
            d.set_video_events(self.get_supported_vod_events())
            if d.get_def().is_multifile_torrent():
                d.set_selected_files([infilename])
            print >>sys.stderr,"videoplay: play_vod: Restarting existing Download",`ds.get_download().get_def().get_infohash()`
            self.set_vod_download(d)
            d.restart()


    def manage_other_downloads(self,othertorrentspolicy, targetd = None):
        activetorrents = self.utility.session.get_downloads()
        
        if DEBUG:
            for d2 in activetorrents:
                print >>sys.stderr,"videoplay: other torrents: Currently active is",`d2.get_def().get_name()`

        # Filter out live torrents, they are always removed. They stay in
        # myPreferenceDB so can be restarted.
        newactivetorrents = []
        for d2 in activetorrents:
            if d2.get_def().get_live():
                self.utility.session.remove_download(d2)
                #d2.stop()
            else:
                newactivetorrents.append(d2)

        
        if othertorrentspolicy == OTHERTORRENTS_STOP or othertorrentspolicy == OTHERTORRENTS_STOP_RESTART:
            for d2 in newactivetorrents:
                # also stop targetd, we're restarting in VOD mode.
                d2.stop()
        elif targetd:
            targetd.stop()
            
        if othertorrentspolicy == OTHERTORRENTS_STOP_RESTART:
            if targetd in newactivetorrents:
                newactivetorrents.remove(targetd)
            # TODO: REACTIVATE TORRENTS WHEN DONE. 
            # ABCTorrentTemp.set_previously_active_torrents(newactivetorrents)
            self.set_vod_postponed_downloads(newactivetorrents)

    def manage_others_when_playing_from_file(self,targetd):
        """ When playing from file, make sure all other Downloads are no
        longer in VOD mode, so they won't interrupt the playback.
        """
        activetorrents = self.utility.session.get_downloads()
        for d in activetorrents:
            if d.get_mode() == DLMODE_VOD:
                if d.get_def().get_live():
                    #print >>sys.stderr,"videoplay: manage_when_file_play: Removing live",`d.get_def().get_name()`
                    self.utility.session.remove_download(d)
                else:
                    #print >>sys.stderr,"videoplay: manage_when_file_play: Restarting in NORMAL mode",`d.get_def().get_name()`
                    d.stop()
                    d.set_mode(DLMODE_NORMAL)
                    d.restart()


    def start_and_play(self,tdef,dscfg):
        """ Called by GUI thread when Tribler started with live or video torrent on cmdline """

        # ARNO50: > Preview1: TODO: make sure this works better when Download already existed.
        
        selectedinfilename = None
        if not tdef.get_live():
            videofiles = tdef.get_files(exts=videoextdefaults)
            if len(videofiles) == 1:
                selectedinfilename = videofiles[0]
            elif len(videofiles) > 1:
                selectedinfilename = self.ask_user_to_select_video(videofiles)

        if selectedinfilename or tdef.get_live():
            if tdef.is_multifile_torrent():
                dscfg.set_selected_files([selectedinfilename])

            othertorrentspolicy = OTHERTORRENTS_STOP_RESTART
            self.manage_other_downloads(othertorrentspolicy,targetd = None)

            # Restart download
            dscfg.set_video_event_callback(self.sesscb_vod_event_callback)
            dscfg.set_video_events(self.get_supported_vod_events())
            print >>sys.stderr,"videoplay: Starting new VOD/live Download",`tdef.get_name()`

            d = self.utility.session.start_download(tdef,dscfg)
            self.set_vod_download(d)
            return d
        else:
            return None
        
    
    def sesscb_vod_event_callback(self,d,event,params):
        """ Called by the Session when the content of the Download is ready
         
        Called by Session thread """
        
        print >>sys.stderr,"videoplay: sesscb_vod_event_callback called",currentThread().getName(),"###########################################################"
        wx.CallAfter(self.gui_vod_event_callback,d,event,params)

    def gui_vod_event_callback(self,d,event,params):
        """ Also called by SwarmPlayer """

        print >>sys.stderr,"videoplay: gui_vod_event:",event
        if event == VODEVENT_START:
            filename = params["filename"]
            mimetype = params["mimetype"]
            stream   = params["stream"]
            length   = params["length"]

            if filename:
                self.play_file(filename)
            else:
                blocksize = d.get_def().get_piece_length()
                
                # Estimate duration. Video player (e.g. VLC) often can't tell
                # when streaming.
                estduration = None
                if not d.get_def().get_live():
                    file = None
                    if d.get_def().is_multifile_torrent():
                        file = d.get_selected_files()[0]
                    bitrate = d.get_def().get_bitrate(file)
                    if bitrate is not None:
                        estduration = float(length) / float(bitrate)
                    
                streaminfo = {'mimetype':mimetype,'stream':stream,'length':length,'blocksize':blocksize,'estduration':estduration}
                self.play_stream(streaminfo)
                
        elif event == VODEVENT_PAUSE:
            if self.videoframe is not None: 
                self.videoframe.get_videopanel().PlayPause()
            self.set_player_status("Buffering...")
        elif event == VODEVENT_RESUME:
            if self.videoframe is not None:
                self.videoframe.get_videopanel().PlayPause()
            self.set_player_status("")

    def ask_user_to_select_video(self,videofiles):
        dlg = VideoChooser(self.videoframe.get_window(),self.utility,videofiles,title='Tribler',expl='Select which file to play')
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            index = dlg.getChosenIndex()
            filename = videofiles[index]
        else:
            filename = None
        dlg.Destroy()
        return filename

    def is_ascii_filename(self,filename):
        if isinstance(filename,str):
            return True
        try:
            filename.encode('ascii','strict')
            return True
        except:
            print_exc()
            return False

    def warn_user(self,ds,infilename):
        
        islive = ds.get_download().get_def().get_live()
        if islive and not self.other_downloads:
            # If it's the only download and live, don't warn.
            return
        
        dlg = VODWarningDialog(self.videoframe.get_window(),self.utility,ds,infilename,self.other_downloads,islive)
        result = dlg.ShowModal()
        othertorrentspolicy = dlg.get_othertorrents_policy()
        dlg.Destroy()
        return [result == wx.ID_OK,othertorrentspolicy]

    def create_url(self,videoserver,upath):
        schemeserv = 'http://127.0.0.1:'+str(videoserver.get_port())
        asciipath = unicode2str(upath)
        return schemeserv+urllib.quote(asciipath)



    def get_video_player(self,ext,videourl,mimetype=None):

        video_player_path = self.utility.config.Read('videoplayerpath')
        if DEBUG:
            print >>sys.stderr,"videoplay: Default player is",video_player_path

        if mimetype is None:
            if sys.platform == 'win32':
                # TODO: Use Python's mailcap facility on Linux to find player
                [mimetype,playcmd] = win32_retrieve_video_play_command(ext,videourl)
                if DEBUG:
                    print >>sys.stderr,"videoplay: Win32 reg said playcmd is",playcmd
                    
            if mimetype is None:
                if ext == '.avi':
                    mimetype = 'video/avi'
                elif ext == '.mpegts' or ext == '.ts':
                    mimetype = 'video/mp2t'
                else:
                    mimetype = 'video/mpeg'
        else:
            if sys.platform == 'win32':
                [mimetype,playcmd] = win32_retrieve_playcmd_from_mimetype(mimetype,videourl)

        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            print >>sys.stderr,"videoplay: using internal player"
            return [mimetype,videourl]
        elif self.playbackmode == PLAYBACKMODE_EXTERNAL_MIME and sys.platform == 'win32':
            if playcmd is not None:
                cmd = 'start /B "TriblerVideo" '+playcmd
                return [mimetype,cmd]

        if DEBUG:
            print >>sys.stderr,"videoplay: Defaulting to default player",video_player_path
        qprogpath = quote_program_path(video_player_path)
        #print >>sys.stderr,"videoplay: Defaulting to quoted prog",qprogpath
        if qprogpath is None:
            return [None,None]
        qvideourl = self.escape_path(videourl)
        playcmd = qprogpath+' '+qvideourl
        if sys.platform == 'win32':
            cmd = 'start /B "TriblerVideo" '+playcmd
        elif sys.platform == 'darwin':
            cmd = 'open -a '+playcmd
        else:
            cmd = playcmd
        print >>sys.stderr,"videoplay: using external user-defined player by executing ",cmd
        return [mimetype,cmd]



    def exec_video_player(self,cmd):
        if DEBUG:
            print >>sys.stderr,"videoplay: Command is @"+cmd+"@"
        # I get a weird problem on Linux. When doing a
        # os.popen2("vlc /tmp/file.wmv") I get the following error:
        #[00000259] main interface error: no suitable interface module
        #[00000001] main private error: interface "(null)" initialization failed
        #
        # The only thing that appears to work is
        # os.system("vlc /tmp/file.wmv")
        # but that halts Tribler, as it waits for the created shell to
        # finish. Hmmmm....
        #
        try:
            if sys.platform == 'win32':
                #os.system(cmd)
                (self.player_out,self.player_in) = os.popen2( cmd, 'b' )
            else:
                (self.player_out,self.player_in) = os.popen2( cmd, 'b' )
        except Exception, e:
            print_exc()
            self.onError(self.utility.lang.get('videoplayerstartfailure'),cmd,str(e.__class__)+':'+str(e))



    def escape_path(self,path):
        if path[0] != '"' and path[0] != "'" and path.find(' ') != -1:
            if sys.platform == 'win32':
                # Add double quotes
                path = "\""+path+"\""
            else:
                path = "\'"+path+"\'"
        return path


    def onError(self,action,value,errmsg=u''):
        self.onMessage(wx.ICON_ERROR,action,value,errmsg)

    def onWarning(self,action,value,errmsg=u''):
        self.onMessage(wx.ICON_INFORMATION,action,value,errmsg)

    def onMessage(self,icon,action,value,errmsg=u''):
        # Don't use language independence stuff, self.utility may not be
        # valid.
        msg = action
        msg += '\n'
        msg += value
        msg += '\n'
        msg += errmsg
        msg += '\n'
        dlg = wx.MessageDialog(None, msg, self.utility.lang.get('videoplayererrortitle'), wx.OK|icon)
        result = dlg.ShowModal()
        dlg.Destroy()

    def set_vod_postponed_downloads(self,dlist):
        self.vod_postponed_downloads = dlist
        
    def get_vod_postponed_downloads(self):
        return self.vod_postponed_downloads

    def set_vod_download(self,d):
        self.vod_download = d
        
    def get_vod_download(self):
        return self.vod_download

    #
    # Set information about video playback progress that is displayed
    # to the user.
    #
    def set_content_name(self,name):
        if self.videoframe is not None:
            self.videoframe.get_videopanel().SetContentName(name)

    def set_content_image(self,wximg):
        if self.videoframe is not None:
            self.videoframe.get_videopanel().SetContentImage(wximg)

    def set_player_status(self,msg):
        if self.videoframe is not None:
            self.videoframe.get_videopanel().SetPlayerStatus(msg)

    def set_player_status_and_progress(self,msg,pieces_complete):
        if self.videoframe is not None:
            self.videoframe.get_videopanel().UpdateStatus(msg,pieces_complete)
        
    def set_save_button(self,enable,savebutteneventhandler):
        if self.playbackmode == PLAYBACKMODE_INTERNAL and self.videoframe is not None:
            self.videoframe.get_videopanel().EnableSaveButton(enable,savebutteneventhandler)

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

    #def set_preferredplaybackmode(self,mode):
    #    This is a bit complex: If there is no int. player avail we change
    #    the VideoFrame to contain some minimal info. Would have to dynamically
    #    change that back if we allow dynamic switching of video player.
    #    self.preferredplaybackmode = mode

    #
    # Internal methods
    #
    def videohttpserver_error_callback(self,e,url):
        """ Called by HTTP serving thread """
        wx.CallAfter(self.videohttpserver_error_guicallback,e,url)
        
    def videohttpserver_error_guicallback(self,e,url):
        print >>sys.stderr,"videoplay: Video HTTP server reported error",str(e)
        # if e[0] == ECONNRESET and self.closeextplayercallback is not None:
        if self.closeextplayercallback is not None:
            self.closeextplayercallback()

    def videohttpserver_set_status_callback(self,status):
        """ Called by HTTP serving thread """
        wx.CallAfter(self.videohttpserver_set_status_guicallback,status)

    def videohttpserver_set_status_guicallback(self,status):
        self.videoframe.get_videopanel().SetPlayerStatus(status)
 



class VideoChooser(wx.Dialog):
    
    def __init__(self,parent,utility,filelist,title=None,expl=None):
        
        self.utility = utility
        self.filelist = []
        
        # Convert to Unicode for display
        for file in filelist:
            u = bin2unicode(file)
            self.filelist.append(u)

        if DEBUG:
            print >>sys.stderr,"VideoChooser: filelist",self.filelist
        
        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        if title is None:
            title = self.utility.lang.get('selectvideofiletitle')
        wx.Dialog.__init__(self,parent,-1,title,style=style)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        filebox = wx.BoxSizer(wx.VERTICAL)
        self.file_chooser=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(300, -1), self.filelist)
        self.file_chooser.SetSelection(0)
        
        if expl is None:
            self.utility.lang.get('selectvideofile')
        filebox.Add(wx.StaticText(self, -1, expl), 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        filebox.Add(self.file_chooser)
        sizer.Add(filebox, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        okbtn = wx.Button(self, wx.ID_OK, label=self.utility.lang.get('ok'), style = wx.BU_EXACTFIT)
        buttonbox.Add(okbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        cancelbtn = wx.Button(self, wx.ID_CANCEL, label=self.utility.lang.get('cancel'), style = wx.BU_EXACTFIT)
        buttonbox.Add(cancelbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        sizer.Add(buttonbox, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        self.SetSizerAndFit(sizer)

    def getChosenIndex(self):        
        return self.file_chooser.GetSelection()



class VODWarningDialog(wx.Dialog):
    
    def __init__(self, parent, utility, ds, infilename, other_downloads, islive):
        self.parent = parent
        self.utility = utility

        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        if islive:
            title = self.utility.lang.get('livewarntitle')
        else:
            title = self.utility.lang.get('vodwarntitle')
        
        wx.Dialog.__init__(self,parent,-1,title,style=style)

        if islive:
            msg = self.utility.lang.get('livewarngeneral')
        else:
            msg = self.utility.lang.get('vodwarngeneral')
        
        """
        if bitrate is None:
            msg += self.utility.lang.get('vodwarnbitrateunknown')
            msg += self.is_mov_file(videoinfo)
            msg += self.utility.lang.get('vodwarnconclusionno')
        elif bitrate > maxuploadrate and maxuploadrate != 0:
            s = self.utility.lang.get('vodwarnbitrateinsufficient') % (str(bitrate/1024),str(maxuploadrate)+" KB/s")
            msg += s
            msg += self.is_mov_file(videoinfo)
            msg += self.utility.lang.get('vodwarnconclusionno')
        elif bitrate > maxmeasureduploadrate and maxuploadrate == 0:
            s = self.utility.lang.get('vodwarnbitrateinsufficientmeasured') % (str(bitrate/1024),str(maxuploadrate)+" KB/s")
            msg += s
            msg += self.is_mov_file(videoinfo)
            msg += self.utility.lang.get('vodwarnconclusionno')
            
        else:
            if maxuploadrate == 0:
                rate = self.utility.lang.get('unlimited')
            else:
                rate = str(maxuploadrate)+" KB/s"
            s = self.utility.lang.get('vodwarnbitratesufficient') % (str(bitrate/1024),rate)
            msg += s
            extra = self.is_mov_file(videoinfo)
            if extra  == '':
                msg += self.utility.lang.get('vodwarnconclusionyes')
            else:
                msg += extra
                msg += self.utility.lang.get('vodwarnconclusionno')
        
        """
        sizer = wx.BoxSizer(wx.VERTICAL)
        text = wx.StaticText(self, -1, msg)
        text.Wrap(500)
        sizer.Add(text, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL|wx.EXPAND, 5)

        # 22/08/08 boudewijn: only show the selectbox when there are
        # torrents that are actively downloading
        if other_downloads:
            otherslist = [self.utility.lang.get('vodrestartothertorrents'),
                          self.utility.lang.get('vodstopothertorrents'),
                          self.utility.lang.get('vodleaveothertorrents')]

            othersbox = wx.BoxSizer(wx.VERTICAL)
            self.others_chooser=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), otherslist)
            self.others_chooser.SetSelection(OTHERTORRENTS_STOP_RESTART)

            othersbox.Add(wx.StaticText(self, -1, self.utility.lang.get('vodwhataboutothertorrentspolicy')), 1, wx.ALIGN_CENTER_VERTICAL)
            othersbox.Add(self.others_chooser)
            sizer.Add(othersbox, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        else:
            self.others_chooser = None

        sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('vodwarnprompt')), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        

        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        okbtn = wx.Button(self, wx.ID_OK, label=self.utility.lang.get('yes'), style = wx.BU_EXACTFIT)
        buttonbox.Add(okbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        cancelbtn = wx.Button(self, wx.ID_CANCEL, label=self.utility.lang.get('no'), style = wx.BU_EXACTFIT)
        buttonbox.Add(cancelbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        sizer.Add(buttonbox, 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        self.SetSizerAndFit(sizer)

    def get_othertorrents_policypolicy(self):
        if self.others_chooser:
            idx = self.others_chooser.GetSelection()
        else:
            idx = OTHERTORRENTS_STOP_RESTART
        if DEBUG:
            print >>sys.stderr,"videoplay: Other-torrents-policy is",idx
        return idx
    
    def is_mov_file(self,videoinfo):
        orig = videoinfo['inpath']
        (prefix,ext) = os.path.splitext(orig)
        low = ext.lower()
        if low == '.mov':
            return self.utility.lang.get('vodwarnmov')
        else:
            return ''
            

def parse_playtime_to_secs(hhmmss):
    if DEBUG:
        print >>sys.stderr,"videoplay: Playtime is",hhmmss
    r = re.compile("([0-9]+):*")
    occ = r.findall(hhmmss)
    t = None
    if len(occ) > 0:
        if len(occ) == 3:
            # hours as well
            t = int(occ[0])*3600 + int(occ[1])*60 + int(occ[2])
        elif len(occ) == 2:
            # minutes and seconds
            t = int(occ[0])*60 + int(occ[1])
        elif len(occ) == 1:
            # seconds
            t = int(occ[0])
    return t

def return_feasible_playback_modes(syspath):
    l = []
    try:
        import vlc

        if USE_VLC_RAW_INTERFACE:
            # check if the special raw interface is available
            if not inspect.ismethoddescriptor(vlc.MediaControl.set_raw_callbacks):
                raise Exception("Incorrect vlc plugin. This does not provide the set_raw_callbacks method")
        vlcpath = os.path.join(syspath,"vlc")
        if sys.platform == 'win32':
            if os.path.isdir(vlcpath):
                l.append(PLAYBACKMODE_INTERNAL)
        else:
            l.append(PLAYBACKMODE_INTERNAL)
    except Exception:
        print_exc()
    
    if sys.platform == 'win32':
        l.append(PLAYBACKMODE_EXTERNAL_MIME)
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    else:
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    return l

