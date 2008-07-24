 # Written by Arno Bakker, Choopan RATTANAPOKA, Jie Yang
# see LICENSE.txt for license information
#

import os
import sys
import time
import urllib2
from threading import Timer
from traceback import print_exc

if sys.platform == "darwin":
    # on Mac, we can only load VLC/OpenSSL libraries
    # relative to the location of tribler.py
    os.chdir(os.path.abspath(os.path.dirname(sys.argv[0])))
try:
    import wxversion
    wxversion.select('2.8')
except:
    pass
import wx

from Tribler.Video.VLCWrapper import *
from Tribler.Player.systray import PlayerTaskBarIcon

DEBUG = True

class PlayerFrame(wx.Frame):

    def __init__(self,parent):
        wx.Frame.__init__(self, None, -1, 'vlcswitchtest', size=(800,520))
        
        self.parent = parent
        self.vlcwin = VLCLogoWindow(self,parent.vlcwrap,None)
        
        mainbox = wx.BoxSizer(wx.VERTICAL)
        mainbox.Add(self.vlcwin, 1, wx.EXPAND, 1)
        self.SetSizerAndFit(mainbox)
        
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
    
    def OnCloseWindow(self, event = None):

        print >>sys.stderr,"main: ON CLOSE WINDOW"
        if event is not None:
            nr = event.GetEventType()
            lookup = { wx.EVT_CLOSE.evtType[0]: "EVT_CLOSE", wx.EVT_QUERY_END_SESSION.evtType[0]: "EVT_QUERY_END_SESSION", wx.EVT_END_SESSION.evtType[0]: "EVT_END_SESSION" }
            if nr in lookup: 
                nr = lookup[nr]
            print >>sys.stderr,"main: Closing due to event ",nr
            event.Skip()
        else:
            print >>sys.stderr,"main: Closing untriggered by event"
        
        if self.parent is not None:
            self.parent.vlcwrap.stop()
            # VLC continues to draw to the window, so on X11 I get:
            #
            # X Error of failed request:  BadDrawable (invalid Pixmap or Window parameter)
            # Major opcode of failed request:  140 (XVideo)
            #
            # So a mechanism here to postpone the closing until the video
            # has actually stopped would be good. Poor man's mech = sleep:
            #time.sleep(.3)
            self.parent = None


class PlayerApp(wx.App):
    def __init__(self, x, installdir):
        self.installdir = installdir
        wx.App.__init__(self, x)
        
    def OnInit(self):
        try:
            self.vlcwrap = VLCWrapper(self.installdir)
            
            self.videoFrame = PlayerFrame(self)
            self.Bind(wx.EVT_CLOSE, self.videoFrame.OnCloseWindow)
            self.Bind(wx.EVT_QUERY_END_SESSION, self.videoFrame.OnCloseWindow)
            self.Bind(wx.EVT_END_SESSION, self.videoFrame.OnCloseWindow)
            self.videoFrame.Show(True)

            # Need extra GUI item so the app won't shutdown when we close 
            # the main window.
            self.iconpath = os.path.join(os.getcwd(),'Tribler','Images','swarmplayer.ico')
            self.tbicon = PlayerTaskBarIcon(self,self.iconpath)

            wx.CallAfter(self.start0)
            
            return True
        except:
            print_exc()
            return False
        

    def OnExit(self):
        print >>sys.stderr,"main: ONEXIT"
        self.ExitMainLoop()

    def start0(self):
        """ Called by GUI thread """
        stream = urllib2.urlopen('http://www.cs.vu.nl/~arno/arno6a-1.wmv')
        streaminfo = {'mimetype':'video/x-ms-wmv','stream':stream,'length':-1}
        self.vlcwrap.load('raw:',streaminfo=streaminfo)
        self.vlcwrap.start()

        timer = Timer(10.0,self.switch1)
        timer.start()

    def switch1(self):
        """ Called by Timer thread """
        wx.CallAfter(self.start1)
        
    def start1(self):
        """ Called by GUI thread """
        print >>sys.stderr,"main: SWITCHING STREAM %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%"
        
        #stream = urllib2.urlopen('http://video.blendertestbuilds.de/download.blender.org/ED/elephantsdream-480-h264-st-aac.mov')
        #streaminfo = ('video/mov',stream,-1)
        
        stream = urllib2.urlopen('http://www.cs.vu.nl/~arno/arno6a-4.wmv')
        streaminfo = {'mimetype':'video/x-ms-wmv','stream':stream,'length':-1}
        self.vlcwrap.stop()
        self.vlcwrap.load('raw:',streaminfo=streaminfo)
        self.vlcwrap.start()

        timer = Timer(10.0,self.switch2)
        timer.start()

    def switch2(self):
        """ Called by Timer thread """
        wx.CallAfter(self.start2)
        
    def start2(self):
        """ Called by GUI thread """
        print >>sys.stderr,"main: SWITCHING STREAM 22222222222222222222222222222222222222222222222222222"
        
        #self.vlcwrap.media.stop()
        #return
    
        self.vlcwrap.stop()
        self.vlcwrap.load('http://www.cs.vu.nl/~arno/arno6a-2.wmv')
        self.vlcwrap.start()

        timer = Timer(10.0,self.switch3)
        timer.start()

    def switch3(self):
        """ Called by Timer thread """
        wx.CallAfter(self.start3)
        
    def start3(self):
        """ Called by GUI thread """
        print >>sys.stderr,"main: SWITCHING STREAM 33333333333333333333333333333333333333333333333333333"
        
        stream = urllib2.urlopen('http://www.cs.vu.nl/~arno/arno6a-3.wmv')
        streaminfo = {'mimetype':'video/x-ms-wmv','stream':stream,'length':-1}
        self.vlcwrap.stop()
        self.vlcwrap.load('raw:',streaminfo=streaminfo)
        self.vlcwrap.start()

            
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
    
    arg0 = sys.argv[0].lower()
    if arg0.endswith('.exe'):
        installdir = os.path.abspath(os.path.dirname(sys.argv[0]))
    else:
        installdir = os.getcwd()  

    # Launch first single instance
    app = PlayerApp(0, installdir)
    app.MainLoop()
    
if __name__ == '__main__':
    run()
