# Written by Arno Bakker
# Updated by George Milescu
# Updated by Egbert Bouman, now using ConfigParser
# see LICENSE.txt for license information

""" Controls how a TorrentDef is downloaded (rate, where on disk, etc.) """

#
# WARNING: When extending this class:
#
# 1. Add a JavaDoc description for each method you add.
# 2. Also add the methods to APIImplementation/DownloadRuntimeConfig.py
# 3. Document your changes in API.py
#
#

import ast
import copy

from types import StringType

from Tribler.Core.simpledefs import *
from Tribler.Core.defaults import *
from Tribler.Core.Base import *
from Tribler.Core.osutils import get_desktop_dir
from Tribler.Core.SessionConfig import CallbackConfigParser


class DownloadConfigInterface(object):

    """
    (key,value) pair config of per-torrent runtime parameters,
    e.g. destdir, file-allocation policy, etc. Also options to advocate
    torrent, e.g. register in DHT, advertise via Buddycast.

    Use DownloadStartupConfig to manipulate download configs before download
    startup time. This is just a parent class.

    cf. libtorrent torrent_handle
    """
    def __init__(self, dlconfig=None):

        self.dlconfig = dlconfig or CallbackConfigParser()

        # Poor man's versioning of DownloadConfig, add missing default values.
        for section, sect_dict in dldefaults.iteritems():
            if not self.dlconfig.has_section(section):
                self.dlconfig.add_section(section)
            for k, v in sect_dict.iteritems():
                if not self.dlconfig.has_option(section, k):
                    self.dlconfig.set(section, k, v)

        if not dlconfig:
            return

        # modify/fix incorrectly saved dlconfigs
        if dlconfig.has_option('general', 'saveas') and isinstance(dlconfig.get('general', 'saveas'), tuple):
            dlconfig.set('general', 'saveas', dlconfig.get('saveas')[-1])

        if not self.get_dest_dir():
            self.set_dest_dir(get_default_dest_dir())

    def set_dest_dir(self, path):
        """ Sets the directory where to save this Download.
        @param path A path of a directory.
        """
        assert isinstance(path, basestring), path
        self.dlconfig.set('general', 'saveas', path)

    def get_dest_dir(self):
        """ Gets the directory where to save this Download.
        """
        return self.dlconfig.get('general', 'saveas')

    # LAYERVIOLATION: Core has nothing to do with GUI dialogs
    def get_show_saveas(self):
        """ Gets the boolean indicating if we should show a dialog where to save a torrent
        """
        return self.dlconfig.get('general', 'showsaveas')

    def set_show_saveas(self, show):
        """ Sets the boolean indicating if we should show a dialog where to save a torrent
        @param show Boolean to show a dialog
        """
        self.dlconfig.set('general', 'showsaveas', show)

    def get_corrected_filename(self):
        """ Gets the directory name where to save this torrent
        """
        return self.dlconfig.get('general', 'correctedfilename')

    def set_corrected_filename(self, correctedfilename):
        """ Sets the directory name where to save this torrent
        @param correctedfilename name for multifile directory
        """
        self.dlconfig.set('general', 'correctedfilename', correctedfilename)

    def set_video_event_callback(self, usercallback):
        """ Download the torrent in Video-On-Demand mode or as live stream.
        When a playback event occurs, the usercallback function will be
        called, with the following list of arguments:
        <pre>
            Download,event,params
        </pre>
        In which event is a string, and params a dictionary. The following
        events are supported:
        <pre>
        VODEVENT_START:
            The params dictionary will contain the fields

                mimetype,stream,filename,length,bitrate,blocksize,url

            If the filename is set, the video can be read from there. If not,
            the video can be read from the stream, which is a file-like object
            supporting the read(),seek(), and close() operations. It also
            supports an available() method that returns the number of bytes
            that can be read from the stream without blocking.  If the stream
            is not set, the url key contains a URL for the video.

            The MIME type of the video is given by "mimetype", the length of
            the stream in bytes by "length" which may be None if the length is
            unknown (e.g. when live streaming). bitrate is either the bitrate
            as specified in the TorrentDef, or if that was lacking an dynamic
            estimate calculated using the videoanalyser (e.g. ffmpeg), see
            SessionConfig.set_video_analyser_path(). "blocksize" indicates
            the preferred amount of data to read from the stream at a time.

            To fetch a specific file from a multi-file torrent, use the
            set_selected_files() method. This method sets the mode to DLMODE_VOD

        VODEVENT_PAUSE:
            The download engine would like video playback to be paused as the
            data is not coming in fast enough / the data due is not available
            yet.

            The params dictionary contains the fields

                autoresume

            "autoresume" indicates whether or not the Core will generate
            a VODEVENT_RESUME when it is ready again, or that this is left
            to the core user.

        VODEVENT_RESUME:
            The download engine would like video playback to resume.
        </pre>
        The usercallback should ignore events it does not support.

        The usercallback will be called by a popup thread which can be used
        indefinitely (within reason) by the higher level code.

        @param usercallback  A function with the above signature.
        """
        self.dlconfig.set('vod', 'vod_usercallback', usercallback)

    def set_video_events(self, events=[]):
        """ Sets which events will be supported with the usercallback set
        by set_video_event_callback. Supporting the VODEVENT_START event is
        mandatory, and can therefore be omitted from the list.

        @param events        A list of supported VODEVENT_* events.
        """

        # create a copy to avoid loosing the info
        self.dlconfig.set('vod', 'vod_userevents', events[:])

    def set_video_source(self, videosource, authconfig=None, restartstatefilename=None):
        """ Provides the live video source for this torrent from an external
        source.

        @param videosource  A file-like object providing the live video stream
        (i.e., supports read() and close())
        @param authconfig The key information for source authentication of
        packets. See LiveSourceAuthConfig and TorrentDef.create_live_torrent()
        @param restartstatefilename A filename to read/write state needed for a
        graceful restart of the source.
        """
        self.dlconfig.set('vod', 'video_source', videosource)
        if authconfig is None:
            from Tribler.Core.LiveSourceAuthConfig import LiveSourceAuthConfig

            authconfig = LiveSourceAuthConfig(LIVE_AUTHMETHOD_NONE)
        self.dlconfig.set('vod', 'video_source_authconfig', authconfig)
        self.dlconfig.set('vod', 'video_source_restartstatefilename', restartstatefilename)

    def set_video_ratelimit(self, ratelimit):
        """ Sets a limit on the speed at which the video stream is to be read.
        Useful when creating a live stream from file or any other faster-than-live
        data stream.

        @param ratelimit    The maximum speed at which to read from the stream (bps)
        """
        self.dlconfig.set('vod', 'video_ratelimit', ratelimit)

    def set_mode(self, mode):
        """ Sets the mode of this download.
        @param mode DLMODE_NORMAL/DLMODE_VOD """
        self.dlconfig.set('general', 'mode', mode)

    def get_mode(self):
        """ Returns the mode of this download.
        @return DLMODE_NORMAL/DLMODE_VOD """
        return self.dlconfig.get('general', 'mode')

    def get_video_event_callback(self):
        """ Returns the function that was passed to set_video_event_callback().
        @return A function.
        """
        return self.dlconfig.get('vod', 'vod_usercallback')

    def get_video_events(self):
        """ Returns the function that was passed to set_video_events().
        @return A list of events.
        """
        return self.dlconfig.get('vod', 'vod_userevents')

    def get_video_source(self):
        """ Returns the object that was passed to set_video_source().
        @return A file-like object.
        """
        return self.dlconfig.get('vod', 'video_source')

    def get_video_ratelimit(self):
        """ Returns the speed at which the video stream is read (bps).
        @return An integer.
        """
        return self.dlconfig.get('vod', 'video_ratelimit')

    def set_selected_files(self, files):
        """ Select which files in the torrent to download. The filenames must
        be the names as they appear in the content def, including encoding.
        Trivially, when the torrent contains a file 'sjaak.avi' the files
        parameter must be 'sjaak.avi'. When the content def is a torrent def
        and contains multiple files and is named 'filecollection', the files
        parameter must be
            os.path.join('filecollection','sjaak.avi')
        For a swift def, the files must be following the multi-file spec encoding
        (i.e., UTF-8 and /).

        @param files Can be a single filename or a list of filenames (e.g.
        ['harry.avi','sjaak.avi']). Not Unicode strings!
        """
        # TODO: can't check if files exists, don't have tdef here.... bugger
        if isinstance(files, StringType):  # convenience
            files = [files]

        if self.get_mode() == DLMODE_VOD and len(files) > 1:
            raise ValueError("In Video-On-Demand mode only 1 file can be selected for download")

        # Ric: added svc case
        elif self.get_mode() == DLMODE_SVC and len(files) < 2:
            raise ValueError("In SVC Video-On-Demand mode at least 2 files have to be selected for download")

        self.dlconfig.set('general', 'selected_files', files)

    def get_selected_files(self):
        """ Returns the list of files selected for download.
        @return A list of strings. """
        return self.dlconfig.get('general', 'selected_files')

    def set_max_speed(self, direct, speed):
        """ Sets the maximum upload or download speed for this Download.
        @param direct The direction (UPLOAD/DOWNLOAD)
        @param speed The speed in KB/s.
        """
        if direct == UPLOAD:
            self.dlconfig.set('general', 'max_upload_rate', speed)
        else:
            self.dlconfig.set('general', 'max_download_rate', speed)

    def get_max_speed(self, direct):
        """ Returns the configured maximum speed.
        Returns the speed in KB/s. """
        if direct == UPLOAD:
            return self.dlconfig.get('general', 'max_upload_rate')
        else:
            return self.dlconfig.get('general', 'max_download_rate')

    def set_alloc_type(self, value):
        """ Set disk-allocation type:
        <pre>
        * DISKALLOC_NORMAL:  Allocates space as data is received
        * DISKALLOC_BACKGROUND: Also adds space in the background
        * DISKALLOC_PREALLOCATE: Reserves space up front (slow)
        * DISKALLOC_SPARSE: Is only for filesystems that support it by default
          (UNIX)
        </pre>
        @param value A DISKALLOC_* policy.
        """
        self.dlconfig.set('general', 'alloc_type', value)

    def get_alloc_type(self):
        """ Returns the disk-allocation policy.
        @return DISKALLOC_*
        """
        return self.dlconfig.get('general', 'alloc_type')

    def set_super_seeder(self, value):
        """ whether to use special upload-efficiency-maximizing routines (only
        for dedicated seeds).
        @param value Boolean
        """
        self.dlconfig.set('general', 'super_seeder', value)

    def get_super_seeder(self):
        """ Returns hether super seeding is enabled.
        @return Boolean. """
        return self.dlconfig.get('general', 'super_seeder')

    # SWIFTPROC
    def set_swift_listen_port(self, port):
        """ Set the UDP port for the swift process
        (download-to-process mapping permitting).
        @param port A port number.
        """
        self.dlconfig.set('swift', 'swiftlistenport', port)

    def get_swift_listen_port(self):
        """ Returns the UDP port of the swift process.

        @return Port number. """
        return self.dlconfig.get('swift', 'swiftlistenport')

    def set_swift_cmdgw_listen_port(self, port):
        """ Set the TCP listen port for the CMDGW of the swift process
        (download-to-process mapping permitting).
        @param port A port number.
        """
        self.dlconfig.set('swift', 'swiftcmdgwlistenport', port)

    def get_swift_cmdgw_listen_port(self):
        """ Returns the TCP listen port for the CMDGW of the swift process
        (download-to-process mapping permitting).

        @return Port number. """
        return self.dlconfig.get('swift', 'swiftcmdgwlistenport')

    def set_swift_httpgw_listen_port(self, port):
        """ Set the TCP listen port for the CMDGW of the swift process
        (download-to-process mapping permitting).
        @param port A port number.
        """
        self.dlconfig.set('swift', 'swifthttpgwlistenport', port)

    def get_swift_httpgw_listen_port(self):
        """ Returns the TCP listen port for the CMDGW of the swift process.

        @return Port number. """
        return self.dlconfig.get('swift', 'swifthttpgwlistenport')

    def set_swift_meta_dir(self, value):
        """ Set the metadir for storing .m* files of this Download.
        @param value An absolutepath.
        """
        self.dlconfig.set('swift', 'swiftmetadir', value)

    def get_swift_meta_dir(self):
        """ Return the metadir for storing .m* files of this Download.
        @return An absolutepath.
        """
        return self.dlconfig.get('swift', 'swiftmetadir')

    def set_swift_name(self, value):
        self.dlconfig.set('swift', 'name', value)

    def get_swift_name(self):
        return self.dlconfig.get('swift', 'name')


