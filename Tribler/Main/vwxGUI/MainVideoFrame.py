# Written by Fabian van der Werf and Arno Bakker
# see LICENSE.txt for license information

import wx
import sys
import os

from Tribler.Video.VideoFrame import VideoBaseFrame
from Tribler.Main.vwxGUI.EmbeddedPlayer import EmbeddedPlayerPanel
from Tribler.__init__ import LIBRARYNAME

DEBUG = False

        
class VideoMacFrame(wx.Frame, VideoBaseFrame):
    """ Provides a wx.Frame around an EmbeddedPlayerPanel so the embedded player
    is shown as a separate window. The Embedded Player consists of a VLCLogoWindow
    and the media controls such as Play/Pause buttons and Volume Control.

    + Provides a frame fr mac os x using the icons of the 5.0

    """
    def __init__(self, parent, utility, title, iconpath, vlcwrap):
        self.utility = utility
        self.vlcwrap = vlcwrap
        self.videopanel = None
        
        if title is None:
            title = self.utility.lang.get('tb_video_short')
        
        wx.Frame.__init__(self, None, -1, title)
        self.SetBackgroundColour(wx.WHITE)
        
        # Set icons for Frame
        self.icons = wx.IconBundle()
        self.icons.AddIconFromFile(iconpath,wx.BITMAP_TYPE_ICO)
        self.SetIcons(self.icons)

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.Show(False)

    def show_videoframe(self):
        if DEBUG:
            print >>sys.stderr,"videoframe: Swap IN videopanel"
        
        if not self.videopanel:
            self.get_videopanel()

        self.Show()
        self.CenterOnScreen()
        self.Raise()
        self.SetFocus()
                       
        # H4x0r: We need to tell the VLC wrapper a XID of a
        # window to paint in. Apparently on win32 the XID is only
        # known when the window is shown. We give it the command
        # to show here, so shortly after it should be shown.
        #
        wx.CallAfter(self.videopanel.TellLVCWrapWindow4Playback)
    
    def hide_videoframe(self):
        if DEBUG:
            print >>sys.stderr,"videoframe: Swap OUT videopanel"
        
        if self.videopanel is not None:
            self.videopanel.Reset()
            self.Hide()

    def get_videopanel(self):
        if self.videopanel is None:
            self.videopanel = EmbeddedPlayerPanel(self, self.utility, self.vlcwrap, '#E6E6E6', False)
            self.videopanel.SetMinSize((320,320))
            
            mainbox = wx.BoxSizer()
            mainbox.Add(self.videopanel, 1, wx.EXPAND)
            self.SetSizerAndFit(mainbox)
        return self.videopanel

    def get_window(self):
        return self

    def OnCloseWindow(self, event = None):
        self.hide_videoframe()

class VideoDummyFrame(VideoBaseFrame):
    """ Provides a fake Frame around an EmbeddedPlayerPanel so the embedded player
    can be shown inside another window. 
    """
    
    def __init__(self,parent,utility,vlcwrap):
        self.videopanel = EmbeddedPlayerPanel(parent, utility, vlcwrap, '#E6E6E6')
        
        sizer = wx.BoxSizer()
        sizer.Add(self.videopanel)
        parent.SetSizer(sizer)

    def show_videoframe(self):
        if self.videopanel:
            pass
        # H4x0r: We need to tell the VLC wrapper a XID of a
        # window to paint in. Apparently on win32 the XID is only
        # known when the window is shown. We give it the command
        # to show here, so shortly after it should be shown.
        #
        wx.CallAfter(self.videopanel.TellLVCWrapWindow4Playback)
    
    def hide_videoframe(self):
        if self.videopanel:
            pass

    def get_videopanel(self):
        return self.videopanel

    def get_window(self):
        return self.parent
