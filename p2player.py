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

ALLOW_MULTIPLE = False



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
            
            from Tribler.Video.EmbeddedPlayer import VideoFrame
            self.videoFrame = VideoFrame(self)
            
            self.videoserv = VideoHTTPServer.getInstance() # create
            self.videoserv.background_serve()
            
            self.s = Session()
            
            if sys.platform == 'win32':
                tdef = TorrentDef.load('bla.torrent')
            else:
                tdef = TorrentDef.load('/tmp/bla.torrent')
            dcfg = DownloadStartupConfig()
            dcfg.set_video_on_demand(self.vod_ready_callback)
            d = self.s.start_download(tdef,dcfg)
            ##d.set_state_callback(self.state_callback,1)

            self.videoplay = VideoPlayer.getInstance()
            self.videoplay.register(self.utility)
            self.videoplay.set_parentwindow(self.videoFrame)
            

            self.videoFrame.Show(True)
        except Exception,e:
            print_exc()
        return True

    def OnExit(self):
        
        self.torrentfeed.shutdown()
        mainlineDHT.deinit()
        
        if not ALLOW_MULTIPLE:
            del self.single_instance_checker
        ClientPassParam("Close Connection")
        return 0



    def state_callback(self,d,ds):
        """ Called by Session thread """
        print >>sys.stderr,"main: Stats",dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error()
    
    def vod_ready_callback(self,mimetype,stream):
        """ Called by Session thread """
        print >>sys.stderr,"main: VOD ready callback called",currentThread().getName(),"###########################################################",mimetype
    
        """
        f = open("video.avi","wb")
        while True:
            data = stream.read()
            print >>sys.stderr,"main: VOD ready callback: reading",type(data)
            print >>sys.stderr,"main: VOD ready callback: reading",len(data)
            if len(data) == 0:
                break
            f.write(data)
        f.close()
        stream.close()
        """
    
        # HACK: TODO: make to work with file-like interface
        videoserv = VideoHTTPServer.getInstance()
        videoserv.set_movietransport(stream.mt)


        wx.CallAfter(self.harry)
        
    def harry(self):
        self.videoplay.play_url('http://127.0.0.1:6880/')
    
    
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
        ClientPassParam(params[0])
        #print "[StartUpDebug]---------------- 2", time()-start_time
    else:
        print "NOT OTHER"
        abcpath = os.path.abspath(os.path.dirname(sys.argv[0]))
        # Arno: don't chdir to allow testing as other user from other dir.
        #os.chdir(abcpath)

        # Launch first abc single instance
        app = ABCApp(0, params, single_instance_checker, abcpath)
        app.MainLoop()

if __name__ == '__main__':
    run()

