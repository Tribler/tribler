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

from Tribler.Video.__init__ import *
from Tribler.Video.VideoServer import VideoHTTPServer
from Tribler.Video.Progress import ProgressBar,BufferInfo, ProgressInf
from Tribler.Core.Utilities.unicode import unicode2str,bin2unicode
from utils import win32_retrieve_video_play_command,quote_program_path

DEBUG = True

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
        self.parentwindow = None
        self.extprogress = None
        self.contentname = None
        
    def getInstance(*args, **kw):
        if VideoPlayer.__single is None:
            VideoPlayer(*args, **kw)
        return VideoPlayer.__single
    getInstance = staticmethod(getInstance)
        
    def register(self,utility):
        
        self.utility = utility # TEMPARNO: make sure only used for language strings

        self.determine_playbackmode()

    def set_content_name(self,name):
        self.contentname = name
        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            self.parentwindow.set_content_name(self.contentname)

    def set_content_image(self,wximg):
        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            self.parentwindow.set_content_image(wximg)

    def determine_playbackmode(self):
        playbackmode = PLAYBACKMODE_INTERNAL # self.utility.config.Read('videoplaybackmode', "int")
        feasible = return_feasible_playback_modes(self.utility.getPath())
        if playbackmode in feasible:
            self.playbackmode = playbackmode
        else:
            self.playbackmode = feasible[0]
        #print >>sys.stderr,"videoplay: playback mode is %d wanted %d" % (self.playbackmode,playbackmode)

        ###self.playbackmode = PLAYBACKMODE_EXTERNAL_MIME

    def set_parentwindow(self,parentwindow):
        self.parentwindow = parentwindow


   ##  def play_from_file(self,videoinfo):
##         """ Play video file from disk """
##         dest = videoinfo['outpath']
##         if DEBUG:
##             print >>sys.stderr,"videoplay: Playing file from disk",dest

##         (prefix,ext) = os.path.splitext(dest)
##         [mimetype,cmd] = self.get_video_player(ext,dest)
        
##         if DEBUG:
##             print >>sys.stderr,"videoplay: play_from_file: cmd is",cmd
        
##         self.launch_video_player(cmd)

 
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
 

    def play_url(self,url):
        """ Play video file from disk """
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


    def stop_playback(self):
        if self.playbackmode == PLAYBACKMODE_INTERNAL:
            self.parentwindow.stop_playback()


    def get_video_player(self,ext,videourl):

        mimetype = None
        video_player_path = self.utility.config.Read('videoplayerpath')

        if DEBUG:
            print >>sys.stderr,"videoplay: Default player is",video_player_path

        if sys.platform == 'win32':
            # TODO: Use Python's mailcap facility on Linux to find player
            [mimetype,playcmd] = win32_retrieve_video_play_command(ext,videourl)
            if DEBUG:
                print >>sys.stderr,"videoplay: Win32 reg said playcmd is",playcmd
                
        if mimetype is None:
            if ext == '.avi':
                mimetype = 'video/avi'
            elif ext == '.mpegts':
                mimetype = 'video/mp2t'
            else:
                mimetype = 'video/mpeg'

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

    def ask_user_to_select(self,fileindexlist):
        """ Returns an [index,filename] pair """
        filelist = []
        
        for i in range(len(fileindexlist)):
            videoinfo = fileindexlist[i]
            if videoinfo['outpath'] is not None:
                filelist.append(videoinfo['inpath'])
            
        if len(filelist) == 0:
            self.onWarning(self.utility.lang.get('videoplaycontentnotfound'),videoinfo['inpath'])
            return None
            
            
        dlg = VideoChooser(self.parentwindow,self.utility,filelist)
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            index = dlg.getChosenIndex()
        dlg.Destroy()
        
        if result == wx.ID_OK:
            return fileindexlist[index] 
        else:
            return None


    def warn_user(self,ABCTorrentTemp,videoinfo):
        dlg = VODWarningDialog(self.parentwindow,self.utility,videoinfo)
        result = dlg.ShowModal()
        othertorrents = dlg.get_othertorrents()
        dlg.Destroy()
        return [result == wx.ID_OK,othertorrents]

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
    
    def __init__(self, parent, utility, videoinfo):
        self.parent = parent
        self.utility = utility

        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        title = self.utility.lang.get('vodwarntitle')
        wx.Dialog.__init__(self,parent,-1,title,style=style)

        maxuploadrate = self.utility.config.Read('maxuploadrate', 'int')
        maxmeasureduploadrate = self.utility.queue.getMaxMeasuredUploadRate()
        
        bitrate = videoinfo['bitrate']
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
        vlcpath = os.path.join(syspath,"vlc")
        if sys.platform == 'win32':
            if os.path.isdir(vlcpath):
                l.append(PLAYBACKMODE_INTERNAL)
        else:
            l.append(PLAYBACKMODE_INTERNAL)
    except Exception:
        #print_exc(file=sys.stderr)
        pass
    
    if sys.platform == 'win32':
        l.append(PLAYBACKMODE_EXTERNAL_MIME)
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    else:
        l.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
    return l

