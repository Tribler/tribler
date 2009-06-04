# Written by Fabian van der Werf and Arno Bakker
# see LICENSE.txt for license information

import wx
import sys

from Tribler.Video.defs import *

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

    def OnCloseWindow(self, event = None):
        pass

    def get_window(self):
        pass


# See Tribler/Main/vwxGUI/MainVideoFrame.py for Tribler 5.0
# See Tribler/Player/PlayerVideoFrame.py for the SwarmPlayer / 4.5


class VLCLogoWindow(wx.Panel):
    """ A wx.Window to be passed to the vlc.MediaControl to draw the video
    in (normally). In addition, the class can display a logo, a thumbnail and a 
    "Loading: bla.video" message when VLC is not playing.
    """
    
    def __init__(self, parent, size, vlcwrap, logopath, fg=wx.WHITE, bg=wx.BLACK, animate = False, position = (300,300)):
        wx.Panel.__init__(self, parent, -1, size=size)
        self.parent = parent ##
    
        self.SetMinSize(size)
        self.SetBackgroundColour(bg)
        self.bg = bg
        self.vlcwrap = vlcwrap
        self.animation_running = False
       
        self.Bind(wx.EVT_KEY_UP, self.keyDown)

        if logopath is not None and not animate:
            self.logo = wx.BitmapFromImage(wx.Image(logopath),-1)
        else:
            self.logo = None
        self.contentname = None
        self.contentbm = None
        #self.Bind(wx.EVT_PAINT, self.OnPaint)
        if sys.platform == 'darwin':
            self.hsizermain = wx.BoxSizer(wx.HORIZONTAL)
            self.vsizer = wx.BoxSizer(wx.VERTICAL)
            self.vsizer.Add((0,70),0,0,0)
        if animate:
            if sys.platform == 'darwin':
                self.agVideo = wx.animate.GIFAnimationCtrl(self, 1, logopath)
            else:
                self.agVideo = wx.animate.GIFAnimationCtrl(self, 1, logopath, pos = (110,70))
            self.agVideo.Hide()
            if sys.platform == 'darwin':
                self.vsizer.Add(self.agVideo,0,wx.ALIGN_CENTRE_HORIZONTAL,0)
                self.vsizer.Add((0,10),0,0,0)
        else:
            self.agVideo = None

        #self.playbackText = wx.StaticText(self,-1,"Leave Tribler running\n for faster playback",wx.Point(30,140))
        #self.playbackText.SetFont(wx.Font(8, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "UTF-8"))
        #self.playbackText.SetForegroundColour(wx.Colour(255,51,00))
        if sys.platform == 'darwin':
            self.loadingtext = wx.StaticText(self,-1,'')
        else:
            self.loadingtext = wx.StaticText(self,-1,'',wx.Point(0,200),wx.Size(320,30),style=wx.ALIGN_CENTRE)
        if sys.platform == 'darwin':
            self.loadingtext.SetFont(wx.Font(12, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "UTF-8"))
        else:
            self.loadingtext.SetFont(wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "UTF-8"))
        self.loadingtext.SetForegroundColour(wx.WHITE)

        if sys.platform == 'darwin':
            self.vsizer.Add(self.loadingtext,1,wx.ALIGN_CENTRE_HORIZONTAL,0)
            self.hsizermain.Add(self.vsizer,1,wx.ALIGN_CENTRE_HORIZONTAL,0)
            self.SetSizer(self.hsizermain)
            self.SetAutoLayout(1)
            self.Layout()
            self.Refresh()
        if self.vlcwrap is not None:
            wx.CallAfter(self.tell_vclwrap_window_for_playback)
        
    def tell_vclwrap_window_for_playback(self):
        """ This method must be called after the VLCLogoWindow has been
        realized, otherwise the self.GetHandle() call that vlcwrap.set_window()
        does, doesn't return a correct XID.
        """
        self.vlcwrap.set_window(self)

    def get_vlcwrap(self):
        return self.vlcwrap

    def set_content_name(self,s):
        if DEBUG:
            print >>sys.stderr,"VLCWin: set_content_name"
        self.contentname = s
        self.Refresh()
    
    def set_content_image(self,wximg):
        if DEBUG:
            print >>sys.stderr,"VLCWin: set_content_image"
        if wximg is not None:
            self.contentbm = wx.BitmapFromImage(wximg,-1)
        else:
            self.contentbm = None

    def is_animation_running(self):
        return self.animation_running

    def setloadingtext(self, text):
        self.loadingtext.SetLabel(text)
        self.Refresh()

    def show_loading(self):
        if self.agVideo:
            self.agVideo.Show()
            self.agVideo.Play()
            self.animation_running = True
            self.Refresh()


        
        
    def stop_animation(self):
        if self.agVideo:
            self.agVideo.Stop()
            self.agVideo.Hide()
            self.animation_running = False
            self.Refresh()

    def OnPaint(self,evt):
        dc = wx.PaintDC(self)
        dc.Clear()
        dc.BeginDrawing()        

        x,y,maxw,maxh = self.GetClientRect()
        halfx = (maxw-x)/2
        halfy = (maxh-y)/2
        if self.logo is None:
            halfx = 10
            halfy = 10
            lheight = 20
        else:
            halfx -= self.logo.GetWidth()/2
            halfy -= self.logo.GetHeight()/2
            lheight = self.logo.GetHeight()

        dc.SetPen(wx.Pen(self.bg,0))
        dc.SetBrush(wx.Brush(self.bg))
        if sys.platform == 'linux2':
            dc.DrawRectangle(x,y,maxw,maxh)
        if self.logo is not None:
            dc.DrawBitmap(self.logo,halfx,halfy,True)
        #logox = max(0,maxw-self.logo.GetWidth()-30)
        #dc.DrawBitmap(self.logo,logox,20,True)

        dc.SetTextForeground(wx.WHITE)
        dc.SetTextBackground(wx.BLACK)
        
        lineoffset = 120
        txty = halfy+lheight+lineoffset
        if txty > maxh:
            txty = 0
        if self.contentname is not None:
            txt = self.contentname
            dc.DrawText(txt,30,txty)
            lineoffset += 30

        #txt = self.getStatus()
        #dc.DrawText(txt,30,halfy+self.logo.GetHeight()+lineoffset)
        
        if self.contentbm is not None:
            bmy = max(20,txty-20-self.contentbm.GetHeight())
            dc.DrawBitmap(self.contentbm,30,bmy,True)
        
        dc.EndDrawing()
        if evt is not None:
            evt.Skip(True)


    def keyDown(self, event):
        Level = event.StopPropagation()
        event.ResumePropagation(10)

        event.Skip()
        self.gg()




class DelayTimer(wx.Timer):
    """ vlc.MediaCtrl needs some time to stop after we give it a stop command.
        Wait until it is and then tell it to play the new item
    """
    def __init__(self,embedplay):
        wx.Timer.__init__(self)
        self.embedplay = embedplay
        self.Start(100)
        
    def Notify(self):
        if self.embedplay.GetState() != MEDIASTATE_PLAYING:
            if DEBUG:
                print >>sys.stderr,"embedplay: VLC has stopped playing previous video, starting it on new"
            self.Stop()
            self.embedplay.Play()
        elif DEBUG:
            print >>sys.stderr,"embedplay: VLC is still playing old video"

