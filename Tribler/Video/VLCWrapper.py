# Written by Fabian van der Werf and Arno Bakker
# see LICENSE.txt for license information

import sys
import os
import logging
from traceback import print_exc, print_stack
from threading import currentThread

from Tribler.Video.defs import *

VLC_MAXVOLUME = 200  # Also for 0.3

logger = logging.getLogger(__name__)


def check_threading():
    if currentThread().getName() != "MainThread":
        raise Exception("VLCWrapper: Thread violation!")


class VLCWrapper:

    """ Wrapper around the MediaControl API, to hide some of its quirks,
    like the Position() objects.

    At the moment, we create one instance of this class which is reused
    each time to create a VLCWindow.
    """

    def __init__(self, installdir):
        self._logger = logging.getLogger(self.__class__.__name__)

        check_threading()
        self.installdir = installdir
        self.window = None
        self.windowpassedtovlc = -1
        self.initialized = False

    def _init_vlc(self):
        """
        To avoid a bug on Ubuntu Intrepid and Jaunty that causes the
        GUI to instantly exit, we need to delay importing vlc and
        setting the window.
        """
        try:
            import Tribler.vlc as vlc
        except:
            print_stack()
            print_exc()

        self.initialized = True
        self.vlc = vlc
        self.media = self.get_vlc_mediactrl()

        if not self.window is None:
            self.set_window(self.window)

    def set_window(self, wxwindow):
        """ Must be called after wxwindow has been realized, such that
        GetHandle() returns a valid xid. See
        http://mailman.videolan.org/pipermail/vlc-devel/2006-September/025895.html
        """
        self.window = wxwindow
        if not self.initialized:
            return

        check_threading()
        xid = wxwindow.GetHandle()
        if xid == 0:
            self._logger.debug("VLCWrapper: set_window: WARNING: window not yet materialized, XID=0")
            return

        self._logger.debug("VLCWrapper: set_window, XID=%s", xid)

        if self.windowpassedtovlc == xid:
            return

        if sys.platform == 'win32':
            self.vlc.libvlc_media_player_set_hwnd(self.player, xid)
        else:
            self.vlc.libvlc_media_player_set_xwindow(self.player, xid);

        self.windowpassedtovlc = xid

    def get_vlc_mediactrl(self):
        if not self.initialized:
            self._init_vlc()

        check_threading()

        # Arno: 2007-05-11: Don't ask me why but without the "--verbose=0" vlc will ignore the key redef.
        params = ["--verbose=0"]

        """
        # To enable logging to file:
        #[loghandle,logfilename] = mkstemp("vlc-log")
        #os.close(loghandle)
        currwd = os.getcwd()
        logfilename = os.path.join(currwd,"vlc.log")
        params += [""--extraintf=logger""]
        params += ["--logfile",logfilename]
        """

        params += ["--no-drop-late-frames"]  # Arno: 2007-11-19: don't seem to work as expected DEBUG
        params += ["--no-skip-frames"]
        params += ["--quiet-synchro"]
        # JD: avoid "fast catchup" after frame loss by letting VLC have a flexible buffer
        # params += ["--access-filter","timeshift"]
        # params += ["--timeshift-force"]
        # Arno: attempt to improve robustness

        # if sys.platform == 'win32':
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
                # pylint: disable-msg=E1101
                if sys.getwindowsversion()[0] == 6:
                    # detect if aero is on
                    from ctypes import windll, c_int, byref

                    def isAeroEnabled():
                        S_OK = 0
                        if hasattr(windll, 'dwmapi'):
                            dwmapi = windll.dwmapi
                            if hasattr(dwmapi, 'DwmIsCompositionEnabled'):
                                flag = c_int()
                                res = dwmapi.DwmIsCompositionEnabled(byref(flag))
                                return res == S_OK and bool(flag)
                        return False

                    if not isAeroEnabled():
                        params += ["--vout", "vout_directx"]
                # pylint: enable-msg=E1101
            except:
                print_exc()

        # VLC wiki says: "apply[ing] deinterlacing even if the original is not
        # interlaced, is a really bad idea."
        # params += ["--vout-filter","deinterlace"]
        # params += ["--deinterlace-mode","linear"]
        # params += ["--demux=ts"]
        # params += ["--codec=mp4"]
        #
        params += ["--no-plugins-cache"]

        # must come last somehow on Win32
        params += ["--global-key-toggle-fullscreen", "Esc"]
        params += ["--key-toggle-fullscreen", "Esc"]

        # Arno, 2009-07-22: Not sure whether sys.argv0 gives right dir.
        if sys.platform == 'darwin':
            params += ["--plugin-path", "%s/vlc/plugins" % (self.installdir)]

        params += ["--no-video-title-show"]
        params += ["--no-osd"]

        # print >>sys.stderr,"VLCWrapper: get_vlc_mediactrl: params",params

        media = self.vlc.Instance(params)
        self.player = self.vlc.libvlc_media_player_new(media)

        return media

    def load(self, url):
        if not self.initialized:
            self._init_vlc()

        check_threading()
        self._logger.info("VLCWrapper: load: %s", url)

        if url is None:
            """
            To prevent concurrency between the MainThread closing the
            video window and the VLC Dummy-X thread making callbacks,
            the callbacks go to a stable object, the VideoRawVLCServer that
            persists during the lifetime of the player process.
            """

            pass
        else:
            self._logger.debug("VLCWrapper: load: calling playlist_add_item")

            if os.path.exists(url):
                meditem = self.vlc.libvlc_media_new_path(self.media, url)
            else:
                meditem = self.vlc.libvlc_media_new_location(self.media, url)
            self.vlc.libvlc_media_player_set_media(self.player, meditem)

        # print >>sys.stderr,"VLCWrapper: load: after list is",self.media.playlist_get_list()

    def start(self, abspos=0):
        if not self.initialized:
            self._init_vlc()
        check_threading()

        self._logger.debug("VLCWrapper: start")

        self.vlc.libvlc_media_player_play(self.player)
        self.vlc.libvlc_media_player_set_time(self.player, abspos)

    def stop(self):
        if not self.initialized:
            self._init_vlc()

        check_threading()
        self._logger.debug("VLCWrapper: stop")
        self.vlc.libvlc_media_player_stop(self.player)

    def pause(self):
        if not self.initialized:
            self._init_vlc()
        check_threading()
        self._logger.debug("VLCWrapper: pause")
        self.vlc.libvlc_media_player_set_pause(self.player, 1)

    def resume(self):
        if not self.initialized:
            self._init_vlc()
        check_threading()
        self._logger.debug("VLCWrapper: resume")
        self.vlc.libvlc_media_player_pause(self.player)

    def get_our_state(self):
        """ Returns the state of VLC as summarized by Fabian:
        MEDIASTATE_PLAYING, MEDIASTATE_PAUSED, MEDIASTATE_STOPPED,
        Hiding VLC differences.
        """
        status = self.get_stream_information_status()
        if status == self.vlc.State.Playing:
            return MEDIASTATE_PLAYING
        elif status == self.vlc.State.Paused:
            return MEDIASTATE_PAUSED
        elif status == self.vlc.State.Ended:
            return MEDIASTATE_ENDED
        else:
            return MEDIASTATE_STOPPED

    def get_stream_information_status(self):
        """ Returns the state of VLC. """
        if not self.initialized:
            self._init_vlc()
        check_threading()
        return self.vlc.libvlc_media_player_get_state(self.player)

    def get_stream_information_length(self):
        """ Returns the length in bytes of current item playing.
        For 0.3 API the length in time (in ms), libVLC API provides no byte length """
        if not self.initialized:
            self._init_vlc()
        check_threading()
        return self.vlc.libvlc_media_player_get_length(self.player)

    def get_media_position(self):
        """ Returns absolute position in bytes of current item playing.
        For 0.3 API the position in time (in ms), libVLC API provides no byte length """
        if not self.initialized:
            self._init_vlc()
        check_threading()
        return self.vlc.libvlc_media_player_get_time(self.player)

    def set_media_position(self, where):
        """ Arno: For some files set_media_position() doesn't work. Subsequent
        get_media_position()s then do not always return the right value.
        TODO: seek mode

        For 0.3 API the position must be in time (in ms)
        """
        if not self.initialized:
            self._init_vlc()
        check_threading()
        return self.vlc.libvlc_media_player_set_time(self.player, where)

    def set_media_position_relative(self, position, start=False):
        if not self.initialized:
            self._init_vlc()
        check_threading()
        self._logger.debug("VLCWrapper: set_position")
        if start:
            self.vlc.libvlc_media_player_play(self.player)
        self.vlc.libvlc_media_player_set_position(self.player, position)

    def sound_set_volume(self, frac):
        """ frac is float 0..1 """
        if not self.initialized:
            self._init_vlc()
        check_threading()
        self._logger.debug("VLCWrapper: sound_set_volume")
        vol = int(frac * VLC_MAXVOLUME)
        self.vlc.libvlc_audio_set_volume(self.player, vol)

    def sound_get_volume(self):
        """ returns a float 0..1 """
        if not self.initialized:
            self._init_vlc()
        check_threading()
        vol = self.vlc.libvlc_audio_get_volume(self.player)
        return float(vol) / VLC_MAXVOLUME

    def set_fullscreen(self, b):
        """ b is Boolean """
        if not self.initialized:
            self._init_vlc()
        check_threading()
        self._logger.debug("VLCWrapper set_fullscreen")
        self.vlc.libvlc_set_fullscreen(self.player, b)

    def playlist_get_list(self):
        if not self.initialized:
            self._init_vlc()
        check_threading()
        self._logger.debug("VLCWrapper: playlist_get_list")
        return self.media.playlist_get_list()

    def exit(self):
        if not self.initialized:
            self._init_vlc()

        check_threading()
        """ Use with care, Ivaylo's raw interface seems to have issues with
        calling this. So we don't
        """
        self.media.exit()
        self.media = None
