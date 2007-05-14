# Written by Arno Bakker
# see LICENSE.txt for license information
import sys
import os
import wx
import re
import urllib
from threading import currentThread,Event
from traceback import print_exc,print_stack
import urlparse

from safeguiupdate import DelayedInvocation
from Utility.regchecker import Win32RegChecker
from Tribler.Video.__init__ import *
from Tribler.Video.VideoServer import VideoHTTPServer,MovieFileTransport,MovieTransportDecryptWrapper
from Tribler.Video.Progress import ProgressBar,BufferInfo, ProgressInf
from Tribler.unicode import unicode2str

# Filename extensions for video and audio files
EXTENSIONS = ['aac','asf','avi','dv','divx','flc','mpeg','mpeg4','mpg4','mp3','mp4','mpg','mkv','mov','ogm','qt','rm','swf','vob','wmv','wav']

DEBUG = False


PLAYBACKMODE_INTERNAL = 0
PLAYBACKMODE_EXTERNAL_DEFAULT = 1
PLAYBACKMODE_EXTERNAL_MIME = 2

OTHERTORRENTS_STOP_RESTART = 0
OTHERTORRENTS_STOP = 1
OTHERTORRENTS_CONTINUE = 2


class VideoPlayer:
    
    __single = None
    
    def __init__(self):
        if VideoPlayer.__single:
            raise RuntimeError, "VideoPlayer is singleton"
        VideoPlayer.__single = self
        self.extprogress = None
        
    def getInstance(*args, **kw):
        if VideoPlayer.__single is None:
            VideoPlayer(*args, **kw)
        return VideoPlayer.__single
    getInstance = staticmethod(getInstance)
        
    def register(self,utility):
        self.utility = utility
        
        videoserver = VideoHTTPServer.getInstance()
        videoserver.register(self.videoserver_error_callback)

        self.determine_playbackmode()

    def determine_playbackmode(self):
        playbackmode = self.utility.config.Read('videoplaybackmode', "int")
        feasible = return_feasible_playback_modes()
        if playbackmode in feasible:
            self.playbackmode = playbackmode
        else:
            self.playbackmode = feasible[0]

    def set_parentwindow(self,parentwindow):
        self.parentwindow = parentwindow

    def play(self,ABCTorrentTemp):
        self.determine_playbackmode()
        
        if self.is_video_torrent(ABCTorrentTemp):
            
            enc = stat(ABCTorrentTemp)
            videoinfo = self.select_video(ABCTorrentTemp,enc)
            if videoinfo is None:
                return # error already given

            bitrate = videoinfo[2]
            if bitrate is None:
                video_analyser_path = self.utility.config.Read('videoanalyserpath')
                if not os.access(video_analyser_path,os.F_OK):
                    self.onError(self.utility.lang.get('videoanalysernotfound'),video_analyser_path,self.utility.lang.get('videoanalyserwhereset'))
                    return

            # The VLC MediaControl API's playlist_add_item() doesn't accept unicode filenames.
            # So if the file to play is unicode we play it via HTTP. The alternative is to make
            # Tribler save the data in non-unicode filenames.
            #
            flag = self.playbackmode == PLAYBACKMODE_INTERNAL and not self.is_ascii_filename(videoinfo[3])
            
            if ABCTorrentTemp.status.completed:
                if enc or flag:
                    self.play_via_http(ABCTorrentTemp,videoinfo)
                else:
                    self.play_from_file(ABCTorrentTemp,videoinfo)
            else:
                self.play_vod_via_http(ABCTorrentTemp,videoinfo)
        else:
            self.onWarning(self.utility.lang.get('notvideotorrent'),ABCTorrentTemp.files.dest)
            if DEBUG:
                print >>sys.stderr,"videoplay: Not video torrent"


    def is_video_torrent(self,ABCTorrentTemp):
        filelist = find_video_on_disk(ABCTorrentTemp,stat(ABCTorrentTemp))
        if filelist is None or len(filelist) == 0:
            return False
        else:
            return True

    def play_via_http(self,ABCTorrentTemp,videoinfo):
        if DEBUG:
            print >>sys.stderr,"videoplay: Playing encrypted file via HTTP"

        videoserver = VideoHTTPServer.getInstance()
        enc = stat(ABCTorrentTemp)
        
        # If encoded the prefix is e.g. .mpg.enc and we want the .mpg
        dest = videoinfo[3]
        (prefix,ext) = os.path.splitext(dest)
        if enc and ext == '.enc':
            (prefix,ext) = os.path.splitext(prefix)

        videourl = self.create_url(videoserver,'/'+os.path.basename(prefix+ext))
        [mimetype,cmd] = self.get_video_player(ext,videourl)
        
        movietransport = MovieFileTransport(dest,mimetype,seek(ABCTorrentTemp))

        videoserver.set_movietransport(movietransport)
        self.launch_video_player(cmd)
        

    def play_from_file(self,ABCTorrentTemp,videoinfo):
        """ Play video file from disk """
        dest = videoinfo[3]
        if DEBUG:
            print >>sys.stderr,"videoplay: Playing file from disk",dest

        (prefix,ext) = os.path.splitext(dest)
        [mimetype,cmd] = self.get_video_player(ext,dest)
        
        if DEBUG:
            print >>sys.stderr,"videoplay: play_from_file: cmd is",cmd
        
        self.launch_video_player(cmd)


    def play_vod_via_http(self,ABCTorrentTemp,videoinfo):

        # For multi-file torrent: when the user selects a different file, play that
        oldvideoinfo = ABCTorrentTemp.get_videoinfo()
        
        # 1. (Re)Start torrent in VOD mode
        switchfile = oldvideoinfo is not None and oldvideoinfo[0] != videoinfo[0]
        if not ABCTorrentTemp.get_on_demand_download() or switchfile:
            
            if switchfile:
                if self.playbackmode == PLAYBACKMODE_INTERNAL:
                    self.parentwindow.reset_videopanel()
            
            [proceed,othertorrents] = self.warn_user(ABCTorrentTemp,videoinfo)
            if not proceed:
                # User bailing out
                return

            if DEBUG:
                print >>sys.stderr,"videoplay: Enabling VOD on torrent",ABCTorrentTemp

            progressinf = ProgressInf()
            activetorrents = self.utility.torrents["active"].keys()
            
            if DEBUG:
                for t in activetorrents:
                    print >>sys.stderr,"videoplay: other torrents: Currently active is",t.files.dest
            
            if othertorrents == OTHERTORRENTS_STOP or othertorrents == OTHERTORRENTS_STOP_RESTART:
                self.utility.actionhandler.procSTOP()
            else:
                self.utility.actionhandler.procSTOP([ABCTorrentTemp])
                
            if othertorrents == OTHERTORRENTS_STOP_RESTART:
                if ABCTorrentTemp in activetorrents:
                    activetorrents.remove(ABCTorrentTemp)
                ABCTorrentTemp.set_previously_active_torrents(activetorrents)
                
            ABCTorrentTemp.enable_on_demand_download()
            ABCTorrentTemp.set_videoinfo(videoinfo)
            ABCTorrentTemp.set_progressinf(progressinf)
            # The resume procedure does not start the BT1Download class right away,
            # it must wait for the hashchecks scheduled on the network thread to
            # finish.    
            #ABCTorrentTemp.set_vod_started_callback(self.vod_started)
            self.utility.actionhandler.procRESUME([ABCTorrentTemp])
            

    def vod_start_playing(self,ABCTorrentTemp): 
        """ Called by GUI thread """
        
        if DEBUG:
            print >>sys.stderr,"videoplay: VOD started"
            
        if currentThread().getName() != "MainThread":
            print >>sys.stderr,"videoplay: vod_play called by non-MainThread!",currentThread().getName()
            print_stack()
            
        progressinf = ABCTorrentTemp.get_progressinf()
        videoinfo = ABCTorrentTemp.get_videoinfo()
        
        # 2. Setup video source
        enc = stat(ABCTorrentTemp)
        dest = videoinfo[1]
        (prefix,ext) = os.path.splitext(dest)
        if enc and ext == '.enc':
            (prefix,ext) = os.path.splitext(prefix)
            
        videoserver = VideoHTTPServer.getInstance()
        videourl = self.create_url(videoserver,'/'+os.path.basename(prefix+ext))
        [mimetype,cmd] = self.get_video_player(ext,videourl)

        movietransport = ABCTorrentTemp.get_moviestreamtransport()
        movietransport.set_mimetype(mimetype)
        
        if seek(ABCTorrentTemp) is not None:
            mtwrap = MovieTransportDecryptWrapper(movietransport,seek(ABCTorrentTemp))
        else:
            mtwrap = movietransport

        videoserver.set_movietransport(mtwrap)
 
        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            self.parentwindow.invokeLater(self.swapin_videopanel_gui_callback,[cmd],{'play':True,'progressinf':progressinf})
        else:
            self.parentwindow.invokeLater(self.progress4ext_gui_callback,[progressinf,cmd])
 
    def swapin_videopanel_gui_callback(self,cmd,play=False,progressinf=None):
        """ Called by GUI thread """
        self.parentwindow.swapin_videopanel(cmd,play=play,progressinf=progressinf)
 
    def progress4ext_gui_callback(self,progressinf,cmd):
        """ Called by GUI thread """
        self.launch_video_player(cmd)
 
    def vod_stopped(self,ABCTorrentTemp):
        """ Called by GUI thread """
        if DEBUG:
            print >>sys.stderr,"videoplay: VOD stopped"
        
        if currentThread().getName() != "MainThread":
            print >>sys.stderr,"videoplay: vod_stopped called by nonMainThread!",currentThread().getName()
            print_stack()

        ABCTorrentTemp.disable_on_demand_download()
        
        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            self.parentwindow.swapout_videopanel()
        else:
            # TODO: Close separate progress window
            pass
 

    def vod_failed(self,ABCTorrentTemp):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"videoplay: VOD failed"
        self.parentwindow.invokeLater(self.vod_stopped,[ABCTorrentTemp])

    def vod_download_completed(self,ABCTorrentTemp):
        """ The video is in """

        if currentThread().getName() != "MainThread":
            print >>sys.stderr,"videoplay: vod_download_completed called by nonMainThread!",currentThread().getName()
            print_stack()

        ABCTorrentTemp.disable_on_demand_download()
        prevactivetorrents = ABCTorrentTemp.get_previously_active_torrents()
        if prevactivetorrents is not None:
            if DEBUG:
                for t in prevactivetorrents:
                    print >>sys.stderr,"videoplay: download_completed: Reactivating",t.files.dest
            self.utility.actionhandler.procRESUME(prevactivetorrents)


    def vod_back_to_standard_dlmode(self,ABCTorrentTemp):
        self.vod_download_completed(ABCTorrentTemp)
        self.vod_stopped(ABCTorrentTemp)
        self.utility.actionhandler.procSTOP([ABCTorrentTemp])
        self.utility.actionhandler.procRESUME([ABCTorrentTemp])


    def play_url(self,url):
        """ Play video file from disk """
        self.determine_playbackmode()
        
        t = urlparse.urlsplit(url)
        dest = t[2]
        if DEBUG:
            print >>sys.stderr,"videoplay: Playing file from url",url

        
        # VLC will play .flv files, but doesn't like the URLs that YouTube uses,
        # so quote them
        if self.playbackmode != PLAYBACKMODE_INTERNAL:
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

        (prefix,ext) = os.path.splitext(dest)
        [mimetype,cmd] = self.get_video_player(ext,url)
        
        if DEBUG:
            print >>sys.stderr,"videoplay: play_url: cmd is",cmd
        
        self.launch_video_player(cmd)



    def select_video(self,ABCTorrentTemp,enc=False):        
        fileindexlist = find_video_on_disk(ABCTorrentTemp,enc)
        if len(fileindexlist) == 0:
            self.onWarning(self.utility.lang.get('torrentcontainsnovideo'),ABCTorrentTemp.files.dest)
            if DEBUG:
                print >>sys.stderr,"videoplay: Torrent contains no video"
            return None
        elif len(fileindexlist) == 1:
            videoinfo = fileindexlist[0]
            if videoinfo[3] is None:
                self.onWarning(self.utility.lang.get('videoplaycontentnotfound'),videoinfo[1])
                return None
            return fileindexlist[0]
        else:
            return self.ask_user_to_select(fileindexlist)


    def get_video_player(self,ext,videourl):

        mimetype = 'video/mpeg'
        video_player_path = self.utility.config.Read('videoplayerpath')

        if DEBUG:
            print >>sys.stderr,"videoplay: Default player is",video_player_path

        if sys.platform == 'win32':
            # TODO: Use Python's mailcap facility on Linux to find player
            [mimetype,playcmd] = self.win32_retrieve_video_play_command(ext,videourl)
            if mimetype is None:
                mimetype = 'video/mpeg'
            if DEBUG:
                print >>sys.stderr,"videoplay: Win32 reg said playcmd is",playcmd

        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            return [mimetype,videourl]
        elif self.playbackmode == PLAYBACKMODE_EXTERNAL_MIME and sys.platform == 'win32':
            if playcmd is not None:
                cmd = 'start /B "TriblerVideo" '+playcmd
                return [mimetype,cmd]

        if DEBUG:
            print >>sys.stderr,"videoplay: Defaulting to default player",video_player_path
        qprogpath = self.quote_program_path(video_player_path)
        #print >>sys.stderr,"videoplay: Defaulting to quoted prog",qprogpath
        if qprogpath is None:
            return [None,None]
        qvideourl = self.escape_path(videourl)
        playcmd = qprogpath+' '+qvideourl
        if sys.platform == 'win32':
            cmd = 'start /B "TriblerVideo" '+playcmd
        else:
            cmd = playcmd
        return [mimetype,cmd]

            
    def win32_retrieve_video_play_command(self,ext,videourl):
        """ Use the specified extension of to find the player in the Windows registry to play the url (or file)"""
        registry = Win32RegChecker()
        
        if DEBUG:
            print >>sys.stderr,"videoplay: Looking for player for",unicode2str(videourl)
        if ext == '':
            return [None,None]
        
        contenttype = None
        winfiletype = registry.readRootKey(ext)
        if DEBUG:
            print >>sys.stderr,"videoplay: winfiletype is",winfiletype,type(winfiletype)
        if winfiletype is None or winfiletype == '':
            # Darn.... Try this: (VLC seems to be the one messing the registry up in the
            # first place)
            winfiletype = registry.readRootKey(ext,value_name="VLC.Backup")
            if winfiletype is None or winfiletype == '':
                return [None,None]
            # Get MIME type
        if DEBUG:
            print >>sys.stderr,"videoplay: Looking for player for ext",ext,"which is type",winfiletype

        contenttype = registry.readRootKey(ext,value_name="Content Type")
        
        playkey = winfiletype+"\shell\play\command"
        urlopen = registry.readRootKey(playkey)
        if urlopen is None:
            openkey = winfiletype+"\shell\open\command"
            urlopen = registry.readRootKey(openkey)
            if urlopen is None:
                return [None,None]

        # Default is e.g. "C:\Program Files\Windows Media Player\wmplayer.exe" /prefetch:7 /Play "%L"
        # Replace %L
        suo = urlopen.strip() # spaces
        idx = suo.find('%L')
        if idx == -1:
            # Hrrrr: Quicktime uses %1 instead of %L and doesn't seem to quote the program path
            idx = suo.find('%1')
            if idx == -1:
                return [None,None]
            else:
                replace = '%1'
                idx2 = suo.find('%2',idx)
                if idx2 != -1:
                    # Hmmm, a trailer, let's get rid of it
                    if suo[idx-1] == '"':
                        suo = suo[:idx+3] # quoted
                    else:
                        suo = suo[:idx+1]
        else:
            replace = '%L'
            
        # St*pid quicktime doesn't properly quote the program path, e.g.
        # C:\Program Files\Quicktime\bla.exe "%1" instead of
        # "C:\Program Files\Quicktime\bla.exe" "%1"
        if suo[0] != '"':    
            if idx > 0 and (len(suo)-1) >= idx+2 and suo[idx-1] == '"' and suo[idx+2]=='"':
                # %x is quoted
                end = max(0,idx-2)
            else:
                end = max(0,idx-1)
            # I assume everthing till end is the program path
            progpath = suo[0:end]
            qprogpath = self.quote_program_path(progpath)
            if qprogpath is None:
                return [None,None]
            suo = qprogpath+suo[end:]
            if DEBUG:
                print >>sys.stderr,"videoplay: new urlopen is",suo
        return [contenttype,suo.replace(replace,videourl)]

    def quote_program_path(self,progpath):
        idx = progpath.find(' ')
        if idx != -1:
            # Contains spaces, should quote if it's really path
            if not os.access(progpath,os.R_OK):
                if DEBUG:
                    print >>sys.stderr,"videoplay: Could not find assumed progpath",progpath
                return None
            return '"'+progpath+'"'
        else:
            return progpath

    def launch_video_player(self,cmd):
        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            self.parentwindow.swapin_videopanel(cmd)
        else:
            self.exec_video_player(cmd)

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
            print_exc(file=sys.stderr)
            self.onError(self.utility.lang.get('videoplayerstartfailure'),cmd,str(self.error.__class__)+':'+str(self.error))



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

    def ask_user_to_select(self,fileindexlist):
        """ Returns an [index,filename] pair """
        filelist = []
        
        for i in range(len(fileindexlist)):
            videoinfo = fileindexlist[i]
            if videoinfo[3] is not None:
                filelist.append(fileindexlist[i][1])
            
        if len(filelist) == 0:
            self.onWarning(self.utility.lang.get('videoplaycontentnotfound'),videoinfo[1])
            return None
            
            
        dlg = VideoChooser(self.parentwindow,self.utility,filelist)
        result = dlg.ShowModal()
        index = None
        if result == wx.ID_OK:
            index = dlg.getChosenIndex()
        dlg.Destroy()
        
        return fileindexlist[index] 


    def warn_user(self,ABCTorrentTemp,videoinfo):
        dlg = VODWarningDialog(self.parentwindow,self.utility,videoinfo)
        result = dlg.ShowModal()
        othertorrents = dlg.get_othertorrents()
        dlg.Destroy()
        return [result == wx.ID_OK,othertorrents]


    def videoserver_error_callback(self,e,url):
        """ Called by HTTP serving thread """
        self.parentwindow.invokeLater(self.videoserver_error_guicallback,[e,url])
        
    def videoserver_error_guicallback(self,e,url):
        print >>sys.stderr,"videoplay: Video server reported error",str(e)
        #self.onError(self.utility.lang.get('videoserverservefailure')+self.utility.lang.get('videoserverservefailureadvice'),url,str(e.__class__)+':'+str(e))


    def create_url(self,videoserver,upath):
        schemeserv = 'http://127.0.0.1:'+str(videoserver.port)
        asciipath = unicode2str(upath)
        return schemeserv+urllib.quote(asciipath)

    def is_ascii_filename(self,filename):
        if isinstance(filename,str):
            return True
        try:
            filename.encode('ascii','strict')
            return True
        except:
            print_exc(file=sys.stderr)
            return False

