# Written by Fabian van der Werf and Arno Bakker
# see LICENSE.txt for license information

import wx
import sys
import os

from Tribler.Video.defs import *
from Tribler.__init__ import LIBRARYNAME

DEBUG = False


class VideoBaseFrame:

    def show_videoframe(self):
        pass

    def hide_videoframe(self):
        pass

    def get_videopanel(self):
        pass

    def delete_videopanel(self):
        pass

    def OnCloseWindow(self, event=None):
        pass

    def get_window(self):
        pass

    def ShowLoading(self):
        pass

    def Stop(self):
        pass

    def Destroy(self):
        pass


# See Tribler/Main/vwxGUI/MainVideoFrame.py for Tribler 5.0
# See Tribler/Player/PlayerVideoFrame.py for the SwarmPlayer / 4.5


class DelayTimer(wx.Timer):

    """ vlc.MediaCtrl needs some time to stop after we give it a stop command.
        Wait until it is and then tell it to play the new item
    """
    def __init__(self, embedplay):
        wx.Timer.__init__(self)
        self.embedplay = embedplay
        self.Start(100)

    def Notify(self):
        if self.embedplay.GetState() != MEDIASTATE_PLAYING:
            if DEBUG:
                print >>sys.stderr, "embedplay: VLC has stopped playing previous video, starting it on new"
            self.Stop()
            self.embedplay.Play()
        elif DEBUG:
            print >>sys.stderr, "embedplay: VLC is still playing old video"
