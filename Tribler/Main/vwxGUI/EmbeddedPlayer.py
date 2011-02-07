# Written by Fabian van der Werf and Arno Bakker
# see LICENSE.txt for license information
#
# EmbeddedPlayerPanel is the panel used in Tribler 5.0
# EmbeddedPlayer4FramePanel is the panel used in the SwarmPlayer / 4.5
# 

import wx
import sys

import os, shutil
import time
import random
from time import sleep
from tempfile import mkstemp
from threading import currentThread,Event, Thread
from traceback import print_stack,print_exc
from textwrap import wrap

from Tribler.__init__ import LIBRARYNAME
from Tribler.Video.defs import *
from Tribler.Video.VideoFrame import DelayTimer
from Tribler.Video.Progress import ProgressBar, ProgressSlider, VolumeSlider
from Tribler.Video.Buttons import PlayerSwitchButton, PlayerButton
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton

from list_header import PlayerHeader
from list_footer import ListFooter

DEBUG = False


class EmbeddedPlayerPanel(wx.Panel):
    """
    The Embedded Player consists of a VLCLogoWindow and the media controls such 
    as Play/Pause buttons and Volume Control.
    """

    def __init__(self, parent, utility, vlcwrap, bg, border = True):
        wx.Panel.__init__(self, parent, -1)
        self.utility = utility
        self.parent = parent
        self.border = border
        self.SetBackgroundColour(wx.WHITE)
        
        self.volume = 0.48
        self.oldvolume = 0.48
        self.estduration = None

        self.fullscreen_enabled = False
        self.fullscreenwindow = None
        self.play_enabled = False
        self.scroll_enabled = False

        vSizer = wx.BoxSizer(wx.VERTICAL)
        if border:
            self.SetMinSize((34,-1))
            
            images = ("minimize.png", "maximize.png")
            images = [os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images",image) for image in images]
            self.header  = PlayerHeader(self, bg, [], images[0], images[1])
            
            vSizer.Add(self.header, 0, wx.EXPAND)
            
            hSizer  = wx.BoxSizer(wx.HORIZONTAL)
            self.leftLine = wx.Panel(self, size=(1,-1))
            self.leftLine.SetBackgroundColour(bg)
            
            mainbox = wx.BoxSizer(wx.VERTICAL)
            
            self.rightLine = wx.Panel(self, size=(1,-1))
            self.rightLine.SetBackgroundColour(bg)
            
            hSizer.Add(self.leftLine, 0, wx.EXPAND)
            hSizer.Add(mainbox, 1, wx.EXPAND)
            hSizer.Add(self.rightLine, 0, wx.EXPAND)
        
            vSizer.Add(hSizer, 1, wx.EXPAND)
            
            footer = ListFooter(self)
            footer.SetBackgroundColour(bg)
            vSizer.Add(footer, 0, wx.EXPAND)
        else:
            mainbox = vSizer
        
        self.vlcwrap = vlcwrap
        if vlcwrap is not None:
            self.vlcwin = VLCLogoWindow(self, utility, vlcwrap, bg, animate = True)
            self.vlcwin.SetMinSize((320,240))
            
            if border:
                player_img = os.path.join(self.utility.getPath(), LIBRARYNAME,"Main","vwxGUI",'images','player.png')
                self.player_img = wx.StaticBitmap(self, -1, wx.BitmapFromImage(wx.Image(player_img, wx.BITMAP_TYPE_ANY)))
                mainbox.Add(self.player_img, 0, wx.ALIGN_CENTER|wx.TOP, 5)
            mainbox.Add(self.vlcwin, 1, wx.EXPAND, 0)
            
            self.ctrlsizer = wx.BoxSizer(wx.HORIZONTAL)        
            self.slider = ProgressSlider(self, self.utility)
            self.slider.SetRange(0,1)
            self.slider.SetValue(0)
            
            self.mute = SwitchButton(self, name = 'mt')
            self.mute.Bind(wx.EVT_LEFT_UP, self.MuteClicked)
                            
            self.ppbtn = PlayerSwitchButton(self, os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'pause', 'play')
            self.ppbtn.Bind(wx.EVT_LEFT_UP, self.PlayPause)
            self.ppbtn.setSelected(2)
    
            volumebox = wx.BoxSizer(wx.HORIZONTAL)
            self.vol1 = PlayerButton(self,os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'vol1')
            self.vol1.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

            self.vol2 = PlayerButton(self,os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'vol2')
            self.vol2.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

            self.vol3 = PlayerButton(self,os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'vol3')
            self.vol3.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

            self.vol4 = PlayerButton(self,os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'vol4')
            self.vol4.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

            self.vol5 = PlayerButton(self,os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'vol5')
            self.vol5.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

            self.vol6 = PlayerButton(self,os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'vol6')
            self.vol6.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

            volumebox.Add(self.vol1, 0, wx.ALIGN_CENTER_VERTICAL)
            volumebox.Add(self.vol2, 0, wx.ALIGN_CENTER_VERTICAL)
            volumebox.Add(self.vol3, 0, wx.ALIGN_CENTER_VERTICAL)
            volumebox.Add(self.vol4, 0, wx.ALIGN_CENTER_VERTICAL)
            volumebox.Add(self.vol5, 0, wx.ALIGN_CENTER_VERTICAL)            
            volumebox.Add(self.vol6, 0, wx.ALIGN_CENTER_VERTICAL)
            self.updateVol(self.volume)
    
            self.fsbtn = PlayerButton(self, os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'fullScreen')
            self.fsbtn.Bind(wx.EVT_LEFT_UP, self.FullScreen)
            self.fsbtn.setSelected(2)

            self.save_button = PlayerSwitchButton(self, os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'saveDisabled', 'save')   
            self.save_button.Bind(wx.EVT_LEFT_UP, self.Save)
            self.save_callback = lambda:None
            self.save_button.Hide()

            self.ctrlsizer.Add(self.ppbtn, 0, wx.ALIGN_CENTER_VERTICAL)
            self.ctrlsizer.AddSpacer((5,0))
            
            self.ctrlsizer.Add(self.fsbtn, 0, wx.ALIGN_CENTER_VERTICAL)
            self.ctrlsizer.Add(self.slider, 1, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
            self.ctrlsizer.Add(volumebox, 0, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
            self.ctrlsizer.Add(self.mute, 0, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)

            mainbox.Add(self.ctrlsizer, 0, wx.ALIGN_BOTTOM|wx.EXPAND|wx.LEFT|wx.RIGHT, 3)
            if border:
                self.vlcwin.Show(False)
                self.ctrlsizer.ShowItems(False)
        
        # Arno: until we figure out how to show in-playback prebuffering info
        self.statuslabel = wx.StaticText(self)
        vSizer.Add(self.statuslabel, 0, wx.EXPAND)
        self.SetSizer(vSizer)
        
        self.playtimer = None
        self.update = False
        self.timer = None
        
    def mouseAction(self,event):
        if event.LeftDown():
            if self.mute.isToggled(): # unmute
                self.mute.setToggled(False)
            if event.GetEventObject().GetImageNameitem() == 'vol1':
                self.volume = 0.16
            if event.GetEventObject().GetImageName() == 'vol2':
                self.volume = 0.32
            if event.GetEventObject().GetImageName() == 'vol3':
                self.volume = 0.48
            if event.GetEventObject().GetImageName() == 'vol4':
                self.volume = 0.64
            if event.GetEventObject().GetImageName() == 'vol5':
                self.volume = 0.80
            if event.GetEventObject().GetImageName() == 'vol6':
                self.volume = 1.00
            self.oldvolume = self.volume
            self.updateVol(self.volume) 
            self.SetVolume(self.volume)
        elif event.Entering():
            if event.GetEventObject().GetImageName() == 'vol1':
                volume = 0.16
            if event.GetEventObject().GetImageName() == 'vol2':
                volume = 0.32
            if event.GetEventObject().GetImageName() == 'vol3':
                volume = 0.48
            if event.GetEventObject().GetImageName() == 'vol4':
                volume = 0.64
            if event.GetEventObject().GetImageName() == 'vol5':
                volume = 0.80
            if event.GetEventObject().GetImageName() == 'vol6':
                volume = 1.00
            self.updateVol(volume) 
        elif event.Leaving():
            self.updateVol(self.volume) 

    def MuteClicked(self, event):
        if self.mute.isToggled():
            self.volume = self.oldvolume
        else:
            self.volume = 0
        self.updateVol(self.volume) 
        self.SetVolume(self.volume)
        self.mute.setToggled(not self.mute.isToggled())

    def updateVol(self,volume): # updates the volume bars in the gui
        self.vol1.setSelected(volume >= 0.16)
        self.vol2.setSelected(volume >= 0.32)
        self.vol3.setSelected(volume >= 0.48)
        self.vol4.setSelected(volume >= 0.64)
        self.vol5.setSelected(volume >= 0.80)
        self.vol6.setSelected(volume >= 1.00)

    def Load(self,url,streaminfo = None):
        if DEBUG:
            print >>sys.stderr,"embedplay: Load:",url,streaminfo,currentThread().getName()

        ##self.SetPlayerStatus('')
        if streaminfo is not None:
            self.estduration = streaminfo.get('estduration',None)

        # 19/02/10 Boudewijn: no self.slider when self.vlcwrap is None
        # 26/05/09 Boudewijn: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            # Arno: hack: disable dragging when not playing from file.
            if url is None or url.startswith('http:'):
                self.slider.DisableDragging()
            else:
                self.slider.EnableDragging()

            # Arno, 2009-02-17: If we don't do this VLC gets the wrong playlist somehow
            self.vlcwrap.stop()
            self.vlcwrap.playlist_clear()
            self.vlcwrap.load(url,streaminfo=streaminfo)
        
            # Enable update of progress slider
            self.update = True
            wx.CallAfter(self.slider.SetValue,0)
            if self.timer is None:
                self.timer = wx.Timer(self)
                self.Bind(wx.EVT_TIMER, self.UpdateSlider)
            self.timer.Start(200)
        self.enableFullScreen()
        self.enablePlay()
        self.enableScroll()

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
        
        self.OnMaximize()
        
        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            self.vlcwin.stop_animation()

            if self.GetState() != MEDIASTATE_PLAYING:
                self.ppbtn.setToggled(False)
                self.vlcwrap.start()

    def Pause(self, evt=None):
        """ Toggle between playing and pausing of current item """
        if DEBUG:
            print >>sys.stderr,"embedplay: Pause pressed"

        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            if self.GetState() == MEDIASTATE_PLAYING:
                self.ppbtn.setToggled(True)
                self.vlcwrap.pause()

    def PlayPause(self, evt=None):
        """ Toggle between playing and pausing of current item """
        if DEBUG:
            print >>sys.stderr,"embedplay: PlayPause pressed"
        
        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            if self.GetState() == MEDIASTATE_PLAYING:
                self.ppbtn.setToggled(True)
                self.vlcwrap.pause()

            else:
                if self.play_enabled:
                    self.vlcwin.stop_animation()
                    self.ppbtn.setToggled(False)
                    self.vlcwrap.resume()

    def Seek(self, evt=None):
        if DEBUG:
            print >>sys.stderr,"embedplay: Seek"
        
        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
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

    def enableScroll(self):
        self.scroll_enabled = True
        # 19/02/10 Boudewijn: no self.slider when self.vlcwrap is None
        if self.vlcwrap:
            self.slider.EnableDragging()

    def disableScroll(self):
        self.scroll_enabled = False
        # 19/02/10 Boudewijn: no self.slider when self.vlcwrap is None
        if self.vlcwrap:
            self.slider.DisableDragging()

    def enablePlay(self):
        self.play_enabled = True
        self.ppbtn.setSelected(False)

    def disablePlay(self):
        self.play_enabled = False
        self.ppbtn.setSelected(2)

    def enableFullScreen(self):
        self.fullscreen_enabled = True
        self.fsbtn.setSelected(False)

    def disableFullScreen(self):
        self.fullscreen_enabled = False
        self.fsbtn.setSelected(2)

    def FullScreen(self, evt=None):
        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap and self.fullscreen_enabled:
            self._ToggleFullScreen()
            
    def OnFullScreenKey(self, event, fullscreenwindow):
        if event.GetUnicodeKey() == wx.WXK_ESCAPE:
            self._ToggleFullScreen(fullscreenwindow)
            
        elif event.GetUnicodeKey() == wx.WXK_SPACE:
            if self.GetState() == MEDIASTATE_PLAYING:
                self.vlcwrap.pause()
            else:
                self.vlcwrap.resume()
    
    def _ToggleFullScreen(self):
        if isinstance(self.parent, wx.Frame): #are we shown in popup frame
            if self.ctrlsizer.IsShown(0):
                self.parent.ShowFullScreen(True)
                self.ctrlsizer.ShowItems(False)
            
                self.Bind(wx.EVT_KEY_DOWN, lambda event: self.OnFullScreenKey(event))
                self.Layout()
            else:
                self.parent.ShowFullScreen(False)
                self.ctrlsizer.ShowItems(True)
                
                self.Bind(wx.EVT_KEY_DOWN, None)
                self.Layout()
        else:
            #saving media player state
            cur_time = self.vlcwrap.get_media_position()
            cur_state = self.vlcwrap.get_our_state()
            
            self.vlcwrap.stop()
            if not self.fullscreenwindow:
                # create a new top level frame where to attach the vlc widget and
                # render the fullscreen video
                print >> sys.stderr, "creating fullscreenwindow"
                
                self.fullscreenwindow = wx.Frame(None, title="FullscreenVLC")
                self.fullscreenwindow.SetBackgroundColour("BLACK")
                
                eventPanel = wx.Panel(self.fullscreenwindow)
                eventPanel.SetBackgroundColour(wx.BLACK)
                eventPanel.Bind(wx.EVT_KEY_DOWN, lambda event: self.OnFullScreenKey(event))
                self.fullscreenwindow.Bind(wx.EVT_CLOSE, lambda event: self._ToggleFullScreen())
                
                self.fullscreenwindow.ShowFullScreen(True)
                self.vlcwrap.set_window(self.fullscreenwindow)
            else:
                self.TellLVCWrapWindow4Playback()
                self.fullscreenwindow.Destroy()
                self.fullscreenwindow = None
            
            #restoring state
            if cur_state == MEDIASTATE_PLAYING:
                self.vlcwrap.start(cur_time)
                
            elif cur_state == MEDIASTATE_PAUSED:
                self.vlcwrap.start(cur_time)
                
                def doPause(cur_time):
                    self.vlcwrap.pause()
                    self.vlcwrap.set_media_position(cur_time)
                wx.CallLater(500, doPause, cur_time)

    def Save(self, evt = None):
        # save media content in different directory
        if self.save_button.isToggled():
            self.save_callback()
    
    def SetVolume(self, volume, evt = None):
        if DEBUG:
            print >> sys.stderr, "embedplay: SetVolume:",self.volume
        
        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            self.vlcwrap.sound_set_volume(volume)  ## float(self.volume.GetValue()) / 100

    def Stop(self):
        if DEBUG:
            print >> sys.stderr, "embedplay: Stop"
        self.OnMinimize()
        
        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            self.vlcwrap.stop()
            self.ppbtn.SetLabel(self.utility.lang.get('playprompt'))
            self.slider.ResetTime()
            self.slider.SetValue(0)
            self.disableFullScreen()
            self.disablePlay()
            self.disableScroll()

            if self.timer is not None:
                self.timer.Stop()

    def GetState(self):
        """ Returns the state of VLC as summarized by Fabian: 
        MEDIASTATE_PLAYING, MEDIASTATE_PAUSED, MEDIASTATE_STOPPED """
            
        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            status = self.vlcwrap.get_stream_information_status()

            if DEBUG:
                print >>sys.stderr,"embedplay: GetState",status

            import vlc
            if status == vlc.PlayingStatus:
                return MEDIASTATE_PLAYING
            elif status == vlc.PauseStatus:
                return MEDIASTATE_PAUSED
            else:
                return MEDIASTATE_STOPPED
        else:
            return MEDIASTATE_STOPPED

    def Reset(self):
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
        if sys.platform == 'win32':
            msg = "\n".join(wrap(s,64))
        else:
            msg = "\n".join(wrap(s,48))
        self.SetLoadingText(msg)

    def SetContentName(self,s):
        self.vlcwin.set_content_name(s)

    def SetContentImage(self,wximg):
        self.vlcwin.set_content_image(wximg)

    def SetLoadingText(self,text):
        if text == None:
            text = ''
        if text != self.statuslabel.GetLabel():
            self.statuslabel.SetLabel(text)

    #
    # Internal methods
    #
    def UpdateProgressSlider(self, pieces_complete):
        # 19/02/10 Boudewijn: no self.slider when self.vlcwrap is None
        if self.vlcwrap:
            self.slider.setBufferFromPieces(pieces_complete)
            self.slider.Refresh()
        
    def DisableInput(self):
        # return # Not currently used
        
        self.ppbtn.Disable()
        # 19/02/10 Boudewijn: no self.slider when self.vlcwrap is None
        if self.vlcwrap:
            self.slider.Disable()
        self.fsbtn.Disable()

    def UpdateSlider(self, evt):
        ##if not self.volumeicon.isToggled():
        ##    self.volume.SetValue(int(self.vlcwrap.sound_get_volume() * 100))

        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            if self.update and self.GetState() != MEDIASTATE_STOPPED:

                len = self.vlcwrap.get_stream_information_length()
                if len == -1 or len == 0:
                    if self.estduration is None:
                        return
                    else:
                        len = int(self.estduration)
                else:
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

    def ShowLoading(self):
        if self.vlcwrap:
            self.vlcwin.show_loading()
            self.OnMaximize()

    def OnMinimize(self):
        if self.vlcwrap and self.border:
            self.SetMinSize((34,-1))
            
            self.vlcwin.Show(False)
            self.ctrlsizer.ShowItems(False)
            self.header.ShowMinimized(False)
            self.statuslabel.Show(False)
            self.player_img.Show(True)
            
            self.utility.guiUtility.frame.Layout()
        
    def OnMaximize(self):
        if self.vlcwrap and self.border:
            self.SetMinSize((320,-1))
            
            self.vlcwin.Show(True)
            self.ctrlsizer.ShowItems(True)
            self.header.ShowMinimized(True)
            self.statuslabel.Show(True)
            self.player_img.Show(False)

            self.utility.guiUtility.frame.Layout()

class VLCLogoWindow(wx.Panel):
    """ A wx.Window to be passed to the vlc.MediaControl to draw the video
    in (normally). In addition, the class can display a logo, a thumbnail and a 
    "Loading: bla.video" message when VLC is not playing.
    """
    
    def __init__(self, parent, utility, vlcwrap, bg=wx.BLACK, animate = False, position = (300,300)):
        wx.Panel.__init__(self, parent)
        self.parent = parent ##

        self.utility = utility    
        self.SetBackgroundColour(bg)
        self.bg = bg
        self.vlcwrap = vlcwrap
        self.animation_running = False

        self.contentname = None
        self.contentbm = None
        if sys.platform == 'darwin':
            self.hsizermain = wx.BoxSizer(wx.HORIZONTAL)
            self.vsizer = wx.BoxSizer(wx.VERTICAL)
            self.vsizer.Add((0,70),0,0,0)
        
        if animate:
            animation = os.path.join(self.utility.getPath(),'Tribler','Main','vwxGUI','images','video_grey.gif')
            
            if sys.platform == 'darwin':
                self.agVideo = wx.animate.GIFAnimationCtrl(self, 1, animation)
            else:
                self.agVideo = wx.animate.GIFAnimationCtrl(self, 1, animation, pos = (110,70))
            self.agVideo.Hide()
            
            if sys.platform == 'darwin':
                self.vsizer.Add(self.agVideo,0,wx.ALIGN_CENTRE_HORIZONTAL,0)
                self.vsizer.Add((0,10),0,0,0)
        else:
            self.agVideo = None
        
        if sys.platform == 'darwin':
            self.hsizermain.Add(self.vsizer,1,wx.ALIGN_CENTRE_HORIZONTAL,0)
            self.SetSizer(self.hsizermain)
            self.SetAutoLayout(1)
            self.Layout()
            self.Refresh()
            
        if self.vlcwrap is not None:
            wx.CallAfter(self.tell_vclwrap_window_for_playback)
        self.Refresh()

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

    def show_loading(self):
        if self.agVideo:
            self.logo = None
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
        halfx = 10
        halfy = 10
        lheight = 20

        dc.SetPen(wx.Pen(self.bg,0))
        dc.SetBrush(wx.Brush(self.bg))
        if sys.platform == 'linux2':
            dc.DrawRectangle(x,y,maxw,maxh)

        dc.SetTextForeground(wx.WHITE)
        dc.SetTextBackground(wx.BLACK)
        
        lineoffset = 120
        txty = halfy+lheight+lineoffset
        if txty > maxh:
            txty = 0

        if self.contentbm is not None:
            bmy = max(20,txty-20-self.contentbm.GetHeight())
            dc.DrawBitmap(self.contentbm,30,bmy,True)

        dc.EndDrawing()
        if evt is not None:
            evt.Skip(True)
