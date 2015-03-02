# Written by Fabian van der Werf and Arno Bakker
# see LICENSE.txt for license information
#
# EmbeddedPlayerPanel is the panel used in Tribler 5.0
# EmbeddedPlayer4FramePanel is the panel used in the SwarmPlayer / 4.5
#

import wx
import time
import logging
from threading import currentThread
from traceback import print_exc

from Tribler.Core.simpledefs import (NTFY_TORRENTS, NTFY_VIDEO_ENDED, DLSTATUS_HASHCHECKING, DLSTATUS_STOPPED_ON_ERROR,
                                     NTFY_VIDEO_BUFFERING, DLMODE_VOD)
from Tribler.Core.CacheDB.Notifier import Notifier

from Tribler.Main.vwxGUI import forceWxThread, warnWxThread, SEPARATOR_GREY, GRADIENT_DGREY, GRADIENT_LGREY
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager
from Tribler.Main.vwxGUI.widgets import (VideoProgress, FancyPanel, ActionButton, TransparentText, VideoVolume,
                                         VideoSlider)

from Tribler.Core.Video.defs import MEDIASTATE_PLAYING, MEDIASTATE_ENDED, MEDIASTATE_STOPPED, MEDIASTATE_PAUSED
from Tribler.Core.Video.VideoPlayer import VideoPlayer


class DelayTimer(wx.Timer):

    """ vlc.MediaCtrl needs some time to stop after we give it a stop command.
        Wait until it is and then tell it to play the new item
    """

    def __init__(self, embedplay):
        wx.Timer.__init__(self)
        self._logger = logging.getLogger(self.__class__.__name__)

        self.embedplay = embedplay
        self.Start(100)

    def Notify(self):
        if self.embedplay.GetState() != MEDIASTATE_PLAYING:
            self._logger.debug("embedplay: VLC has stopped playing previous video, starting it on new")
            self.Stop()
            self.embedplay.Play()
        else:
            self._logger.debug("embedplay: VLC is still playing old video")


