# Written by Fabian van der Werf and Arno Bakker
# see LICENSE.txt for license information

import wx
import sys

import vlc

import os
import time
import traceback
from time import sleep
from tempfile import mkstemp
from threading import currentThread,Event
from traceback import print_stack,print_exc
from Progress import ProgressBar
from Tribler.Main.vwxGUI.tribler_topButton import *



# Fabian: can't use the constants from wx.media since 
# those all yield 0 (for my wx)
# Arno: These modes are not what vlc returns, but Fabian's summary of that
MEDIASTATE_PLAYING = 1
MEDIASTATE_PAUSED  = 2
MEDIASTATE_STOPPED = 3

vlcstatusmap = {vlc.PlayingStatus:'vlc.PlayingStatus',
                vlc.PauseStatus:'vlc.PauseStatus',
                vlc.ForwardStatus:'vlc.ForwardStatus',
                vlc.BackwardStatus:'vlc.BackwardStatus',
                vlc.InitStatus:'vlc.InitStatus',
                vlc.EndStatus:'vlc.EndStatus',
                vlc.UndefinedStatus:'vlc.UndefinedStatus'}

DEBUG = True


class VideoItem:
    
    def __init__(self,path):
        self.path = path
        
    def getPath(self):
        return self.path


class VideoFrame(wx.Frame):
    
    def __init__(self,parent):
        self.utility = parent.utility
        wx.Frame.__init__(self, None, -1, self.utility.lang.get('tb_video_short'), 
                          size=(800,525)) # Use 16:9 aspect ratio: 500 = (800/16) * 9 + 50 for controls
        self.createMainPanel()


        iconpath = os.path.join(self.utility.getPath(),'Tribler','Images','tribler.ico')
        self.icons = wx.IconBundle()
        self.icons.AddIconFromFile(iconpath,wx.BITMAP_TYPE_ICO)
        self.SetIcons(self.icons)

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

    def createMainPanel(self):
        oldcwd = os.getcwd()
        if sys.platform == 'win32':
            global vlcinstalldir
            vlcinstalldir = os.path.join(self.utility.getPath(),"vlc")
            os.chdir(vlcinstalldir)

        self.showingvideo = False
        self.videopanel = EmbeddedPlayer(self, -1, self, False, self.utility)
        #self.videopanel.Hide()
        self.Hide()
        # Arno, 2007-04-02: There is a weird problem with stderr when using VLC on Linux
        # see Tribler\Video\vlcmedia.py:VLCMediaCtrl. Solution is to sleep 1 sec here.
        # Arno: 2007-04-23: Appears to have been caused by wx.SingleInstanceChecker
        # in wxPython-2.8.1.1.
        #
        #if sys.platform == 'linux2':
        #    print "Sleeping for a few seconds to allow VLC to initialize"
        #    sleep(5)
            
        if sys.platform == 'win32':
            os.chdir(oldcwd)

    def OnCloseWindow(self, event = None):
        self.swapout_videopanel()        
        

    def swapin_videopanel(self,url,play=True):
        
        if DEBUG:
            print >>sys.stderr,"videoframe: Swap IN videopanel"
        
        if not self.showingvideo:
            self.showingvideo = True
            self.Show()
            
        self.Raise()
        self.SetFocus()

        self.item = VideoItem(url)
        self.videopanel.SetItem(self.item,play=play)

    def swapout_videopanel(self):
        
        if DEBUG:
            print >>sys.stderr,"videoframe: Swap OUT videopanel"
        
        self.videopanel.reset()
        if self.showingvideo:
            self.showingvideo = False
            self.Hide()

    def reset_videopanel(self):
        self.videopanel.reset()
        
    def set_player_status(self,s):
        """ Called by any thread """
        if self.videopanel:
            self.videopanel.set_player_status(s)

    def set_content_name(self,name):
        """ Called by any thread """
        if self.videopanel:
            self.videopanel.set_content_name(name)
        