class DownloadStartupConfig(DownloadConfigInterface, Serializable, Copyable):

    """
    (key,value) pair config of per-torrent runtime parameters,
    e.g. destdir, file-allocation policy, etc. Also options to advocate
    torrent, e.g. register in DHT, advertise via Buddycast.

    cf. libtorrent torrent_handle
    """
    def __init__(self, dlconfig=None):
        """ Normal constructor for DownloadStartupConfig (copy constructor
        used internally) """
        DownloadConfigInterface.__init__(self, dlconfig)
    #
    # Class method
    #

    def load(filename):
        """
        Load a saved DownloadStartupConfig from disk.

        @param filename  An absolute Unicode filename
        @return DownloadStartupConfig object
        """
        # Class method, no locking required
        dlconfig = CallbackConfigParser()
        if not dlconfig.read(filename):
            raise IOError, "Failed to open download config file"

        for sect_dict in dlconfig._sections.values():
            for k, v in sect_dict.iteritems():
                if k != '__name__':
                    try:
                        sect_dict[k] = ast.literal_eval(v)
                    except:
                        pass
        return DownloadStartupConfig(dlconfig)

    load = staticmethod(load)

    def save(self, filename):
        """ Save the DownloadStartupConfig to disk.
        @param filename  An absolute Unicode filename
        """
        # Called by any thread
        config_file = open(filename, "wb")
        self.dlconfig.write(config_file)
        config_file.close()

    #
    # Copyable interface
    #
    def copy(self):
        config = copy.copy(self.dlconfig)
        return DownloadStartupConfig(config)


def get_default_dest_dir():
    """ Returns the default dir to save content to.
    <pre>
    * For Win32/MacOS: Desktop\TriblerDownloads
    * For UNIX:
        If Desktop exists: Desktop\TriblerDownloads
        else: Home\TriblerDownloads
    </pre>
    """
    downloaddir = 'TriblerDownloads'

    if os.path.isdir(downloaddir):
        return os.path.abspath(downloaddir)

    uhome = get_desktop_dir()
    return os.path.join(uhome, downloaddir)
