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
        pass

    def hide_videoframe(self):
        pass

    def get_videopanel(self):
        return self.videopanel

    def get_window(self):
        return self.parent
