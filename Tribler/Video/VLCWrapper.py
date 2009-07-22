# Written by Fabian van der Werf and Arno Bakker
# see LICENSE.txt for license information

import sys
import os
import random
from traceback import print_exc,print_stack
from threading import currentThread

#
# 16/06/09 boudewijn: it appears that under Ubuntu importing and using
# VLC must be delayed until the GUI is ready for it. We define 'the
# GUI is ready for it' to be when the user is able to perform actions
# such as play. Only then will vlc be imported and the wrapper
# initialized.
#

# import vlc

# #
# # With VLC 0.9.x came changes to the MediaControl API. In particular,
# # there is no longer a concept of a playlist. The VLCWrapper can now
# # deal with both versions of the API.
# #
# try:
#     vlc.Instance
#     VLC_MEDIACONTROL_API_VERSION = "0.2"
# except:
#     #print_exc()
#     VLC_MEDIACONTROL_API_VERSION = "0.1"

# from Tribler.Video.VideoServer import VideoRawVLCServer

# vlcstatusmap = {vlc.PlayingStatus:'vlc.PlayingStatus',
#                 vlc.PauseStatus:'vlc.PauseStatus',
#                 vlc.InitStatus:'vlc.InitStatus',
#                 vlc.EndStatus:'vlc.EndStatus',
#                 vlc.UndefinedStatus:'vlc.UndefinedStatus'}

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
        self.window = None
        self.initialized = False

    def _init_vlc(self):
        """
        To avoid a bug on Ubuntu Intrepid and Jaunty that causes the
        GUI to instantly exit, we need to delay importing vlc and
        seting the window.
        """
        import vlc
        from Tribler.Video.VideoServer import VideoRawVLCServer

        # avoid another init
        self.initialized = True

        self.vlc = vlc
    
        #
        # With VLC 0.9.x came changes to the MediaControl API. In particular,
        # there is no longer a concept of a playlist. The VLCWrapper can now
        # deal with both versions of the API.
        #
        try:
            vlc.Instance
            self.VLC_MEDIACONTROL_API_VERSION = "0.2"
        except:
            # print_exc()
            self.VLC_MEDIACONTROL_API_VERSION = "0.1"

        self.media = self.get_vlc_mediactrl()
        self.videorawserv = VideoRawVLCServer.getInstance()

        if not self.window is None:
            self.set_window(self.window)

    def set_window(self,wxwindow):
        """ Must be called after wxwindow has been realized, such that
        GetHandle() returns a valid xid. See
        http://mailman.videolan.org/pipermail/vlc-devel/2006-September/025895.html
        """
        if not self.initialized:
            self.window = wxwindow
            return

        check_threading()
        xid = wxwindow.GetHandle()
        if xid == 0:
            if DEBUG:
                print >>sys.stderr,"VLCWrapper: set_window: WARNING: window not yet materialized, XID=0"
            return
        
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: set_window, XID=",xid
            
        if sys.platform == 'darwin':
            self.media.set_visual_macosx_type(self.vlc.DrawableControlRef)
        self.media.set_visual(xid)
        
    
    def get_vlc_mediactrl(self):
        if not self.initialized:
            self._init_vlc()

        check_threading()
        if self.VLC_MEDIACONTROL_API_VERSION == "0.1":
            if sys.platform == 'win32':
                oldcwd = os.getcwd()
                os.chdir(os.path.join(self.installdir,'vlc'))
    
        # Arno: 2007-05-11: Don't ask me why but without the "--verbose=0" vlc will ignore the key redef.
        params = ["--verbose=2"]
        
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
        
        if self.VLC_MEDIACONTROL_API_VERSION == "0.1":
            params += ["--http-reconnect"]
        
        #if sys.platform == 'win32':
        #    params += ["--plugin-path", "c:\\build\\mbvlc100\\vlc\\plugins" ]




        # Arno, 2009-03-30: On my Vista Test Machine (no Aero) video playback 
        # doesn't work with our VLC 0.8.6h. The Direct3D vout is chosen and 
        # that gives a "Failed to create texture" error. Apparent solution is 
        # to set vout to vout_directx (opengl and wingdi also work, but former 
        # doesn't work on all tested content and the latter gives poor output 
        # quality. On a machine with Aero this unfortunately causes it to
        # switch the color scheme to Windows Vista Basic :-( Need Aero detection.
        #
        if sys.platform == "win32":
            try:
                # 5 = XP, 6 = Vista
                if sys.getwindowsversion()[0] == 6:
                    params += ["--vout","vout_directx"]
            except:
                print_exc()

        # VLC wiki says: "apply[ing] deinterlacing even if the original is not
        # interlaced, is a really bad idea."
        #params += ["--vout-filter","deinterlace"]
        #params += ["--deinterlace-mode","linear"]
        #params += ["--demux=ts"]
        #params += ["--codec=mp4"]
        #
        params += ["--no-plugins-cache"]
        # must come last somehow on Win32
        if self.VLC_MEDIACONTROL_API_VERSION == "0.2":
            params += ["--key-toggle-fullscreen", "Esc"] 
        else:
            params += ["--key-fullscreen", "Esc"]
        
        # Arno, 2009-07-22: Not sure whether sys.argv0 gives right dir.
        if sys.platform == 'darwin':
            params += ["--plugin-path", "%s/macbinaries/vlc_plugins" % (
                 # location of plugins: next to tribler.py
                 os.path.abspath(os.path.dirname(sys.argv[0]))
                 )]

        if self.VLC_MEDIACONTROL_API_VERSION == "0.2":
            if sys.platform == 'win32':
                params += ["--plugin-path", os.path.abspath(os.path.join(self.installdir,'vlc','plugins'))]

            
        #print >>sys.stderr,"VLCWrapper: get_vlc_mediactrl: params",params
            
        media = self.vlc.MediaControl(params)

        if self.VLC_MEDIACONTROL_API_VERSION == "0.1":            
            if sys.platform == 'win32':
                os.chdir(oldcwd)
    
        return media
    
    def load(self,url,streaminfo=None):
        if not self.initialized:
            self._init_vlc()

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
            if self.VLC_MEDIACONTROL_API_VERSION == "0.2":
                self.media.set_mrl(url)
            else:
                self.media.playlist_add_item(url)

        #print >>sys.stderr,"VLCWrapper: load: after list is",self.media.playlist_get_list()


    def start(self,abspos=0):
        if not self.initialized:
            self._init_vlc()

        check_threading()
        if DEBUG:
            if self.VLC_MEDIACONTROL_API_VERSION == "0.2":
                print >>sys.stderr,"VLCWrapper: start: item is",self.media.get_mrl()
            else:
                print >>sys.stderr,"VLCWrapper: start: list is",self.media.playlist_get_list()    
        pos = self.vlc.Position()
        pos.origin = self.vlc.AbsolutePosition
        pos.key = self.vlc.MediaTime
        pos.value = abspos
        self.media.start(pos)


    def stop(self):
        if not self.initialized:
            self._init_vlc()

        check_threading()
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: stop"
        self.media.stop()

    def pause(self):
        if not self.initialized:
            self._init_vlc()

        check_threading()
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: pause"
        self.media.pause()

    def resume(self):
        if not self.initialized:
            self._init_vlc()

        check_threading()
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: resume"
        self.media.resume()


    def get_stream_information_status(self):
        """ Returns the state of VLC. """
        if not self.initialized:
            self._init_vlc()

        check_threading() 
        return self.media.get_stream_information()["status"]

    def get_stream_information_length(self):
        """ Returns the length in bytes of current item playing """
        if not self.initialized:
            self._init_vlc()

        check_threading() 
        return self.media.get_stream_information()["length"]

    def get_media_position(self):
        """ Returns absolute position in bytes of current item playing """
        if not self.initialized:
            self._init_vlc()

        check_threading() 
        return self.media.get_media_position(self.vlc.AbsolutePosition, self.vlc.MediaTime).value

    def set_media_position(self, where):
        """ Arno: For some files set_media_position() doesn't work. Subsequent 
        get_media_position()s then do not always return the right value.
        TODO: seek mode
        """
        if not self.initialized:
            self._init_vlc()

        check_threading()
        pos = self.vlc.Position() 
        pos.origin = self.vlc.AbsolutePosition
        pos.key = self.vlc.MediaTime
        pos.value = where
        
        self.media.set_media_position(pos)
        

    def sound_set_volume(self, frac):
        """ frac is float 0..1 """
        if not self.initialized:
            self._init_vlc()

        check_threading()
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: sound_set_volume"
        vol = int(frac * VLC_MAXVOLUME)
        self.media.sound_set_volume(vol)

    def sound_get_volume(self):
        """ returns a float 0..1 """
        if not self.initialized:
            self._init_vlc()

        check_threading()
        vol = self.media.sound_get_volume()
        return float(vol) / VLC_MAXVOLUME

    def set_fullscreen(self,b):
        """ b is Boolean """
        if not self.initialized:
            self._init_vlc()

        check_threading()
        if DEBUG:
            print >>sys.stderr,"VLCWrapper set_fullscreen"
        if b:
            self.media.set_fullscreen(1)
        else:
            self.media.set_fullscreen(0)

    def playlist_get_list(self):
        if not self.initialized:
            self._init_vlc()

        check_threading()
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: playlist_get_list"
        if self.VLC_MEDIACONTROL_API_VERSION == "0.2":
            return [self.media.get_mrl()]
        else:
            return self.media.playlist_get_list()

    def playlist_clear(self):
        if not self.initialized:
            self._init_vlc()

        check_threading()
        if DEBUG:
            print >>sys.stderr,"VLCWrapper: playlist_clear"

        if self.VLC_MEDIACONTROL_API_VERSION == "0.2":
            #raise RuntimeError("VLC MediaControlAPI 0.2 doesn't support playlist ops")
            pass
        else:
            self.media.playlist_clear()

    def exit(self):
        if not self.initialized:
            self._init_vlc()

        check_threading()
        """ Use with care, Ivaylo's raw interface seems to have issues with
        calling this. So we don't
        """
        self.media.exit()
        self.media = None
        