class EmbeddedPlayer(wx.Panel):

    def __init__(self, parent, id, closehandler, allowclose, utility):
        wx.Panel.__init__(self, parent, id)
        self.item = None
        self.status = 'Loading player...'

        self.closehandler = closehandler
        self.utility = utility
        #self.SetBackgroundColour(wx.WHITE)
        self.SetBackgroundColour(wx.BLACK)

        logofilename = os.path.join(self.utility.getPath(),'Tribler','Images','logo4video.png')
        #logofilename = None

        mainbox = wx.BoxSizer(wx.VERTICAL)
        self.mediactrl = VLCMediaCtrl(self, -1,logofilename)

        # TEMP ARNO: until we figure out how to show in-playback prebuffering info
        self.statuslabel = wx.StaticText(self, -1, self.status )
        self.statuslabel.SetForegroundColour(wx.WHITE)
        
        ctrlsizer = wx.BoxSizer(wx.HORIZONTAL)        
        self.slider = wx.Slider(self, -1)
        #self.slider.SetBackgroundColor(wx.BLACK)
        self.slider.Bind(wx.EVT_SCROLL_THUMBRELEASE, self.Seek)
        self.slider.Bind(wx.EVT_SCROLL_THUMBTRACK, self.stopSliderUpdate)
        self.slider.SetRange(0,1)
        self.slider.SetValue(0)
        ctrlsizer.Add(self.slider, 1, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
        
        #self.ppbtn = tribler_topButton(self, name="playerPause")
        self.ppbtn = wx.Button(self, -1, self.utility.lang.get('playprompt'))
        #self.ppbtn.setBackground(wx.BLACK)
        self.ppbtn.Bind(wx.EVT_BUTTON, self.PlayPause)

        self.volumebox = wx.BoxSizer(wx.HORIZONTAL)
        self.volumetext = wx.StaticText(self, -1, self.utility.lang.get('volumeprompt'))        
        self.volume = wx.Slider(self, -1)
        self.volume.SetRange(0, 100)
        self.volume.Bind(wx.EVT_SCROLL_THUMBTRACK, self.SetVolume)
        self.volumebox.Add(self.volumetext, 0, wx.ALIGN_CENTER_VERTICAL)
        self.volumebox.Add(self.volume, 1, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)

        self.fsbtn = wx.Button(self, -1, self.utility.lang.get('fullscreen'))
        self.fsbtn.Bind(wx.EVT_BUTTON, self.FullScreen)

        ctrlsizer.Add(self.ppbtn, 0, wx.ALIGN_CENTER_VERTICAL)
        ctrlsizer.Add(self.volumebox, 1, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
        ctrlsizer.Add(self.fsbtn, 0, wx.ALIGN_CENTER_VERTICAL)
        mainbox.Add(self.mediactrl, 1, wx.EXPAND, 1)
        mainbox.Add(self.statuslabel, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 30)
        mainbox.Add(ctrlsizer, 0, wx.ALIGN_BOTTOM|wx.EXPAND, 1)
        self.SetSizerAndFit(mainbox)
        
        self.playtimer = None
        self.bitrateset = False
        self.update = False
        self.timer = None
        
    def SetItem(self, item, play = True):
        self.item = item
        if DEBUG:
            print >>sys.stderr,"embedplay: Telling player to play",item.getPath(),currentThread().getName()
        self.mediactrl.Load(self.item.getPath())
        self.update = True
        wx.CallAfter(self.slider.SetValue,0)
        
        if self.timer is None:
            self.timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.updateSlider)
        self.timer.Start(200)
        
        if play:
            self.playtimer = DelayTimer(self)


    def enableInput(self):
        self.ppbtn.Enable(True)
        self.slider.Enable(True)
        self.fsbtn.Enable(True)


    def disableInput(self):
        return # Not currently used
        
        self.ppbtn.Disable()
        self.slider.Disable()
        self.fsbtn.Disable()

    def reset(self):
        self.disableInput()
        self.Stop()

    def updateSlider(self, evt):
        self.volume.SetValue(int(self.mediactrl.GetVolume() * 100))

        #s = self.mediactrl.GetState()

        if self.update:
            len = self.mediactrl.Length()
            if len == -1:
                return
            len /= 1000

            cur = self.mediactrl.Tell() / 1000

            self.slider.SetRange(0, len)
            self.slider.SetValue(cur)

    def stopSliderUpdate(self, evt):
        self.update = False


    def Seek(self, evt):
        if self.item == None:
            return
        
        oldsliderpos = self.slider.GetValue()
        pos = oldsliderpos * 1000
        
        if DEBUG:
            print >>sys.stderr,"embedplay: Seek", pos
        try:
            self.mediactrl.Seek(pos)
        except vlc.InvalidPosition,e:
            self.slider.SetValue(oldsliderpos)
        self.update = True
        

    def PlayPause(self, evt=None):
        if self.mediactrl.GetState() == MEDIASTATE_PLAYING:
            self.ppbtn.SetLabel(self.utility.lang.get('playprompt'))
            self.mediactrl.Pause()
        else:
            self.ppbtn.SetLabel(self.utility.lang.get('pauseprompt'))
            self.mediactrl.Play()

    def FullScreen(self,evt=None):
        self.mediactrl.FullScreen()

    def SetVolume(self, evt):
        self.mediactrl.SetVolume(float(self.volume.GetValue()) / 100)

    """
    def run(self):
        while not self.stop.isSet():
            evt = UpdateEvent(self.GetId())
            wx.PostEvent(self, evt)
            self.stop.wait(0.2)
    """

    def Stop(self):
        self.ppbtn.SetLabel(self.utility.lang.get('playprompt'))
        self.mediactrl.Stop()
        if self.timer is not None:
            self.timer.Stop()
        self.bitrateset = False

    def __del__(self):
        self.Stop()
        wx.Panel.__del__(self)


    def CloseWindow(self,event=None):
        self.Stop()
        self.closehandler.swapout_videopanel()


    def set_player_status(self,s):
        #if self.mediactrl:
        #    self.mediactrl.setStatus(s)
        wx.CallAfter(self.OnSetStatus,s)
        
    def OnSetStatus(self,s):
        self.status = s
        self.statuslabel.SetLabel(self.status)

    def set_content_name(self,s):
        if self.mediactrl:
            self.mediactrl.setContentName(s)


class DelayTimer(wx.Timer):
    """ vlc.MediaCtrl needs some time to stop after we give it a stop command.
        Wait until it is and then tell it to play the new item
    """
    def __init__(self,embedplay):
        wx.Timer.__init__(self)
        self.embedplay = embedplay
        self.Start(100)
        
    def Notify(self):
        if self.embedplay.mediactrl.GetState() != MEDIASTATE_PLAYING:
            if DEBUG:
                print >>sys.stderr,"embedplay: VLC has stopped playing previous video, starting it on new"
            self.Stop()
            self.embedplay.PlayPause()
        elif DEBUG:
            print >>sys.stderr,"embedplay: VLC is still playing old video"



VLC_MAXVOL = 200

class VLCMediaCtrl(wx.Window):
    def __init__(self, parent, id, logofilename):

        wx.Window.__init__(self, parent, id, size=(320,240))
        self.SetMinSize((320,240))
        self.SetBackgroundColour(wx.BLACK)
        self.status = "Player is loading..."
        self.name = None

        if logofilename is not None:
            self.logo = wx.BitmapFromImage(wx.Image(logofilename),-1)
            self.Bind(wx.EVT_PAINT, self.OnPaint)

        #
        # Arno, 2007-04-02: On Linux (Centos 4.4) with vlc 0.8.6a I get a weird 
        # problem. When vlc is loaded the main Tribler gets IOErrors while writing
        # to stderr. It is unclear what the cause of these errors is. 
        # 
        # What appears to work is to have the MainThread sleep 1 second after it
        # created the VLC control and using "--verbose 0 --logile X" as parameters.
        #
        # Arno, 2007-05-08: The problem with stderr appears to be caused by wx.SingleInstanceChecker
        # for wxWidgets 2.8.0.1
        #
        #[loghandle,logfilename] = mkstemp("vlc-log")
        #os.close(loghandle)
        #self.media = vlc.MediaControl(["--verbose","0","--logfile",logfilename,"--key-fullscreen","Esc"])
        #self.media = vlc.MediaControl(["--key-fullscreen","Esc"])
        #self.media = vlc.MediaControl()
        self.getVlcMediaCtrl()

    def getVlcMediaCtrl(self):
        if sys.platform == 'win32':
                cwd = os.getcwd()
                os.chdir(vlcinstalldir)

        # Arno: 2007-05-11: Don't ask me why but without the "--verbose=0" vlc will ignore the key redef.
        params = ["--verbose=0"]
        params += ["--key-fullscreen", "Esc"]
        params += ["--no-drop-late-frames"] # Arno: 2007-11-19: don't seem to work as expected DEBUG
        params += ["--no-skip-frames"]
        params += ["--quiet-synchro"]
        
        if sys.platform == 'darwin':
            params += ["--plugin-path", "%s/lib/vlc" % (
                 # location of plugins: next to tribler.py
                 os.path.abspath(os.path.dirname(sys.argv[0]))
                 )]
        self.media = vlc.MediaControl(params)

        self.visinit = False

        if sys.platform == 'win32':
                os.chdir(cwd)
        

    # Be sure that this window is visible before
    # calling Play(), otherwise GetHandle() fails
    def Play(self):
        #self.setStatus("Player is loading...")
        if self.GetState() == MEDIASTATE_PLAYING:
            return

        if not self.visinit:
            xid = self.GetHandle()
            if sys.platform == 'darwin':
                self.media.get_vlc_instance().video_set_macosx_parent_type(1)
            self.media.set_visual(xid)
            self.visinit = True

        if self.GetState() == MEDIASTATE_STOPPED:
            pos = vlc.Position()
            pos.origin = vlc.AbsolutePosition
            pos.key = vlc.MediaTime
            pos.value = 0
            if DEBUG:
                print >>sys.stderr,"VLCMediaCtrl: Actual play command"
            self.media.start(pos)
        else:
            if DEBUG:
                print >>sys.stderr,"VLCMediaCtrl: Actual resume command"
            self.media.resume()


    def Length(self):
        if self.GetState() == MEDIASTATE_STOPPED:
            return -1
        else:
            return self.media.get_stream_information()["length"]
    

    def Tell(self):
        if self.GetState() == MEDIASTATE_STOPPED:
            return 0
        else:
            return self.media.get_media_position(vlc.AbsolutePosition, vlc.MediaTime).value


    def GetState(self):
        status = self.media.get_stream_information()["status"]
        #if DEBUG:
        #    print "VLCMediaCtrl: VLC reports status",status,vlcstatusmap[status]
        if status == vlc.PlayingStatus:
            return MEDIASTATE_PLAYING
        elif status == vlc.PauseStatus:
            return MEDIASTATE_PAUSED
        else:
            return MEDIASTATE_STOPPED


    def Load(self,url):
        self.media.exit()
        self.getVlcMediaCtrl()
        #self.Stop()
        #self.media.playlist_clear()
        #self.visinit = False
        #self.media = vlc.MediaControl()# ["--key-fullscreen","Esc"])
        self.media.playlist_add_item(url)


    def Pause(self):
        self.media.pause()


    def Seek(self, where, mode = wx.FromStart):
        """ Arno: For some files set_media_position() doesn't work. Subsequent get_media_positions()
            then do not return the right value always
        """
        pos = vlc.Position() 

        if mode == wx.FromStart:
            pos.origin = vlc.AbsolutePosition
            pos.key = vlc.MediaTime
            pos.value = where
        elif mode == wx.FromCurrent:
            pos.origin = vlc.RelativePosition
            pos.key = vlc.MediaTime
            pos.value = where
        elif mode == wx.FromEnd:
            pos.origin = vlc.AbsolutePosition
            pos.key = vlc.MediaTime
            pos.value = self.Length() - where

        if self.GetState() == MEDIASTATE_STOPPED:
            self.media.start(pos)
        else:
            self.media.set_media_position(pos)

    def Stop(self):
        self.media.stop()
        self.media.playlist_clear()
        self.setStatus("Player is stopped")


    def __del__(self):
        self.media.exit()


    def SetVolume(self, dVolume):
        vol = int(dVolume * VLC_MAXVOL)
        self.media.sound_set_volume(vol)


    def GetVolume(self):
        vol = self.media.sound_get_volume()
        return float(vol) / VLC_MAXVOL

    def FullScreen(self):
        self.media.set_fullscreen(1)
        
        
    def OnPaint(self,evt):
        dc = wx.PaintDC(self)
        dc.Clear()
        dc.BeginDrawing()        

        x,y,maxw,maxh = self.GetClientRect()
        halfx = (maxw-x)/2
        halfy = (maxh-y)/2
        halfx -= self.logo.GetWidth()/2
        halfy -= self.logo.GetHeight()/2

        dc.SetPen(wx.Pen("#BLACK",0))
        dc.SetBrush(wx.Brush("BLACK"))
        if sys.platform == 'linux2':
            dc.DrawRectangle(x,y,maxw,maxh)
        dc.DrawBitmap(self.logo,halfx,halfy,True)

        dc.SetTextForeground(wx.WHITE)
        dc.SetTextBackground(wx.BLACK)
        
        lineoffset = 80
        name = self.getContentName() 
        if name is not None:
            txt = u'Loading: '+self.name
            dc.DrawText(txt,30,halfy+self.logo.GetHeight()+lineoffset)
            lineoffset += 20

        #txt = self.getStatus()
        #dc.DrawText(txt,30,halfy+self.logo.GetHeight()+lineoffset)
        
        dc.EndDrawing()
        if evt is not None:
            evt.Skip(True)
        
    def getStatus(self):
        return self.status
    
    def setStatus(self,s):
        wx.CallAfter(self.OnSetStatus,s)
        
    def OnSetStatus(self,s):
        self.status = s
        if self.GetState() == MEDIASTATE_STOPPED:
            #self.OnPaint(None)
            self.Refresh()

    def setContentName(self,s):
        wx.CallAfter(self.OnSetContentName,s)
        
    def OnSetContentName(self,s):
        self.name = s

    def getContentName(self):
        return self.name
    
