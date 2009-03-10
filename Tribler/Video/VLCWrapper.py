# Written by Fabian van der Werf and Arno Bakker
# see LICENSE.txt for license information

import sys
import os
import time
import random
from traceback import print_exc
from threading import currentThread


import vlc

#
# With VLC 0.9.x came changes to the MediaControl API. In particular,
# there is no longer a concept of a playlist. The VLCWrapper can now
# deal with both versions of the API.
#
try:
    vlc.Instance
    VLC_MEDIACONTROL_API_VERSION = "0.2"
except:
    #print_exc()
    VLC_MEDIACONTROL_API_VERSION = "0.1"

from Tribler.Video.VideoServer import VideoRawVLCServer

vlcstatusmap = {vlc.PlayingStatus:'vlc.PlayingStatus',
                vlc.PauseStatus:'vlc.PauseStatus',
                vlc.InitStatus:'vlc.InitStatus',
                vlc.EndStatus:'vlc.EndStatus',
                vlc.UndefinedStatus:'vlc.UndefinedStatus'}

DEBUG = True


VLC_MAXVOLUME = 200


def check_threading():
    if currentThread().getName() != "MainThread":
        print >>sys.stderr,"VLCWrapper: Thread violation!"
        print_stack()
        

class VLCWrapper:
    """ Wrapper around the MediaControl API, to hide some of its quirks,
    like the Position() objects, and to hide the VideoRawVLCServer from users.
    
    At the moment, we create one instance of this class which is reused
    each time to create a VLCWindow.
    """

    def __init__(self,installdir):
        check_threading()
        self.installdir = installdir
        self.media = self.get_vlc_mediactrl()
        self.videorawserv = VideoRawVLCServer.getInstance()
    
    def set_window(self,wxwindow):
        """ Must be called after wxwindow has been realized, such that
        GetHandle() returns a valid xid. See
        http://mailman.videolan.org/pipermail/vlc-devel/2006-September/025895.html
        """
        check_threading()
        xid = wxwindow.GetHandle()
        if xid == 0:
            if DEBUG:
                print >>sys.stderr,"VLCWrapper: set_window: WARNING: window not yet materialized, XID=0"
            return
        
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: set_window, XID=",xid
            
        if sys.platform == 'darwin':
            self.media.set_visual_macosx_type(vlc.DrawableControlRef)
        self.media.set_visual(xid)
    
    def get_vlc_mediactrl(self):
        check_threading()
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
        # must come last somehow on Win32
        if VLC_MEDIACONTROL_API_VERSION == "0.2":
            params += ["--key-toggle-fullscreen", "Esc"] 
        else:
            params += ["--key-fullscreen", "Esc"]
        
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
        check_threading()
        print >>sys.stderr,"VLCWrapper: load:",url,streaminfo
        
        #self.media.exit()
        #self.media = self.get_vlc_mediactrl()
        
        if url is None:
            """
            To prevent concurrency between the MainThread closing the 
            video window and the VLC Dummy-X thread making callbacks,
            the callbacks go to a stable object, the VideoRawVLCServer that
            persists during the lifetime of the player process.
            """

            sid = random.randint(0,sys.maxint)
            self.videorawserv.set_inputstream(streaminfo,sid)
               
            if DEBUG:
                print >>sys.stderr,"VLCWrapper: load: stream",sid,"size",streaminfo['length']
            length = streaminfo['length']
            if length is None:
                length = -1
            
            self.media.set_raw_callbacks(self.videorawserv.ReadDataCallback,self.videorawserv.SeekDataCallback,length,sid)
        else:
            if DEBUG:
                print >>sys.stderr,"VLCWrapper: load: calling playlist_add_item"
            if VLC_MEDIACONTROL_API_VERSION == "0.2":
                self.media.set_mrl(url)
            else:
                self.media.playlist_add_item(url)

        #print >>sys.stderr,"VLCWrapper: load: after list is",self.media.playlist_get_list()


    def start(self,abspos=0):
        check_threading()
        if DEBUG:
            if VLC_MEDIACONTROL_API_VERSION == "0.2":
                print >>sys.stderr,"VLCWrapper: start: item is",self.media.get_mrl()
            else:
                print >>sys.stderr,"VLCWrapper: start: list is",self.media.playlist_get_list()    
        pos = vlc.Position()
        pos.origin = vlc.AbsolutePosition
        pos.key = vlc.MediaTime
        pos.value = abspos
        self.media.start(pos)


    def stop(self):
        check_threading()
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: stop"
        self.media.stop()

    def pause(self):
        check_threading()
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: pause"
        self.media.pause()

    def get_stream_information_status(self):
        """ Returns the state of VLC. """
        check_threading() 
        return self.media.get_stream_information()["status"]

    def get_stream_information_length(self):
        """ Returns the length in bytes of current item playing """
        check_threading() 
        return self.media.get_stream_information()["length"]

    def get_media_position(self):
        """ Returns absolute position in bytes of current item playing """
        check_threading() 
        return self.media.get_media_position(vlc.AbsolutePosition, vlc.MediaTime).value

    def set_media_position(self, where):
        """ Arno: For some files set_media_position() doesn't work. Subsequent 
        get_media_position()s then do not always return the right value.
        TODO: seek mode
        """
        check_threading()
        pos = vlc.Position() 
        pos.origin = vlc.AbsolutePosition
        pos.key = vlc.MediaTime
        pos.value = where
        
        self.media.set_media_position(pos)
        

    def sound_set_volume(self, frac):
        """ frac is float 0..1 """
        check_threading()
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: sound_set_volume"
        vol = int(frac * VLC_MAXVOLUME)
        self.media.sound_set_volume(vol)

    def sound_get_volume(self):
        """ returns a float 0..1 """
        check_threading()
        vol = self.media.sound_get_volume()
        return float(vol) / VLC_MAXVOLUME

    def set_fullscreen(self,b):
        """ b is Boolean """
        check_threading()
        if DEBUG:
            print >>sys.stderr,"VLCWrapper set_fullscreen"
        if b:
            self.media.set_fullscreen(1)
        else:
            self.media.set_fullscreen(0)

    def playlist_get_list(self):
        check_threading()
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: playlist_get_list"
        if VLC_MEDIACONTROL_API_VERSION == "0.2":
            return [self.media.get_mrl()]
        else:
            return self.media.playlist_get_list()

    def playlist_clear(self):
        check_threading()
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: playlist_clear"

        if VLC_MEDIACONTROL_API_VERSION == "0.2":
            #raise RuntimeError("VLC MediaControlAPI 0.2 doesn't support playlist ops")
            pass
        else:
            self.media.playlist_clear()

    def exit(self):
        check_threading()
        """ Use with care, Ivaylo's raw interface seems to have issues with
        calling this. So we don't
        """
        self.media.exit()
        self.media = None
        
