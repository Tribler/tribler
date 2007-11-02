#!/usr/bin/python
# Written by Arno Bakker, Choopan RATTANAPOKA, Jie Yang
# see LICENSE.txt for license information

# Arno: M2Crypto overrides the method for https:// in the
# standard Python libraries. This causes msnlib to fail and makes Tribler
# freakout when "http://www.tribler.org/version" is redirected to
# "https://www.tribler.org/version/" (which happened during our website
# changeover) Until M2Crypto 0.16 is patched I'll restore the method to the
# original, as follows.
#
# This must be done in the first python file that is started.
#
import os
import sys
import time
import commands
from threading import enumerate

if sys.platform == "darwin":
    # on Mac, we can only load VLC/OpenSSL libraries
    # relative to the location of tribler.py
    os.chdir(os.path.abspath(os.path.dirname(sys.argv[0])))
import wx
from wx import xrc
#import hotshot

from triblerAPI import *

from Tribler.Video.VideoServer import VideoHTTPServer
from Tribler.Video.VideoPlayer import VideoPlayer
from Utility.utility import Utility
from Tribler.Video.EmbeddedPlayer import VideoFrame
from Tribler.API.RateManager import UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager

ALLOW_MULTIPLE = False

RATELIMITADSL = False


class ABCFrame(VideoFrame):

    def __init__(self,parent):
        VideoFrame.__init__(self,parent)
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
    
    def OnCloseWindow(self, event = None):
        if event is not None:
            nr = event.GetEventType()
            lookup = { wx.EVT_CLOSE.evtType[0]: "EVT_CLOSE", wx.EVT_QUERY_END_SESSION.evtType[0]: "EVT_QUERY_END_SESSION", wx.EVT_END_SESSION.evtType[0]: "EVT_END_SESSION" }
            if nr in lookup: nr = lookup[nr]
            print "Closing due to event ",nr
            print >>sys.stderr,"Closing due to event ",nr
            event.Skip()
        else:
            print "Closing untriggered by event"
    
        ts = enumerate()
        for t in ts:
            print >>sys.stderr,"Thread still running",t.getName(),"daemon",t.isDaemon()
        

