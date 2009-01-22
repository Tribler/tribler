# Written by Fabian van der Werf and Arno Bakker
# see LICENSE.txt for license information

import wx
import sys

import os, shutil
import time
import traceback
from time import sleep
from tempfile import mkstemp
from threading import currentThread,Event, Thread
from traceback import print_stack,print_exc
import random

from Tribler.__init__ import LIBRARYNAME
from Tribler.Video.defs import *
from Tribler.Video.Progress import ProgressBar, ProgressSlider, VolumeSlider
from Tribler.Video.Buttons import PlayerSwitchButton, PlayerButton

DEBUG = False


class VideoFrame(wx.Frame):
    """ Provides a wx.Frame around an EmbeddedPlayerPanel so the embedded player
    is shown as a separate window. The Embedded Player consists of a VLCLogoWindow
    and the media controls such as Play/Pause buttons and Volume Control.
    """
    
    def __init__(self,parent,title,iconpath,vlcwrap,logopath):
        self.utility = parent.utility
        if title is None:
            title = self.utility.lang.get('tb_video_short')
        
        if vlcwrap is None:
            size = (800,150)
        else:
            size = (800,520) # Use 16:9 aspect ratio: 500 = (800/16) * 9 + 50 for controls
        wx.Frame.__init__(self, None, -1, title, size=size) 
        
        self.create_videopanel(vlcwrap,logopath)

        # Set icons for Frame
        self.icons = wx.IconBundle()
        self.icons.AddIconFromFile(iconpath,wx.BITMAP_TYPE_ICO)
        self.SetIcons(self.icons)

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

    def create_videopanel(self,vlcwrap, logopath):
        self.showingvideo = False
        self.videopanel = EmbeddedPlayerPanel(self, self.utility, vlcwrap, logopath)
        self.Hide()

    def show_videoframe(self):
        if DEBUG:
            print >>sys.stderr,"videoframe: Swap IN videopanel"
            
        if self.videopanel is not None:
            if not self.showingvideo:
                self.showingvideo = True
                self.Show()
                
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
            if self.showingvideo:
                self.showingvideo = False
                self.Hide()

    def get_videopanel(self):
        return self.videopanel

    def delete_videopanel(self):
        self.videopanel = None

    def OnCloseWindow(self, event = None):
        self.hide_videoframe()        
                 

