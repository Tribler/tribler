# Written by Fabian van der Werf and Arno Bakker
# see LICENSE.txt for license information

import sys
import os
import time
import random

import wx
import vlc

from Tribler.Video.VideoServer import VideoRawVLCServer

DEBUG = True

class VLCLogoWindow(wx.Window):
    """ A wx.Window to be passed to the vlc.MediaControl to draw the video
    in. In addition, the class can display a logo, a thumbnail and a 
    "Loading: bla.video" message when VLC is not playing.
    """
    
    def __init__(self, parent, size, vlcwrap, logopath):
        wx.Window.__init__(self, parent, -1, size=size)
        self.SetMinSize(size)
        self.SetBackgroundColour(wx.BLACK)
        
        self.vlcwrap = vlcwrap

        if logopath is not None:
            self.logo = wx.BitmapFromImage(wx.Image(logopath),-1)
        else:
            self.logo = None
        self.contentname = None
        self.contentbm = None
        self.Bind(wx.EVT_PAINT, self.OnPaint)

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
        if DEBUG:
            print >>sys.stderr,"VLCWin: OnPaint"

        dc = wx.PaintDC(self)
        dc.Clear()
        dc.BeginDrawing()        

        dc.SetPen(wx.Pen("#BLACK",0))
        dc.SetBrush(wx.Brush("BLACK"))

        x,y,maxw,maxh = self.GetClientRect()
        halfx = (maxw-x)/2
        halfy = (maxh-y)/2

        if sys.platform == 'linux2':
            dc.DrawRectangle(x,y,maxw,maxh)

        lineoffset = 120

        if self.logo is not None:
            halfx -= self.logo.GetWidth()/2
            halfy -= self.logo.GetHeight()/2

            dc.DrawBitmap(self.logo,halfx,halfy,True)
            
            txty = halfy+self.logo.GetHeight()+lineoffset
        else:
            txty = halfy

        dc.SetTextForeground(wx.WHITE)
        dc.SetTextBackground(wx.BLACK)
        
        if self.contentname is not None:
            dc.DrawText(self.contentname,30,txty)
            lineoffset += 30

        if self.contentbm is not None:
            bmy = max(0,txty-20-self.contentbm.GetHeight())
            dc.DrawBitmap(self.contentbm,30,bmy,True)
        
        dc.EndDrawing()
        if evt is not None:
            evt.Skip(True)
        
        

VLC_MAXVOLUME = 200

