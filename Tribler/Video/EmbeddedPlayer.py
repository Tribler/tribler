# Written by Fabian van der Werf and Arno Bakker
# see LICENSE.txt for license information

import wx
import vlc
import os
import sys
import time
import traceback
from time import sleep
from tempfile import mkstemp
from threading import currentThread,Event
from traceback import print_stack,print_exc
from safeguiupdate import FlaglessDelayedInvocation
from Progress import ProgressBar
from Tribler.vwxGUI.tribler_topButton import *



# Fabian: can't use the constants from wx.media since 
# those all yield 0 (for my wx)
# Arno: These modes are not what vlc returns, but Fabian's summary of that
MEDIASTATE_PLAYING = 1
MEDIASTATE_PAUSED  = 2
MEDIASTATE_STOPPED = 3

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
                          size=(800,650))
        self.createMainPanel()

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

    def createMainPanel(self):
        oldcwd = os.getcwd()
        if sys.platform == 'win32':
            vlcinstalldir = os.path.join(self.utility.getPath(),"vlc")
            os.chdir(vlcinstalldir)

        self.showingvideo = False
        self.videopanel = EmbeddedPlayer(self, -1, self, False, self.utility)
        #self.videopanel.Hide()
        self.Hide()
        # Arno, 2007-04-02: There is a weird problem with stderr when using VLC on Linux
        # see Tribler\Video\vlcmedia.py:VLCMediaCtrl. Solution is to sleep 1 sec here.
        # Arno: 2007-04-23: Appears to have been cause by wx.SingleInstanceChecker
        # in wxPython-2.8.1.1.
        #
        #if sys.platform == 'linux2':
        #    print "Sleeping for a few seconds to allow VLC to initialize"
        #    sleep(5)
            
        if sys.platform == 'win32':
            os.chdir(oldcwd)

    def OnCloseWindow(self, event = None):
        self.swapout_videopanel()        
        

    def swapin_videopanel(self,url,play=True,progressinf=None):
        
        print >>sys.stderr,"videoframe: Swap IN videopanel"
        
        if not self.showingvideo:
            self.showingvideo = True
            self.Show()

        self.item = VideoItem(url)
        self.videopanel.SetItem(self.item,play=play,progressinf=progressinf)

    def swapout_videopanel(self):
        
        print >>sys.stderr,"videoframe: Swap OUT videopanel"
        
        self.videopanel.reset()
        if self.showingvideo:
            self.showingvideo = False
            self.Hide()

    def get_video_progressinf(self):
        return self.videopanel

    def reset_videopanel(self):
        self.videopanel.reset()
        
        
    def invokeLater(self,*args,**kwargs):
        self.videopanel.invokeLater(*args,**kwargs)