class VideoChooser(wx.Dialog):
    
    def __init__(self,parent,utility,filelist):
        
        self.utility = utility
        self.filelist = filelist

        if DEBUG:
            print >>sys.stderr,"VideoChooser: filelist",self.filelist
        
        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        title = self.utility.lang.get('selectvideofiletitle')
        wx.Dialog.__init__(self,parent,-1,title,style=style)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        filebox = wx.BoxSizer(wx.VERTICAL)
        self.file_chooser=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), self.filelist)
        self.file_chooser.SetSelection(0)

        filebox.Add(wx.StaticText(self, -1, self.utility.lang.get('selectvideofile')), 1, wx.ALIGN_CENTER_VERTICAL)
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
    
    def __init__(self, parent, utility, videoinfo):
        self.parent = parent
        self.utility = utility

        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        title = self.utility.lang.get('vodwarntitle')
        wx.Dialog.__init__(self,parent,-1,title,style=style)

        maxuploadrate = self.utility.config.Read('maxuploadrate', 'int')
        
        bitrate = videoinfo[2]
        msg = self.utility.lang.get('vodwarngeneral')
        if bitrate is None:
            msg += self.utility.lang.get('vodwarnbitrateunknown')
            msg += self.utility.lang.get('vodwarnconclusionno')
        elif bitrate > maxuploadrate and maxuploadrate != 0:
            s = self.utility.lang.get('vodwarnbitrateinsufficient') % (str(bitrate/1024),str(maxuploadrate)+" KB/s")
            msg += s
            msg += self.utility.lang.get('vodwarnconclusionno')
        else:
            if maxuploadrate == 0:
                rate = self.utility.lang.get('unlimited')
            else:
                rate = str(maxuploadrate)+" KB/s"
            s = self.utility.lang.get('vodwarnbitratesufficient') % (str(bitrate/1024),rate)
            msg += s
            msg += self.utility.lang.get('vodwarnconclusionyes')
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        text = wx.StaticText(self, -1, msg)
        text.Wrap(500)
        sizer.Add(text, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL|wx.EXPAND, 5)

        self.otherslist = [self.utility.lang.get('vodrestartothertorrents'),
                           self.utility.lang.get('vodstopothertorrents'),
                           self.utility.lang.get('vodleaveothertorrents')]

        othersbox = wx.BoxSizer(wx.VERTICAL)
        self.others_chooser=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), self.otherslist)
        
        # Be smart: if 
        if bitrate is None or (bitrate > maxuploadrate and maxuploadrate != 0):
            self.others_chooser.SetSelection(OTHERTORRENTS_STOP_RESTART)
        else:
            self.others_chooser.SetSelection(OTHERTORRENTS_CONTINUE)
            
        othersbox.Add(wx.StaticText(self, -1, self.utility.lang.get('vodwhataboutothertorrents')), 1, wx.ALIGN_CENTER_VERTICAL)
        othersbox.Add(self.others_chooser)
        sizer.Add(othersbox, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('vodwarnprompt')), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        

        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        okbtn = wx.Button(self, wx.ID_OK, label=self.utility.lang.get('yes'), style = wx.BU_EXACTFIT)
        buttonbox.Add(okbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        cancelbtn = wx.Button(self, wx.ID_CANCEL, label=self.utility.lang.get('no'), style = wx.BU_EXACTFIT)
        buttonbox.Add(cancelbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        sizer.Add(buttonbox, 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        self.SetSizerAndFit(sizer)

    def get_othertorrents(self):
        idx = self.others_chooser.GetSelection()
        if DEBUG:
            print >>sys.stderr,"videoplay: Other-torrents-policy is",idx
        return idx


        
def is_movie(filename,enc=False):
    # filter movies
    movie_extensions = [".%s" % e for e in EXTENSIONS]

    low = filename.lower()
    for ext in movie_extensions:
        if low.endswith( ext ) or (enc and low.endswith(ext+'.enc')):
            return True
    else:
        return False


def find_video_on_disk(ABCTorrentTemp,enc=False):
    """ Returns four tuple [index,printname,bitrate,filenameasondisk] of the video files 
    found on the local disk 
    """
    # TODO: let user select if multiple
    
    metainfo = ABCTorrentTemp.metainfo
    info = metainfo['info']

    fileindexlist = []
    if 'name' in info:
        if is_movie(info['name'],enc):
            bitrate = None
            try:
                playtime = None
                if info.has_key('playtime'):
                    playtime = parse_playtime_to_secs(info['playtime'])
                elif 'playtime' in metainfo: # HACK: encode playtime in non-info part of existing torrent
                    playtime = parse_playtime_to_secs(metainfo['playtime'])
                """
                elif 'azureus_properties' in metainfo:
                    if 'Speed Bps' in metainfo['azureus_properties']:
                        bitrate = float(metainfo['azureus_properties']['Speed Bps'])/8.0
                        playtime = file_length / bitrate
                """
                if playtime is not None:
                    bitrate = info['length']/playtime
            except:
                print_exc(file=sys.stderr)

            fileindexlist.append([-1,info['name'],bitrate,ABCTorrentTemp.files.dest])

    if 'files' in info:
        for i in range(len(info['files'])):
            x = info['files'][i]
            if is_movie(x['path'][-1],enc):
                
                intorrentpath = ''
                for elem in x['path']:
                    intorrentpath = os.path.join(intorrentpath,elem)
                bitrate = None
                try:
                    playtime = None
                    if x.has_key('playtime'):
                        playtime = parse_playtime_to_secs(x['playtime'])
                    elif 'playtime' in metainfo: # HACK: encode playtime in non-info part of existing torrent
                        playtime = parse_playtime_to_secs(metainfo['playtime'])
                        
                    if playtime is not None:
                        bitrate = x['length']/playtime
                except:
                    print_exc(file=sys.stderr)
                fileindexlist.append([i,intorrentpath,bitrate,ABCTorrentTemp.files.getSingleFileDest(index=i)])
    return fileindexlist

## TEMP REMOVE
def is_video_torrent(metainfo):
    return False

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

def return_feasible_playback_modes():
    l = []
    try:
        import vlc
        l.append(PLAYBACKMODE_INTERNAL)
    except ImportError:
        pass
    
    if sys.platform == 'win32':
        l.append(PLAYBACKMODE_EXTERNAL_MIME)
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    else:
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    return l