class EmbeddedPlayerPanel(wx.Panel):

    """
    The Embedded Player consists of a VLCWindow and the media controls such
    as Play/Pause buttons and Volume Control.
    """

    VIDEO_SIZE = (320, 240)

    def __init__(self, parent, utility, vlcwrap, bg_color):
        wx.Panel.__init__(self, parent, -1)

        self._logger = logging.getLogger(self.__class__.__name__)

        self._gui_image_manager = GuiImageManager.getInstance()

        self.utility = utility
        self.guiutility = utility.guiUtility
        self.videoplayer = VideoPlayer.getInstance()
        self.parent = parent
        self.SetBackgroundColour(bg_color)

        self.fullscreenwindow = None
        self.download = None
        self.download_hash = None
        self.update = True
        self.timeoffset = None
        self.oldvolume = 0

        vSizer = wx.BoxSizer(wx.VERTICAL)

        self.vlcwrap = vlcwrap

        if vlcwrap:
            self.vlcwin = VLCWindow(self, vlcwrap)
            self.vlcwin.SetMinSize(EmbeddedPlayerPanel.VIDEO_SIZE)
            vSizer.Add(self.vlcwin, 1, wx.EXPAND, 0)

            self.logowin = LogoWindow(self)
            self.logowin.SetMinSize(EmbeddedPlayerPanel.VIDEO_SIZE)
            vSizer.Add(self.logowin, 1, wx.EXPAND, 0)

            self.ctrlpanel = FancyPanel(self, border=wx.TOP)
            self.ctrlpanel.SetMinSize((-1, 30))
            self.ctrlpanel.SetBorderColour(SEPARATOR_GREY)
            self.ctrlpanel.SetBackgroundColour(GRADIENT_LGREY, GRADIENT_DGREY)

            self.ctrlsizer = wx.BoxSizer(wx.HORIZONTAL)

            self.slider = VideoSlider(self.ctrlpanel)
            self.slider.Enable(False)
            self.timeposition = TransparentText(self.ctrlpanel, -1, "--:-- / --:--")

            self.bmp_muted = self._gui_image_manager.getImage(u"video_muted.png")
            self.bmp_unmuted = self._gui_image_manager.getImage(u"video_unmuted.png")
            self.mute = ActionButton(self.ctrlpanel, -1, self.bmp_unmuted)
            self.mute.Bind(wx.EVT_LEFT_UP, self.MuteClicked)

            self.bmp_pause = self._gui_image_manager.getImage(u"video_pause.png")
            self.bmp_play = self._gui_image_manager.getImage(u"video_play.png")
            self.ppbtn = ActionButton(self.ctrlpanel, -1, self.bmp_play)
            self.ppbtn.Bind(wx.EVT_LEFT_UP, self.PlayPause)
            self.ppbtn.Enable(False)

            self.sbtn = ActionButton(self.ctrlpanel, -1, self._gui_image_manager.getImage(u"video_stop.png"))
            self.sbtn.Bind(wx.EVT_LEFT_UP, self.OnStop)
            self.sbtn.Enable(False)

            self.volctrl = VideoVolume(self.ctrlpanel, -1)
            self.volctrl.SetVolumeHandler(self.OnVolumeChanged)
            self.volctrl.SetMinSize((30, 17))
            self.volctrl.Enable(False)

            self.fsbtn = ActionButton(self.ctrlpanel, -1, self._gui_image_manager.getImage(u"video_fullscreen.png"))
            self.fsbtn.Bind(wx.EVT_LEFT_UP, self.FullScreen)
            self.fsbtn.Enable(False)

            self.ctrlsizer.AddSpacer((10, -1))
            self.ctrlsizer.Add(self.ppbtn, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP, 1)
            self.ctrlsizer.AddSpacer((10, -1))
            self.ctrlsizer.Add(self.sbtn, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP, 1)
            self.ctrlsizer.AddSpacer((10, -1))
            self.ctrlsizer.Add(self.slider, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
            self.ctrlsizer.Add(self.timeposition, 0, wx.ALIGN_CENTER_VERTICAL)
            self.ctrlsizer.AddSpacer((10, -1))

            self.ctrlsizer.Add(self.mute, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP, 1)
            self.ctrlsizer.AddSpacer((5, -1))
            self.ctrlsizer.Add(self.volctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP, 1)
            self.ctrlsizer.AddSpacer((10, -1))
            self.ctrlsizer.Add(self.fsbtn, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP, 1)
            self.ctrlsizer.AddSpacer((10, -1))

            self.ctrlpanel.SetSizer(self.ctrlsizer)

            vSizer.Add(self.ctrlpanel, 0, wx.ALIGN_BOTTOM | wx.EXPAND)

            self.notifier = Notifier.getInstance()

        self.SetSizer(vSizer)

        self.playtimer = None
        self.timer = None

        if self.vlcwrap:
            self.SetMinSize((EmbeddedPlayerPanel.VIDEO_SIZE[0], -1))
            self.vlcwin.Show(True)
            self.logowin.Show(False)
            self.ctrlsizer.ShowItems(True)
            self.guiutility.frame.Layout()

            self.guiutility.library_manager.add_download_state_callback(self.OnStatesCallback)

            self.guiutility.utility.session.add_observer(self.OnVideoBuffering, NTFY_TORRENTS, [NTFY_VIDEO_BUFFERING])

            self.videoplayer.set_internalplayer_callback(self.LoadAndStartPlay)

    def OnVideoBuffering(self, subject, changeType, torrent_tuple):
        if not self:
            return

        download_hash, _, is_buffering = torrent_tuple
        if self.download and self.download.get_def().get_infohash() == download_hash:
            @forceWxThread
            def do_gui():
                if is_buffering:
                    self.Pause(gui_vod_event=True)
                else:
                    self.Resume()
            do_gui()

    def OnStatesCallback(self, dslist, magnetlist):
        if not self or not self.download:
            return

        for ds in dslist:
            if ds.get_download() == self.download and self.download.get_mode() == DLMODE_VOD:
                if ds.get_status() == DLSTATUS_HASHCHECKING:
                    progress = ds.get_progress()
                    label = 'Checking\n%d%%' % (progress * 100)
                elif ds.get_status() == DLSTATUS_STOPPED_ON_ERROR:
                    progress = 0
                    label = 'Loading\nfailed'
                else:
                    progress = ds.get_vod_prebuffering_progress()
                    label = 'Loading\n%d%%' % (progress * 100)

                pieces_complete = ds.get_pieces_complete() if ds.get_progress() < 1.0 else [True]
                self.UpdateStatus(label, progress, pieces_complete)

    def OnVolumeChanged(self, volume):
        if self.mute.GetBitmapLabel() == self.bmp_muted:  # unmute
            self.mute.SetBitmapLabel(self.bmp_unmuted, recreate=True)
        self.volume = volume
        self.oldvolume = self.volume
        self.SetVolume(self.volume)

    def MuteClicked(self, event):
        if self.mute.GetBitmapLabel() == self.bmp_muted:
            self.volume = self.oldvolume
        else:
            self.volume = 0

        self.volctrl.SetValue(self.volume)
        self.SetVolume(self.volume)
        self.mute.SetBitmapLabel(
            self.bmp_unmuted if self.mute.GetBitmapLabel() == self.bmp_muted else self.bmp_muted, recreate=True)

    @forceWxThread
    def LoadAndStartPlay(self, url, download):
        self.Load(url, download)
        self.StartPlay()

    @warnWxThread
    def Load(self, url, download):
        self._logger.debug("embedplay: Load: %s %s", url, currentThread().getName())

        self.download = download
        self.download_hash = download.get_def().get_infohash()

        # 19/02/10 Boudewijn: no self.slider when self.vlcwrap is None
        # 26/05/09 Boudewijn: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            self.slider.Enable(False)

            # Arno, 2009-02-17: If we don't do this VLC gets the wrong playlist somehow
            self.vlcwrap.stop()
            self.vlcwrap.load(url)

            # Enable update of progress slider
            wx.CallAfter(self.slider.SetValue, 0)
            if self.timer is None:
                self.timer = wx.Timer(self)
                self.Bind(wx.EVT_TIMER, self.UpdateSlider)
            self.timer.Start(500)

            self.volume = self.vlcwrap.sound_get_volume()
            self.oldvolume = self.vlcwrap.sound_get_volume()
            self.volctrl.SetValue(self.volume)
            self.volctrl.Enable(True)

        self.fsbtn.Enable(True)
        self.ppbtn.SetBitmapLabel(self.bmp_pause, recreate=True)
        self.ppbtn.Enable(True)
        self.sbtn.Enable(True)

    def StartPlay(self):
        """ Start playing the new item after VLC has stopped playing the old one """
        self._logger.debug("embedplay: PlayWhenStopped")

        self.playtimer = DelayTimer(self)

    @warnWxThread
    def Play(self, evt=None):
        self._logger.debug("embedplay: Play pressed")

        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            if self.GetState() != MEDIASTATE_PLAYING:
                self.vlcwrap.start()
                self.ppbtn.SetBitmapLabel(self.bmp_pause, recreate=True)
                self.ppbtn.Enable(True)
            else:
                self._logger.debug("embedplay: Play pressed, already playing")

    @warnWxThread
    def Pause(self, evt=None, gui_vod_event=False):
        self._logger.debug("embedplay: Pause pressed")

        if self.vlcwrap:
            if self.GetState() == MEDIASTATE_PLAYING:
                self.vlcwrap.pause()
            self.ppbtn.SetBitmapLabel(self.bmp_play, recreate=True)
            if gui_vod_event:
                self.ppbtn.Enable(False)
                self.ShowLoading()

    @warnWxThread
    def Resume(self, evt=None):
        self._logger.debug("embedplay: Resume pressed")

        if self.vlcwrap:
            if self.GetState() != MEDIASTATE_PLAYING:
                self.vlcwrap.resume()
            self.ppbtn.SetBitmapLabel(self.bmp_pause, recreate=True)
            self.ppbtn.Enable(True)
            self.slider.Enable(True)
            self.HideLoading()

    @warnWxThread
    def PlayPause(self, evt=None):
        self._logger.debug("embedplay: PlayPause pressed")

        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            if self.GetState() in [MEDIASTATE_ENDED, MEDIASTATE_STOPPED]:
                # Ensures that the related download also starts
                self.guiutility.library_manager.startLastVODTorrent()
            else:
                self.vlcwrap.resume()
                self.ppbtn.SetBitmapLabel(
                    self.bmp_play if self.ppbtn.GetBitmapLabel() == self.bmp_pause else self.bmp_pause, recreate=True)
                self.ppbtn.Enable(True)

    @warnWxThread
    def Seek(self, evt=None):
        self._logger.debug("embedplay: Seek")

        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            self.ppbtn.SetBitmapLabel(self.bmp_pause, recreate=True)
            self.ppbtn.Enable(self.download.get_progress() == 1.0)
            position = self.slider.GetValue()
            self.update = False

            try:
                self.Pause(gui_vod_event=True)
                self.videoplayer.seek(position)
                self.vlcwrap.set_media_position_relative(
                    position, self.GetState() in [MEDIASTATE_ENDED, MEDIASTATE_STOPPED])

                length = self.vlcwrap.get_stream_information_length()
                length = length / 1000 if length > 0 else self.videoplayer.get_vod_duration(self.download_hash)
                time_position = length * position
                self.timeoffset = time_position - (self.vlcwrap.get_media_position() / 1000)

                self.update = True
            except:
                print_exc()
                self._logger.debug('embedplay: Could not seek')

    def FullScreen(self, evt=None):
        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap and self.fsbtn.IsEnabled():
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

    @warnWxThread
    def _ToggleFullScreen(self):
        # saving media player state
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
            self.fullscreenwindow.Show()
            self.fullscreenwindow.ShowFullScreen(True)
            eventPanel.SetFocus()
            self.vlcwrap.set_window(self.fullscreenwindow)
        else:
            self.vlcwrap.set_window(self.vlcwin)
            self.fullscreenwindow.Destroy()
            self.fullscreenwindow = None

        # restoring state
        if cur_state == MEDIASTATE_PLAYING:
            self.vlcwrap.start(cur_time)

        elif cur_state == MEDIASTATE_PAUSED:
            self.vlcwrap.start(cur_time)

            def doPause(cur_time):
                self.vlcwrap.pause()
                self.vlcwrap.set_media_position(cur_time)
            wx.CallLater(500, doPause, cur_time)

    def SetVolume(self, volume, evt=None):
        self._logger.debug("embedplay: SetVolume: %s", self.volume)

        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            self.vlcwrap.sound_set_volume(volume)

    def OnStop(self, event=None):
        if self.vlcwrap and self.sbtn.IsEnabled():
            self.Stop()
            self.ppbtn.Enable(True)
            # Ensures that the related download also stops.
            self.guiutility.library_manager.stopLastVODTorrent()

    @forceWxThread
    def Stop(self):
        self._logger.debug("embedplay: Stop")

        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            self.vlcwrap.stop()
            self.timeposition.SetLabel('--:-- / --:--')
            self.slider.SetValue(0)
            self.timeoffset = None
            self.fsbtn.Enable(False)
            self.sbtn.Enable(False)
            self.ppbtn.SetBitmapLabel(self.bmp_play, recreate=True)
            self.slider.Enable(False)
            self.HideLoading()

            if self.timer is not None:
                self.timer.Stop()

    def GetState(self):
        """ Returns the state of VLC as summarized by Fabian:
        MEDIASTATE_PLAYING, MEDIASTATE_PAUSED, MEDIASTATE_ENDED, MEDIASTATE_STOPPED """

        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap:
            status = self.vlcwrap.get_our_state()
            self._logger.debug("embedplay: GetState %s", status)

            return status

        # catchall
        return MEDIASTATE_STOPPED

    def Reset(self):
        self.Stop()
        self.slider.SetPieces([])

    @forceWxThread
    def UpdateStatus(self, label, progress, pieces_complete):
        self.logowin.loading.SetValue(progress)
        self.logowin.loading.SetLabel(label)

        if self.vlcwrap:
            self.slider.SetPieces(pieces_complete)

    @warnWxThread
    def UpdateSlider(self, evt):
        # Boudewijn, 26/05/09: when using the external player we do not have a vlcwrap
        if self.vlcwrap and self.update:
            if self.GetState() not in [MEDIASTATE_ENDED, MEDIASTATE_STOPPED]:

                length = self.vlcwrap.get_stream_information_length()
                length = length / 1000 if length > 0 else self.videoplayer.get_vod_duration(self.download_hash)
                cur = self.vlcwrap.get_media_position() / 1000
                if length and self.timeoffset:
                    cur += self.timeoffset

                if cur >= 0 and length:
                    self.slider.SetValue(float(cur) / length)

                cur_str = self.FormatTime(float(cur)) if cur >= 0 else '--:--'
                length_str = self.FormatTime(length) if length else '--:--'
                self.timeposition.SetLabel('%s / %s' % (cur_str, length_str))
                self.ctrlsizer.Layout()
            elif self.GetState() == MEDIASTATE_ENDED:
                vp = VideoPlayer.getInstance()
                download, fileindex = (vp.get_vod_download(), vp.get_vod_fileindex())
                self.OnStop(None)
                if download:
                    self.notifier.notify(NTFY_TORRENTS, NTFY_VIDEO_ENDED, (
                        download.get_def().get_infohash(), fileindex))
                if self.fullscreenwindow:
                    self._ToggleFullScreen()

    def FormatTime(self, s):
        longformat = time.strftime('%d:%H:%M:%S', time.gmtime(s))
        if longformat.startswith('01:'):
            longformat = longformat[3:]
        while longformat.startswith('00:') and len(longformat) > len('00:00'):
            longformat = longformat[3:]
        return longformat

    def ShowLoading(self):
        if self.vlcwrap:
            self.logowin.loading.SetValue(0.0)
            self.logowin.show_loading()
            self.logowin.Show(True)
            self.vlcwin.Show(False)
            self.Layout()

    def HideLoading(self):
        if self.vlcwrap:
            self.logowin.hide_loading()
            self.logowin.Show(False)
            self.vlcwin.Show(True)
            self.Layout()

    def RecreateVLCWindow(self):
        if self.vlcwrap:
            vlcwin = VLCWindow(self, self.vlcwrap)
            vlcwin.SetMinSize(EmbeddedPlayerPanel.VIDEO_SIZE)
            vlcwin.Show(self.vlcwin.IsShown())
            self.GetSizer().Replace(self.vlcwin, vlcwin)
            self.vlcwin.Destroy()
            self.vlcwin = vlcwin


class VLCWindow(wx.Panel):

    """ A wx.Window to be passed to the vlc.MediaControl to draw the video in (normally). """

    def __init__(self, parent, vlcwrap):
        wx.Panel.__init__(self, parent)
        self.parent = parent
        self.SetBackgroundColour(wx.BLACK)
        self.vlcwrap = vlcwrap

        self.hsizermain = wx.BoxSizer(wx.HORIZONTAL)
        self.vsizer = wx.BoxSizer(wx.VERTICAL)
        self.hsizermain.Add(self.vsizer, 1, wx.CENTER)
        self.SetSizer(self.hsizermain)
        self.SetAutoLayout(1)
        self.Layout()

        self.vlcwrap.set_window(self)
        self.Refresh()

    def get_vlcwrap(self):
        return self.vlcwrap


class LogoWindow(wx.Panel):

    """ A wx.Window that can display the buffering progress when VLC is not playing. """

    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.parent = parent
        self.SetBackgroundColour(wx.BLACK)

        self.hsizermain = wx.BoxSizer(wx.HORIZONTAL)
        self.vsizer = wx.BoxSizer(wx.VERTICAL)

        self.loading = VideoProgress(self, -1)
        self.loading.Hide()
        self.loading.SetMinSize((300, 300))
        self.vsizer.Add(self.loading, 0, wx.CENTER | wx.RESERVE_SPACE_EVEN_IF_HIDDEN)

        self.hsizermain.Add(self.vsizer, 1, wx.CENTER)
        self.SetSizer(self.hsizermain)
        self.SetAutoLayout(1)
        self.Layout()
        self.Refresh()

    def show_loading(self):
        if self.loading:
            self.logo = None
            self.loading.Show()
            self.Refresh()

    def hide_loading(self):
        if self.loading:
            self.loading.Hide()
            self.Refresh()