class VLCWrapper:
    """ Wrapper around the MediaControl API, to hide some of its quirks,
    like the Position() objects, and to hide the VideoRawVLCServer from users.
    
    At the moment, we create one instance of this class which is reused
    each time to create a VLCWindow.
    """

    def __init__(self,installdir):
        self.installdir = installdir
        self.media = self.get_vlc_mediactrl()
        self.videoserv = VideoRawVLCServer.getInstance()
    
    def set_window(self,wxwindow):
        """ Must be called after wxwindow has been realized, such that
        GetHandle() returns a valid xid. See
        http://mailman.videolan.org/pipermail/vlc-devel/2006-September/025895.html
        """
        xid = wxwindow.GetHandle()
        if sys.platform == 'darwin':
            self.media.set_visual_macosx_type(vlc.DrawableControlRef)
        self.media.set_visual(xid)
    
    def get_vlc_mediactrl(self):
        if sys.platform == 'win32':
            oldcwd = os.getcwd()
            os.chdir(os.path.join(self.installdir,'vlc'))
    
        # Arno: 2007-05-11: Don't ask me why but without the "--verbose=0" vlc will ignore the key redef.
        params = ["--verbose=0"]
        
        """
        # To enable logging to file:
        #[loghandle,logfilename] = mkstemp("vlc-log")
        #os.close(loghandle)
        currwd = os.getcwd()
        logfilename = os.path.join(currwd,"vlc.log")
        params += ["--file-logging"]
        params += ["--logfile",logfilename]
        """
        
        params += ["--no-drop-late-frames"] # Arno: 2007-11-19: don't seem to work as expected DEBUG
        params += ["--no-skip-frames"]
        params += ["--quiet-synchro"]
        # JD: avoid "fast catchup" after frame loss by letting VLC have a flexible buffer
        #params += ["--access-filter","timeshift"]
        #params += ["--timeshift-force"]
        # Arno: attempt to improve robustness
        params += ["--http-reconnect"]

        # VLC wiki says: "apply[ing] deinterlacing even if the original is not
        # interlaced, is a really bad idea."
        #params += ["--vout-filter","deinterlace"]
        #params += ["--deinterlace-mode","linear"]
        #params += ["--demux=ts"]
        #params += ["--codec=mp4"]
        #
        params += ["--no-plugins-cache"]
        params += ["--key-fullscreen", "Esc"] # must come last somehow on Win32
        
        if sys.platform == 'darwin':
            params += ["--plugin-path", "%s/macbinaries/vlc_plugins" % (
                 # location of plugins: next to tribler.py
                 os.path.abspath(os.path.dirname(sys.argv[0]))
                 )]
            
        media = vlc.MediaControl(params)
            
        if sys.platform == 'win32':
                os.chdir(oldcwd)
    
        return media
    
    def load(self,url,streaminfo=None):
        
        #self.media.exit()
        #self.media = self.get_vlc_mediactrl()
        
        if streaminfo is not None:
            # AAA
            #sid = 0
            sid = random.randint(0,sys.maxint)
            
            """
            To prevent concurrency between the MainThread closing the 
            video window and the VLC Dummy-X thread making callbacks,
            the callbacks go to a stable object, the VideoRawVLCServer that
            persists during the lifetime of the player process.
            """
            
            self.videoserv.set_inputstream(streaminfo,sid)
               
            if DEBUG:
                print >>sys.stderr,"VLCWrapper: Load: stream",sid,"size",streaminfo['length']
            length = streaminfo['length']
            if length is None:
                length = -1
            
            self.media.set_raw_callbacks(self.videoserv.ReadDataCallback,self.videoserv.SeekDataCallback,length,sid)
            # AAA
            #self.media.set_raw_callbacks(videoserv.ReadDataCallback,videoserv.SeekDataCallback,length)
            
        else:
            self.media.playlist_add_item(url)

    def start(self,abspos=0):
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: play: start"
        pos = vlc.Position()
        pos.origin = vlc.AbsolutePosition
        pos.key = vlc.MediaTime
        pos.value = abspos
        self.media.start(pos)

    def stop(self):
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: stop"
        self.media.stop()

    def pause(self):
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: pause"
        self.media.pause()

    def get_stream_information_status(self):
        """ Returns the state of VLC. """ 
        return self.media.get_stream_information()["status"]

    def get_stream_information_length(self):
        """ Returns the length in bytes of current item playing """ 
        return self.media.get_stream_information()["length"]

    def get_media_position(self):
        """ Returns absolute position in bytes of current item playing """ 
        return self.media.get_media_position(vlc.AbsolutePosition, vlc.MediaTime).value

    def set_media_position(self, where):
        """ Arno: For some files set_media_position() doesn't work. Subsequent 
        get_media_position()s then do not always return the right value.
        TODO: seek mode
        """
        pos = vlc.Position() 
        pos.origin = vlc.AbsolutePosition
        pos.key = vlc.MediaTime
        pos.value = where
        
        self.media.set_media_position(pos)
        

    def sound_set_volume(self, frac):
        """ frac is float 0..1 """
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: sound_set_volume"
        vol = int(frac * VLC_MAXVOLUME)
        self.media.sound_set_volume(vol)

    def sound_get_volume(self):
        """ returns a float 0..1 """
        vol = self.media.sound_get_volume()
        return float(vol) / VLC_MAXVOLUME

    def set_fullscreen(self,b):
        """ b is Boolean """
        if DEBUG:
            print >>sys.stderr,"VLCWrapper set_fullscreen"
        if b:
            self.media.set_fullscreen(1)
        else:
            self.media.set_fullscreen(0)

    def playlist_get_list(self):
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: playlist_get_list"
        return self.media.playlist_get_list()

    def playlist_clear(self):
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: playlist_clear"
        self.media.playlist_clear()

    def exit(self):
        """ Use with care, Ivaylo's raw interface seems to have issues with
        calling this. So we don't
        """
        self.media.exit()
        self.media = None
        