class ABCApp(wx.App):
    def __init__(self, x, params, single_instance_checker, abcpath):
        self.params = params
        self.single_instance_checker = single_instance_checker
        self.abcpath = abcpath
        self.error = None
        wx.App.__init__(self, x)
        
    def OnInit(self):
        try:
            self.utility = Utility(self.abcpath)
            self.utility.app = self
            print self.utility.lang.get('build')
            
            
            self.videoFrame = ABCFrame(self)
            
            self.videoserv = VideoHTTPServer.getInstance() # create
            self.videoserv.background_serve()
            
            self.s = Session()

            if RATELIMITADSL:
                self.count = 0
                self.r = UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager()
                self.r.set_global_max_speed(DOWNLOAD,400)
                self.r.set_global_max_speed(UPLOAD,90)
                self.s.set_download_states_callback(self.ratelimit_callback,getpeerlist=False)
            
            if self.params[0] != "":
                torrentfilename = self.params[0]
            else:
                print >>sys.stderr,"main: No torrent file on cmd line"
                self.OnExit()
                return False

            tdef = TorrentDef.load(torrentfilename)
            videofiles = tdef.get_video_files()
            if len(videofiles) > 1:
                raise ValueError("Torrent contains multiple video files, pick manually")
            print >>sys.stderr,"main: Found video file",videofiles
            
            dcfg = DownloadStartupConfig()
            dcfg.set_video_on_demand(self.vod_ready_callback)
            dcfg.set_selected_files(videofiles)
            dcfg.set_max_conns_to_initiate(300)
            dcfg.set_max_conns(300)
            
            d = self.s.start_download(tdef,dcfg)
            d.set_state_callback(self.state_callback,1)

            self.videoplay = VideoPlayer.getInstance()
            self.videoplay.register(self.utility)
            self.videoplay.set_parentwindow(self.videoFrame)
            
            self.Bind(wx.EVT_CLOSE, self.videoFrame.OnCloseWindow)
            self.Bind(wx.EVT_QUERY_END_SESSION, self.videoFrame.OnCloseWindow)
            self.Bind(wx.EVT_END_SESSION, self.videoFrame.OnCloseWindow)

            self.videoFrame.Show(True)
        except Exception,e:
            print_exc()
            if self.s is not None:
                self.s.shutdown()
            return False
        return True

    def OnExit(self):
        print >>sys.stderr,"ONEXIT"
        self.s.shutdown()
        
        
        ###time.sleep(5) # TODO: make network thread non-daemon which MainThread has to end.
        
        if not ALLOW_MULTIPLE:
            del self.single_instance_checker
        ## TODO ClientPassParam("Close Connection")
        return 0


    def state_callback(self,ds):
        """ Called by Session thread """
        print >>sys.stderr,"main: Stats",dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error()
        logmsgs = ds.get_log_messages()
        if len(logmsgs) > 0:
            print >>sys.stderr,"main: Log",logmsgs[0]
        progress = ds.get_vod_prebuffering_progress()
        playable = ds.get_vod_playable()
        t = ds.get_vod_playable_after()
        print >>sys.stderr,"main: After is",t
        if t > float(2 ** 30):
            intime = "inf"
        elif t == 0.0:
            intime = "now"
        else:
            h, t = divmod(t, 60.0*60.0)
            m, s = divmod(t, 60.0)
            if h == 0.0:
                if m == 0.0:
                    intime = "%ds" % (s)
                else:
                    intime = "%dm:%02ds" % (m,s)
            else:
                intime = "%dh:%02dm:%02ds" % (h,m,s)
                
        #print >>sys.stderr,"main: VODStats",progress,playable

        if progress != 1.0:
            pstr = str(int(progress*100))
            msg = "Prebuffering "+pstr+"% done, eta "+intime
        elif playable:
            msg = "Starting playback..."
            print_stack()
        else:
            msg = "Waiting for sufficient download speed... "+intime
        self.videoFrame.set_player_status(msg)
        
        
        return (1.0,False)
    
    def vod_ready_callback(self,d,mimetype,stream,filename):
        """ Called by Session thread """
        print >>sys.stderr,"main: VOD ready callback called",currentThread().getName(),"###########################################################",mimetype
    
        if filename:
            func = lambda:self.play_from_file(filename)
            wx.CallAfter(func)
        else:
            # HACK: TODO: make to work with file-like interface
            videoserv = VideoHTTPServer.getInstance()
            videoserv.set_movietransport(stream.mt)
            wx.CallAfter(self.play_from_stream)
        
    def play_from_stream(self):
        """ Called by MainThread """
        print >>sys.stderr,"main: Playing from stream"
        self.videoplay.play_url('http://127.0.0.1:6880/')
    
    def play_from_file(self,filename):
        """ Called by MainThread """
        print >>sys.stderr,"main: Playing from file",filename
        self.videoplay.play_url(filename)

    def ratelimit_callback(self,dslist):
        adjustspeeds = False
        if self.count % 4 == 0:
            adjustspeeds = True
        self.count += 1
        
        if not adjustspeeds:
            return (1.0,False)
        
        for ds in dslist:
            d = ds.get_download()
            complete = ds.get_pieces_complete()
            print >>sys.stderr,"main: Pieces completed",`d.get_def().get_name()`,"len",len(complete)
            
            if adjustspeeds:
                self.r.add_downloadstate(ds)
            
        if adjustspeeds:
            self.r.adjust_speeds()
        return (1.0,False)


    
class DummySingleInstanceChecker:
    
    def __init__(self,basename):
        pass

    def IsAnotherRunning(self):
        "Uses pgrep to find other tribler.py processes"
        # If no pgrep available, it will always start tribler
        progressInfo = commands.getoutput('pgrep -fl tribler.py | grep -v pgrep')
        numProcesses = len(progressInfo.split('\n'))
        if DEBUG:
            print 'ProgressInfo: %s, num: %d' % (progressInfo, numProcesses)
        return numProcesses > 1
                
        
##############################################################
#
# Main Program Start Here
#
##############################################################
def run(params = None):
    if params is None:
        params = [""]
    
    if len(sys.argv) > 1:
        params = sys.argv[1:]
    
    # Create single instance semaphore
    # Arno: On Linux and wxPython-2.8.1.1 the SingleInstanceChecker appears
    # to mess up stderr, i.e., I get IOErrors when writing to it via print_exc()
    #
    # TEMPORARILY DISABLED on Linux
    if sys.platform != 'linux2':
        single_instance_checker = wx.SingleInstanceChecker("tribler-" + wx.GetUserId())
    else:
        single_instance_checker = DummySingleInstanceChecker("tribler-")

    #print "[StartUpDebug]---------------- 1", time()-start_time
    if not ALLOW_MULTIPLE and single_instance_checker.IsAnotherRunning():
        #Send  torrent info to abc single instance
        ## TODO ClientPassParam(params[0])
        #print "[StartUpDebug]---------------- 2", time()-start_time
        pass
    else:
        abcpath = os.path.abspath(os.path.dirname(sys.argv[0]))
        # Arno: don't chdir to allow testing as other user from other dir.
        os.chdir(abcpath) # TODO: comment out as soon as all hidden BSDDB create things are worked out.

        # Launch first abc single instance
        app = ABCApp(0, params, single_instance_checker, abcpath)
        app.MainLoop()

if __name__ == '__main__':
    run()

