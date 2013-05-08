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
from Tribler.Video.Buttons import PlayerButton
from Tribler.Video.Progress import ProgressSlider
from Tribler.Main.vwxGUI.widgets import VideoProgress, FancyPanel, ActionButton

from Tribler.Main.vwxGUI import DEFAULT_BACKGROUND, forceWxThread, SEPARATOR_GREY, GRADIENT_DGREY, GRADIENT_LGREY

DEBUG = False

class EmbeddedPlayerPanel(wx.Panel):
    """
    The Embedded Player consists of a VLCLogoWindow and the media controls such
    as Play/Pause buttons and Volume Control.
    """

    VIDEO_SIZE = (320,240)

    def __init__(self, parent, utility, vlcwrap, bg, border = True):
        wx.Panel.__init__(self, parent, -1)

        self.__check_thread()

        self.utility = utility
        self.parent = parent
        self.border = border
        self.SetBackgroundColour(DEFAULT_BACKGROUND)

        self.volume = 0.48
        self.oldvolume = 0.48
        self.estduration = None

        self.fullscreen_enabled = False
        self.fullscreenwindow = None
        self.play_enabled = False
        self.stop_enabled = False
        self.scroll_enabled = False

        vSizer = wx.BoxSizer(wx.VERTICAL)
        if border:
            self.SetMinSize((34,-1))

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
        else:
            mainbox = vSizer

        self.vlcwrap = vlcwrap
        if vlcwrap is not None:
            self.vlcwin = VLCLogoWindow(self, utility, vlcwrap, bg, animate = True)
            self.vlcwin.SetMinSize(EmbeddedPlayerPanel.VIDEO_SIZE)

            if border:
                player_img = os.path.join(self.utility.getPath(), LIBRARYNAME,"Main","vwxGUI",'images','player.png')
                self.player_img = wx.StaticBitmap(self, -1, wx.BitmapFromImage(wx.Image(player_img, wx.BITMAP_TYPE_ANY)))
                mainbox.Add(self.player_img, 0, wx.ALIGN_CENTER|wx.TOP, 5)
            mainbox.Add(self.vlcwin, 1, wx.EXPAND, 0)

            self.ctrlpanel = FancyPanel(self, border = wx.TOP)
            self.ctrlpanel.SetMinSize((-1, 30))
            self.ctrlpanel.SetBorderColour(SEPARATOR_GREY)
            self.ctrlpanel.SetBackgroundColour(GRADIENT_LGREY, GRADIENT_DGREY)

            self.ctrlsizer = wx.BoxSizer(wx.HORIZONTAL)

            self.slider = ProgressSlider(self.ctrlpanel, self.utility)
            self.slider.SetRange(0,1)
            self.slider.SetValue(0)

            self.bmp_muted = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","mtEnabled.png"))
            self.bmp_unmuted = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","mt.png"))
            self.mute = ActionButton(self.ctrlpanel, -1, self.bmp_unmuted)
            self.mute.Bind(wx.EVT_LEFT_UP, self.MuteClicked)

            self.bmp_pause = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Video","Images","pause.png"))
            self.bmp_play = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Video","Images","play.png"))
            self.ppbtn = ActionButton(self.ctrlpanel, -1, self.bmp_pause)
            self.ppbtn.Bind(wx.EVT_LEFT_UP, self.PlayPause)
            self.ppbtn.Enable(False)

            self.sbtn = ActionButton(self.ctrlpanel, -1, wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Video","Images","stop.png")))
            self.sbtn.Bind(wx.EVT_LEFT_UP, self.OnStop)
            self.sbtn.Enable(False)

            volumebox = wx.BoxSizer(wx.HORIZONTAL)
            self.vol1 = PlayerButton(self.ctrlpanel,os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'vol1')
            self.vol1.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

            self.vol2 = PlayerButton(self.ctrlpanel,os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'vol2')
            self.vol2.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

            self.vol3 = PlayerButton(self.ctrlpanel,os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'vol3')
            self.vol3.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

            self.vol4 = PlayerButton(self.ctrlpanel,os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'vol4')
            self.vol4.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

            self.vol5 = PlayerButton(self.ctrlpanel,os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'vol5')
            self.vol5.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

            self.vol6 = PlayerButton(self.ctrlpanel,os.path.join(self.utility.getPath(), LIBRARYNAME,'Video', 'Images'), 'vol6')
            self.vol6.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)

            volumebox.Add(self.vol1, 0, wx.ALIGN_CENTER_VERTICAL)
            volumebox.Add(self.vol2, 0, wx.ALIGN_CENTER_VERTICAL)
            volumebox.Add(self.vol3, 0, wx.ALIGN_CENTER_VERTICAL)
            volumebox.Add(self.vol4, 0, wx.ALIGN_CENTER_VERTICAL)
            volumebox.Add(self.vol5, 0, wx.ALIGN_CENTER_VERTICAL)
            volumebox.Add(self.vol6, 0, wx.ALIGN_CENTER_VERTICAL)
            self.updateVol(self.volume)

            self.fsbtn = ActionButton(self.ctrlpanel, -1, wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Video","Images","fullScreen.png")))
            self.fsbtn.Bind(wx.EVT_LEFT_UP, self.FullScreen)
            self.fsbtn.Enable(False)

            self.ctrlsizer.Add(self.ppbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
            self.ctrlsizer.Add(self.sbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
            self.ctrlsizer.Add(self.slider, 1, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)

            self.ctrlsizer.Add(self.mute, 0, wx.ALIGN_CENTER_VERTICAL)
            self.ctrlsizer.Add(volumebox, 0, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
            self.ctrlsizer.Add(self.fsbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
            
            self.ctrlpanel.SetSizer(self.ctrlsizer)

            mainbox.Add(self.ctrlpanel, 0, wx.ALIGN_BOTTOM|wx.EXPAND)
            if border:
                self.vlcwin.Show(False)
                self.ctrlsizer.ShowItems(False)

        # Arno: until we figure out how to show in-playback prebuffering info
        self.statuslabel = wx.StaticText(self)
        vSizer.Add(self.statuslabel, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 5)
        self.SetSizer(vSizer)

        self.playtimer = None
        self.update = False
        self.timer = None

        if self.vlcwrap and self.border:
            self.SetMinSize((EmbeddedPlayerPanel.VIDEO_SIZE[0],-1))

            self.vlcwin.Show(True)
            self.ctrlsizer.ShowItems(True)
            self.statuslabel.Show(True)
            self.player_img.Show(False)

            self.utility.guiUtility.frame.Layout()

    def mouseAction(self,event):
        if event.LeftDown():
            if self.mute.GetBitmapLabel() == self.bmp_muted: # unmute
                self.mute.SetBitmapLabel(self.bmp_unmuted, recreate = True)
            if event.GetEventObject().GetImageName() == 'vol1':
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
        if self.mute.GetBitmapLabel() == self.bmp_muted:
            self.volume = self.oldvolume
        else:
            self.volume = 0

        self.updateVol(self.volume)
        self.SetVolume(self.volume)
        self.mute.SetBitmapLabel(self.bmp_unmuted if self.mute.GetBitmapLabel() == self.bmp_muted else self.bmp_muted, recreate = True)

    def updateVol(self,volume): # updates the volume bars in the gui
        self.vol1.setSelected(volume >= 0.16)
        self.vol2.setSelected(volume >= 0.32)
        self.vol3.setSelected(volume >= 0.48)
        self.vol4.setSelected(volume >= 0.64)
        self.vol5.setSelected(volume >= 0.80)
        self.vol6.setSelected(volume >= 1.00)

    def Load(self,url,streaminfo = None):
        self.__check_thread()

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
            self.timer.Start(500)

        self.enableFullScreen()
        self.enablePlay()
        self.enableStop()
#        self.enableScroll()

    def StartPlay(self):
        """ Start playing the new item after VLC has stopped playing the old
        one
        """
        if DEBUG:
            print >>sys.stderr,"embedplay: PlayWhenStopped"
        self.playtimer = DelayTimer(self)

    def Play(self, evt=None):
        self.__check_thread()

        if DEBUG:
            print >>sys.stderr,"embedplay: Play pressed"

        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            if self.GetState() != MEDIASTATE_PLAYING:
                self.vlcwin.stop_animation()

                self.ppbtn.SetBitmapLabel(self.bmp_pause, recreate = True)
                self.vlcwrap.start()
            elif DEBUG:
                print >>sys.stderr,"embedplay: Play pressed, already playing"

    def Pause(self, evt=None):
        self.__check_thread()

        """ Toggle between playing and pausing of current item """
        if DEBUG:
            print >>sys.stderr,"embedplay: Pause pressed"

        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            if self.GetState() == MEDIASTATE_PLAYING:
                self.ppbtn.SetBitmapLabel(self.bmp_play, recreate = True)
                self.vlcwrap.pause()
            elif DEBUG:
                print >>sys.stderr,"embedplay: Pause pressed, not playing"


    def Resume(self, evt=None):
        self.__check_thread()

        if DEBUG:
            print >>sys.stderr,"embedplay: Resume pressed"

        if self.vlcwrap:
            if self.GetState() != MEDIASTATE_PLAYING:
                self.vlcwin.stop_animation()
                self.ppbtn.SetBitmapLabel(self.bmp_pause, recreate = True)
                self.vlcwrap.resume()

    def PlayPause(self, evt=None):
        self.__check_thread()

        """ Toggle between playing and pausing of current item """
        if DEBUG:
            print >>sys.stderr,"embedplay: PlayPause pressed"

        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            self.vlcwrap.resume()
            self.ppbtn.SetBitmapLabel(self.bmp_play if self.ppbtn.GetBitmapLabel() == self.bmp_pause else self.bmp_pause, recreate = True)

    def Seek(self, evt=None):
        self.__check_thread()

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
        self.ppbtn.Enable(True)

    def disablePlay(self):
        self.play_enabled = False
        self.ppbtn.Enable(False)

    def enableStop(self):
        self.stop_enabled = True
        self.sbtn.Enable(True)

    def disableStop(self):
        self.stop_enabled = False
        self.sbtn.Enable(False)

    def enableFullScreen(self):
        self.fullscreen_enabled = True
        self.fsbtn.Enable(True)

    def disableFullScreen(self):
        self.fullscreen_enabled = False
        self.fsbtn.Enable(False)

    def FullScreen(self, evt=None):
        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap and self.fullscreen_enabled:
            self._ToggleFullScreen()

    def OnFullScreenKey(self, event):
        if event.GetUnicodeKey() == wx.WXK_ESCAPE:
            self._ToggleFullScreen()

        elif event.GetUnicodeKey() == wx.WXK_SPACE:
            self._TogglePause()

    def _TogglePause(self):
        if self.GetState() == MEDIASTATE_PLAYING:
            self.vlcwrap.pause()
        else:
            self.vlcwrap.resume()

    def _ToggleFullScreen(self):
        self.__check_thread()

        if isinstance(self.parent, wx.Frame): #are we shown in popup frame
            if self.ctrlsizer.IsShown(0): #we are not in fullscreen -> ctrlsizer is showing
                self.parent.ShowFullScreen(True)
                self.ctrlsizer.ShowItems(False)
                self.statuslabel.Show(False)
                self.Layout()

                #Niels: 07-03-2012, only evt_close seems to work :(
                quitId = wx.NewId()
                pauseId = wx.NewId()
                self.parent.Bind(wx.EVT_MENU, lambda event: self._ToggleFullScreen(), id = quitId)
                self.parent.Bind(wx.EVT_MENU, lambda event: self._TogglePause(), id = pauseId)

                self.parent.Bind(wx.EVT_CLOSE, lambda event: self._ToggleFullScreen())
                self.parent.Bind(wx.EVT_LEFT_DCLICK, lambda event: self._ToggleFullScreen())

                accelerators = [(wx.ACCEL_NORMAL, wx.WXK_ESCAPE, quitId), (wx.ACCEL_CTRL, wx.WXK_SPACE, pauseId)]
                self.parent.SetAcceleratorTable(wx.AcceleratorTable(accelerators))
            else:
                self.parent.ShowFullScreen(False)
                self.ctrlsizer.ShowItems(True)
                self.statuslabel.Show(True)
                self.Layout()

                self.parent.SetAcceleratorTable(wx.NullAcceleratorTable)
                self.parent.Unbind(wx.EVT_CLOSE)
        else:
            #saving media player state
            cur_time = self.vlcwrap.get_media_position()
            cur_state = self.vlcwrap.get_our_state()

            self.vlcwrap.stop()
            if not self.fullscreenwindow:
                # create a new top level frame where to attach the vlc widget and
                # render the fullscreen video
                self.fullscreenwindow = wx.Frame(None, title="FullscreenVLC")
                self.fullscreenwindow.SetBackgroundColour("BLACK")

                eventPanel = wx.Panel(self.fullscreenwindow)
                eventPanel.SetBackgroundColour(wx.BLACK)
                eventPanel.Bind(wx.EVT_KEY_DOWN, lambda event: self.OnFullScreenKey(event))
                self.fullscreenwindow.Bind(wx.EVT_CLOSE, lambda event: self._ToggleFullScreen())
                self.fullscreenwindow.ShowFullScreen(True)
                eventPanel.SetFocus()
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

    def OnStop(self, event):
        if self.vlcwrap and self.stop_enabled:
            self.Stop()
            self.disableStop()

    def Stop(self):
        self.__check_thread()

        if DEBUG:
            print >> sys.stderr, "embedplay: Stop"

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
            status = self.vlcwrap.get_our_state()
            if DEBUG:
                print >>sys.stderr,"embedplay: GetState",status

            return status

        # catchall
        return MEDIASTATE_STOPPED

    def Reset(self):
        self.Stop()
        self.UpdateProgressSlider([False])

    #
    # Control on-screen information
    #
    @forceWxThread
    def UpdateStatus(self,playerstatus,pieces_complete,vod_progress):
        self.SetPlayerStatus(playerstatus,vod_progress)
        if self.vlcwrap is not None:
            self.UpdateProgressSlider(pieces_complete)

    def SetPlayerStatus(self,text,progress):
        self.SetLoadingText(text)
        self.SetProgress(progress)

    def SetContentName(self,s):
        self.vlcwin.set_content_name(s)

    def SetContentImage(self,wximg):
        self.vlcwin.set_content_image(wximg)

    def SetLoadingText(self,text):
        if text == None:
            text = ''

        if text != self.statuslabel.GetLabel():
            self.statuslabel.SetLabel(text)
            if sys.platform == 'win32':
                self.statuslabel.Wrap(self.GetClientSize().width)
            self.statuslabel.Refresh()
            self.Layout()

    def SetProgress(self,progress):
        self.vlcwin.loading.SetValue(progress)

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

        self.ppbtn.Enable(False)
        # 19/02/10 Boudewijn: no self.slider when self.vlcwrap is None
        if self.vlcwrap:
            self.slider.Disable()
        self.fsbtn.Enable(False)

    def UpdateSlider(self, evt):
        self.__check_thread()

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

    def __check_thread(self):
        if __debug__ and not wx.Thread_IsMain():
            print  >> sys.stderr,"EmbeddedPlayer: __check_thread thread",currentThread().getName(),"is NOT MainThread"
            print_stack()

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

        self.contentname = None
        self.contentbm = None
        self.hsizermain = wx.BoxSizer(wx.HORIZONTAL)
        self.vsizer = wx.BoxSizer(wx.VERTICAL)

        if animate:
            self.loading = VideoProgress(self, -1)
            self.loading.Hide()
            self.loading.SetMinSize((300, 300))

            self.vsizer.Add(self.loading, 0, wx.CENTER|wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        else:
            self.loading = None

        self.hsizermain.Add(self.vsizer, 1, wx.CENTER)
        self.SetSizer(self.hsizermain)
        self.SetAutoLayout(1)
        self.Layout()

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

    def show_loading(self):
        if self.loading:
            self.logo = None
            self.loading.Show()
            self.Refresh()

    def stop_animation(self):
        if self.loading:
            self.loading.Hide()
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

#Niels: this is a wrapper to make wx.media.mediactrl respond to the vlcwrap commands
#Unfortunately it does not work on linux and mac, making it useless
#import wx.media
#self.vlcwin = wx.media.MediaCtrl(self)
#self.vlcwrap = FakeVlc(self.vlcwin)
#
#def fake():
#    pass
#self.vlcwin.show_loading = fake
#self.vlcwin.tell_vclwrap_window_for_playback = fake
#self.vlcwin.stop_animation = fake
#
#class FakeVlc():
#    def __init__(self, mediactrl):
#        self.mediactrl = mediactrl
#        self.mediactrl.Bind(wx.media.EVT_MEDIA_LOADED, self.OnLoaded)
#
#    def stop(self):
#        print >> sys.stderr, "Stop"
#        self.mediactrl.Stop()
#
#    def playlist_clear(self):
#        pass
#
#    def load(self, url, streaminfo):
#        print >> sys.stderr, "Load", url
#        self.mediactrl.LoadFromURI(url)
#        wx.CallLater(1000, self.OnLoaded, None)
#
#    def OnLoaded(self, event):
#        print >> sys.stderr, "Loaded", event
#        self.start()
#
#    def start(self, startposition = 0):
#        print >> sys.stderr, "Play"
#
#        if self.mediactrl.Play():
#            if startposition != 0:
#                self.mediactrl.Seek(startposition)
#        else:
#            print >> sys.stderr, "Play returned False"
#
#    def pause(self):
#        print >> sys.stderr, "Pause"
#        self.mediactrl.Pause()
#
#    def resume(self):
#        if self.get_our_state() == MEDIASTATE_PLAYING:
#            self.pause()
#        else:
#            self.start()
#
#    def set_media_position(self, pos):
#        print >> sys.stderr, "Seek"
#        self.mediactrl.Seek(pos)
#
#    def get_media_position(self):
#        return self.mediactrl.Tell()
#
#    def get_our_state(self):
#        state = self.mediactrl.GetState()
#        if state == wx.media.MEDIASTATE_STOPPED:
#            return MEDIASTATE_STOPPED
#
#        if state == wx.media.MEDIASTATE_PAUSED:
#            return MEDIASTATE_PAUSED
#
#        if state == wx.media.MEDIASTATE_PLAYING:
#            return MEDIASTATE_PLAYING
#
#    def get_stream_information_length(self):
#        return self.mediactrl.Length()
#
#    def sound_set_volume(self, vol):
#        self.mediactrl.SetVolume(vol)