class EmbeddedPlayerPanel(wx.Panel):
    """
    The Embedded Player consists of a VLCLogoWindow and the media controls such 
    as Play/Pause buttons and Volume Control.
    """

    def __init__(self, parent, utility, vlcwrap, logopath):
        wx.Panel.__init__(self, parent, -1)
        self.utility = utility

        #self.SetBackgroundColour(wx.WHITE)
        self.SetBackgroundColour((216,233,240))
        mainbox = wx.BoxSizer(wx.VERTICAL)


        if vlcwrap is None:
            size = (320,64)
        else:
            size = (320,240) 
        
        self.vlcwin = VLCLogoWindow(self,size,vlcwrap,logopath)
        self.vlcwrap = vlcwrap

        # Arno: until we figure out how to show in-playback prebuffering info
        self.statuslabel = wx.StaticText(self, -1, 'Loading player...' )
        self.statuslabel.SetForegroundColour(wx.WHITE)

        if vlcwrap is not None:
            ctrlsizer = wx.BoxSizer(wx.HORIZONTAL)        
            #self.slider = wx.Slider(self, -1)
            self.slider = ProgressSlider(self, self.utility)
            #self.slider.Bind(wx.EVT_SCROLL_THUMBRELEASE, self.Seek)
            #self.slider.Bind(wx.EVT_SCROLL_THUMBTRACK, self.StopSliderUpdate)
            self.slider.SetRange(0,1)
            self.slider.SetValue(0)
            self.oldvolume = None
            
                            
            self.ppbtn = PlayerSwitchButton(self, os.path.join(self.utility.getPath(), LIBRARYNAME, 'Images'), 'pause', 'play')
            self.ppbtn.Bind(wx.EVT_LEFT_UP, self.PlayPause)
    
            self.volumebox = wx.BoxSizer(wx.HORIZONTAL)
            self.volumeicon = PlayerSwitchButton(self, os.path.join(self.utility.getPath(), LIBRARYNAME, 'Images'), 'volume', 'mute')   
            self.volumeicon.Bind(wx.EVT_LEFT_UP, self.Mute)
            self.volume = VolumeSlider(self, self.utility)
            self.volume.SetRange(0, 100)
            self.volumebox.Add(self.volumeicon, 0, wx.ALIGN_CENTER_VERTICAL)
            self.volumebox.Add(self.volume, 0, wx.ALIGN_CENTER_VERTICAL, 0)
    
            self.fsbtn = PlayerButton(self, os.path.join(self.utility.getPath(), LIBRARYNAME, 'Images'), 'fullScreen')
            self.fsbtn.Bind(wx.EVT_LEFT_UP, self.FullScreen)
    
            self.save_button = PlayerSwitchButton(self, os.path.join(self.utility.getPath(), LIBRARYNAME, 'Images'), 'saveDisabled', 'save')   
            self.save_button.Bind(wx.EVT_LEFT_UP, self.Save)
            self.save_callback = lambda:None
            
            ctrlsizer.Add(self.ppbtn, 0, wx.ALIGN_CENTER_VERTICAL)
            ctrlsizer.Add(self.slider, 1, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
            ctrlsizer.Add(self.volumebox, 0, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
            ctrlsizer.Add(self.fsbtn, 0, wx.ALIGN_CENTER_VERTICAL)
            ctrlsizer.Add(self.save_button, 0, wx.ALIGN_CENTER_VERTICAL)
        
        mainbox.Add(self.vlcwin, 1, wx.EXPAND, 1)
        mainbox.Add(self.statuslabel, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 30)
        if vlcwrap is not None:
            mainbox.Add(ctrlsizer, 0, wx.ALIGN_BOTTOM|wx.EXPAND, 1)
        self.SetSizerAndFit(mainbox)
        
        self.playtimer = None
        self.bitrateset = False
        self.update = False
        self.timer = None
        
    def Load(self,url,streaminfo = None):
        if DEBUG:
            print >>sys.stderr,"embedplay: Load:",url,streaminfo,currentThread().getName()
        # Arno: hack: disable dragging when not playing from file.
        if url.startswith('http:') or streaminfo is not None:
           self.slider.DisableDragging()
        else:
           self.slider.EnableDragging()
        self.SetPlayerStatus('')

        # Arno, 2008-10-17: If we don't do this VLC gets the wrong playlist somehow
        #self.vlcwrap.stop()
        self.vlcwrap.playlist_clear()
             
        self.vlcwrap.load(url,streaminfo=streaminfo)
        
        # Enable update of progress slider
        self.update = True
        wx.CallAfter(self.slider.SetValue,0)
        if self.timer is None:
            self.timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.UpdateSlider)
        self.timer.Start(200)
        
    def StartPlay(self):
        """ Start playing the new item after VLC has stopped playing the old
        one
        """
        if DEBUG:
            print >>sys.stderr,"embedplay: PlayWhenStopped"
        self.playtimer = DelayTimer(self)

    def Play(self, evt=None):
        if DEBUG:
            print >>sys.stderr,"embedplay: Play pressed"

        if self.GetState() != MEDIASTATE_PLAYING:
            self.ppbtn.setToggled(False)
            self.vlcwrap.start()

    def Pause(self, evt=None):
        """ Toggle between playing and pausing of current item """
        if DEBUG:
            print >>sys.stderr,"embedplay: Pause pressed"
        
        if self.GetState() == MEDIASTATE_PLAYING:
            self.ppbtn.setToggled(True)
            self.vlcwrap.pause()


    def PlayPause(self, evt=None):
        """ Toggle between playing and pausing of current item """
        if DEBUG:
            print >>sys.stderr,"embedplay: PlayPause pressed"
        
        if self.GetState() == MEDIASTATE_PLAYING:
            self.ppbtn.setToggled(True)
            self.vlcwrap.pause()

        else:
            self.ppbtn.setToggled(False)
            self.vlcwrap.start()


    def Seek(self, evt=None):
        if DEBUG:
            print >>sys.stderr,"embedplay: Seek", pos
        
        oldsliderpos = self.slider.GetValue()
        #print >>sys.stderr, 'embedplay: Seek: GetValue returned,',oldsliderpos
        pos = int(oldsliderpos * 1000.0)
        #print >>sys.stderr, 'embedplay: Seek: newpos',pos
        
        try:
            if self.GetState() == MEDIASTATE_STOPPED:
                self.vlcwrap.start(pos)
            else:
                self.vlcwrap.set_media_position(pos)
        except:
            print_exc()
            if DEBUG:
                print >> sys.stderr, 'embedplay: could not seek'
            self.slider.SetValue(oldsliderpos)
        self.update = True
        

    def FullScreen(self,evt=None):
        self.vlcwrap.set_fullscreen(True)

    def Mute(self, evt = None):
        if self.volumeicon.isToggled():
            if self.oldvolume is not None:
                self.vlcwrap.sound_set_volume(self.oldvolume)
            self.volumeicon.setToggled(False)
        else:
            self.oldvolume = self.vlcwrap.sound_get_volume()
            self.vlcwrap.sound_set_volume(0.0) # mute sound
            self.volumeicon.setToggled(True)
        
    def Save(self, evt = None):
        # save media content in different directory
        if self.save_button.isToggled():
            self.save_callback()
            
    
    def SetVolume(self, evt = None):
        if DEBUG:
            print >> sys.stderr, "embedplay: SetVolume:",self.volume.GetValue()
        self.vlcwrap.sound_set_volume(float(self.volume.GetValue()) / 100)
        # reset mute
        if self.volumeicon.isToggled():
            self.volumeicon.setToggled(False)

    def Stop(self):
        if DEBUG:
            print >> sys.stderr, "embedplay: Stop"
        self.vlcwrap.stop()
        self.ppbtn.SetLabel(self.utility.lang.get('playprompt'))
        self.slider.SetValue(0)
        if self.timer is not None:
            self.timer.Stop()
        self.bitrateset = False

    def GetState(self):
        """ Returns the state of VLC as summarized by Fabian: 
        MEDIASTATE_PLAYING, MEDIASTATE_PAUSED, MEDIASTATE_STOPPED """
        if DEBUG:
            print >>sys.stderr,"embedplay: GetState"
            
        status = self.vlcwrap.get_stream_information_status()
        
        import vlc
        if status == vlc.PlayingStatus:
            return MEDIASTATE_PLAYING
        elif status == vlc.PauseStatus:
            return MEDIASTATE_PAUSED
        else:
            return MEDIASTATE_STOPPED


    def EnableSaveButton(self, b, callback):
        self.save_button.setToggled(b)
        if b:
            self.save_callback = callback
        else:
            self.save_callback = lambda:None

    def Reset(self):
        self.DisableInput()
        self.Stop()
        self.UpdateProgressSlider([False])

    #
    # Control on-screen information
    #
    def UpdateStatus(self,playerstatus,pieces_complete):
        self.SetPlayerStatus(playerstatus)
        if self.vlcwrap is not None:
            self.UpdateProgressSlider(pieces_complete)
    
    def SetPlayerStatus(self,s):
        self.statuslabel.SetLabel(s)

    def SetContentName(self,s):
        self.vlcwin.set_content_name(s)

    def SetContentImage(self,wximg):
        self.vlcwin.set_content_image(wximg)


    #
    # Internal methods
    #
    def EnableInput(self):
        self.ppbtn.Enable(True)
        self.slider.Enable(True)
        self.fsbtn.Enable(True)

    def UpdateProgressSlider(self, pieces_complete):
        self.slider.setBufferFromPieces(pieces_complete)
        self.slider.Refresh()
        
    def DisableInput(self):
        return # Not currently used
        
        self.ppbtn.Disable()
        self.slider.Disable()
        self.fsbtn.Disable()

    def UpdateSlider(self, evt):
        if not self.volumeicon.isToggled():
            self.volume.SetValue(int(self.vlcwrap.sound_get_volume() * 100))

        if self.update and self.GetState() != MEDIASTATE_STOPPED:
            len = self.vlcwrap.get_stream_information_length()
            if len == -1:
                return
            len /= 1000

            cur = self.vlcwrap.get_media_position() / 1000

            self.slider.SetRange(0, len)
            self.slider.SetValue(cur)
            self.slider.SetTimePosition(float(cur), len)

    def StopSliderUpdate(self, evt):
        self.update = False


    def TellLVCWrapWindow4Playback(self):
        if self.vlcwrap is not None:
            self.vlcwin.tell_vclwrap_window_for_playback()


class VLCLogoWindow(wx.Window):
    """ A wx.Window to be passed to the vlc.MediaControl to draw the video
    in (normally). In addition, the class can display a logo, a thumbnail and a 
    "Loading: bla.video" message when VLC is not playing.
    """
    
    def __init__(self, parent, size, vlcwrap, logopath):
        wx.Window.__init__(self, parent, -1, size=size)
        self.SetMinSize(size)
        self.SetBackgroundColour((216,233,240))
        
        self.vlcwrap = vlcwrap

        if logopath is not None:
            self.logo = wx.BitmapFromImage(wx.Image(logopath),-1)
        else:
            self.logo = None
        self.contentname = None
        self.contentbm = None
        self.Bind(wx.EVT_PAINT, self.OnPaint)

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

    def OnPaint(self,evt):
        dc = wx.PaintDC(self)
        dc.Clear()
        dc.BeginDrawing()        

        x,y,maxw,maxh = self.GetClientRect()
        halfx = (maxw-x)/2
        halfy = (maxh-y)/2
        halfx -= self.logo.GetWidth()/2
        halfy -= self.logo.GetHeight()/2

        dc.SetPen(wx.Pen(wx.Colour(216,233,240),0))
        dc.SetBrush(wx.Brush(wx.Colour(216,233,240)))
        if sys.platform == 'linux2':
            dc.DrawRectangle(x,y,maxw,maxh)
        dc.DrawBitmap(self.logo,halfx,halfy,True)
        #logox = max(0,maxw-self.logo.GetWidth()-30)
        #dc.DrawBitmap(self.logo,logox,20,True)

        dc.SetTextForeground(wx.WHITE)
        dc.SetTextBackground(wx.BLACK)
        
        lineoffset = 120
        txty = halfy+self.logo.GetHeight()+lineoffset
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
            self.embedplay.PlayPause()
        elif DEBUG:
            print >>sys.stderr,"embedplay: VLC is still playing old video"