class EmbeddedPlayer(wx.Panel,FlaglessDelayedInvocation):

    def __init__(self, parent, id, closehandler, allowclose, utility):
        wx.Panel.__init__(self, parent, id)
        FlaglessDelayedInvocation.__init__(self)
        self.item = None

        self.closehandler = closehandler
        self.utility = utility
        self.SetBackgroundColour(wx.BLACK)

        #logofilename = os.path.join(self.utility.getPath(),'icons','logo4video.png')
        logofilename = None

        mainbox = wx.BoxSizer(wx.VERTICAL)
        self.mediactrl = VLCMediaCtrl(self, -1,logofilename)
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
        mainbox.Add(ctrlsizer, 0, wx.ALIGN_BOTTOM|wx.EXPAND, 1)
        self.SetSizerAndFit(mainbox)
        
        self.playtimer = None
        self.progressinf = None
        self.bitrateset = False
        self.progress = None
        self.update = False
        self.timer = None
        
    def SetItem(self, item, play = True,progressinf = None):
        self.item = item
        if DEBUG:
            print >>sys.stderr,"embedplay: Telling player to play",item.getPath(),currentThread().getName()
        self.mediactrl.Load(item.getPath())

        if progressinf is not None:
            self.progressinf = progressinf
            self.progressinf.set_callback(self.bufferinfo_updated_network_callback)
            if self.progress is not None:
                self.progress.set_blocks(self.progressinf.get_bufferinfo().tricolore)
        else:
            self.enableInput()
            if self.progress is not None:
                self.progress.set_blocks([2]*100)
                self.progress.Refresh()

        self.update = True
        
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
        self.ppbtn.Disable()
        self.slider.Disable()
        self.fsbtn.Disable()

    def reset(self):
        self.disableInput()
        self.Stop()
        if self.progress is not None:
            self.progress.set_blocks([0]*100)
            self.progress.Refresh()
        

    def updateSlider(self, evt):
        self.volume.SetValue(int(self.mediactrl.GetVolume() * 100))

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


    def run(self):
        while not self.stop.isSet():
            evt = UpdateEvent(self.GetId())
            wx.PostEvent(self, evt)
            self.stop.wait(0.2)


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

    def bufferinfo_updated_network_callback(self):
        """ Called by network thread """
        self.invokeLater(self.bufferinfo_updated_gui_callback)
        
    def bufferinfo_updated_gui_callback(self):
        """ Called by GUI thread """
        #print >>sys.stderr,"embedplay: Playable is",self.progressinf.get_bufferinfo().get_playable()
        #print >>sys.stderr,"embedplay: Bitrate is",self.progressinf.get_bufferinfo().get_bitrate()
        
        if self.progress is not None:
            self.progress.Refresh()
        if not self.ppbtn.IsEnabled() and self.progressinf.get_bufferinfo().get_playable():
            self.enableInput()
        """
        if not self.bitrateset:
            br = self.progressinf.get_bufferinfo().get_bitrate()
            if br is not None and br != 0.0:
                self.bitrateset = True
                txt = str(int((br/1024.0)*8.0))+ " kbps"  
                self.br.SetLabel(txt)
       """     

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



VLC_MAXVOL = 1024

class VLCMediaCtrl(wx.Window):
    def __init__(self, parent, id, logofilename):

        wx.Window.__init__(self, parent, id, size=(320,240))
        self.SetMinSize((320,240))
        self.SetBackgroundColour(wx.BLACK)

        if logofilename is not None:
            self.logo = wx.BitmapFromImage(wx.Image(logofilename).Scale(100,142),-1)
            self.Bind(wx.EVT_PAINT, self.OnPaint)

        #
        # Arno, 2007-04-02: On Linux (Centos 4.4) with vlc 0.8.6a I get a weird 
        # problem. When vlc is loaded the main Tribler gets IOErrors while writing
        # to stderr. It is unclear what the cause of these errors is. 
        # 
        # What appears to work is to have the MainThread sleep 1 second after it
        # created the VLC control and using "--verbose 0 --logile X" as parameters.
        #
        [loghandle,logfilename] = mkstemp("vlc-log")
        os.close(loghandle)
        #self.media = vlc.MediaControl(["--verbose","0","--logfile",logfilename,"--key-fullscreen","Esc"])
        self.media = vlc.MediaControl()
        self.visinit = False

        

    # Be sure that this window is visible before
    # calling Play(), otherwise GetHandle() fails
    def Play(self):

        if self.GetState() == MEDIASTATE_PLAYING:
            return

        if not self.visinit:
            xid = self.GetHandle()
            self.media.set_visual(xid)
            self.visinit = True

        if self.GetState() == MEDIASTATE_STOPPED:
            pos = vlc.Position()
            pos.origin = vlc.AbsolutePosition
            pos.key = vlc.MediaTime
            pos.value = 0
            self.media.start(pos)
        else:
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
        if status == vlc.PlayingStatus:
            return MEDIASTATE_PLAYING
        elif status == vlc.PauseStatus:
            return MEDIASTATE_PAUSED
        else:
            return MEDIASTATE_STOPPED


    def Load(self,url):
        self.Stop()
        self.media.playlist_clear()
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
        dc.DrawRectangle(x,y,maxw,maxh)
        dc.DrawBitmap(self.logo,halfx,halfy,True)
        
        dc.EndDrawing()
        if evt is not None:
            evt.Skip(True)
        
