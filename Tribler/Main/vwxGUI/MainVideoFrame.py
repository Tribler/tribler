# Written by Fabian van der Werf and Arno Bakker
# see LICENSE.txt for license information

import wx

from Tribler.Video.VideoFrame import VideoBaseFrame
from Tribler.Main.vwxGUI.EmbeddedPlayer import EmbeddedPlayerPanel


class VideoDummyFrame(VideoBaseFrame):

    """ Provides a fake Frame around an EmbeddedPlayerPanel so the embedded player
    can be shown inside another window.
    """

    def __init__(self, parent, utility, vlcwrap):
        self.videopanel = EmbeddedPlayerPanel(parent, utility, vlcwrap, wx.BLACK)
        self.parent = parent
        self.utility = utility
        self.vlcwrap = vlcwrap

        if vlcwrap:
            sizer = wx.BoxSizer()
            sizer.Add(self.videopanel, 1, wx.EXPAND)
            parent.SetSizer(sizer)
        else:
            self.videopanel.Hide()

    def recreate_vlc_window(self):
        self.videopanel.RecreateVLCWindow()

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
