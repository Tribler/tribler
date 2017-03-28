"""
Controls how a TorrentDef is downloaded (rate, where on disk, etc.).

Author(s): Arno Bakker, Egbert Bouman
"""
import copy
import logging

import os
from ConfigParser import ParsingError, MissingSectionHeaderError
from types import StringType

from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.defaults import dldefaults
from Tribler.Core.osutils import get_home_dir
from Tribler.Core.simpledefs import DLMODE_VOD, STATEDIR_DLCONFIG, UPLOAD

logger = logging.getLogger(__name__)


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
        super(DownloadConfigInterface, self).__init__()

        self.dlconfig = dlconfig or CallbackConfigParser()

        # Dumb^WPoor man's versioning of DownloadConfig, add missing default values.
        write = False
        for section, sect_dict in dldefaults.iteritems():
            if not self.dlconfig.has_section(section):
                self.dlconfig.add_section(section)
            for k, v in sect_dict.iteritems():
                if not self.dlconfig.has_option(section, k):
                    write = True
                    self.dlconfig.set(section, k, v)

        if write and self.dlconfig.filename:
            self.dlconfig.write_file()

        if dlconfig:
            # TODO(emilon): I guess this can be removed?
            # modify/fix incorrectly saved dlconfigs
            if dlconfig.has_option('downloadconfig', 'saveas') and isinstance(dlconfig.get('downloadconfig', 'saveas'), tuple):
                dlconfig.set('downloadconfig', 'saveas', dlconfig.get('saveas')[-1])

    def copy(self):
        return DownloadConfigInterface(self.dlconfig.copy())

    def set_dest_dir(self, path):
        """ Sets the directory where to save this Download.
        @param path A path of a directory.
        """
        assert isinstance(path, basestring), path
        self.dlconfig.set('downloadconfig', 'saveas', path)

    def get_dest_dir(self):
        """ Gets the directory where to save this Download.
        """

        dest_dir = self.dlconfig.get('downloadconfig', 'saveas')

        if not dest_dir:
            dest_dir = get_default_dest_dir()
            self.set_dest_dir(dest_dir)

        return dest_dir


    def get_corrected_filename(self):
        """ Gets the directory name where to save this torrent
        """
        return self.dlconfig.get('downloadconfig', 'correctedfilename')

    def set_corrected_filename(self, correctedfilename):
        """ Sets the directory name where to save this torrent
        @param correctedfilename name for multifile directory
        """
        self.dlconfig.set('downloadconfig', 'correctedfilename', correctedfilename)

    def set_mode(self, mode):
        """ Sets the mode of this download.
        @param mode DLMODE_NORMAL/DLMODE_VOD """
        self.dlconfig.set('downloadconfig', 'mode', mode)

    def get_mode(self):
        """ Returns the mode of this download.
        @return DLMODE_NORMAL/DLMODE_VOD """
        return self.dlconfig.get('downloadconfig', 'mode')

    def set_hops(self, hops):
        self.dlconfig.set('downloadconfig', 'hops', hops)

    def get_hops(self):
        return self.dlconfig.get('downloadconfig', 'hops')

    def set_safe_seeding(self, value):
        self.dlconfig.set('downloadconfig', 'safe_seeding', value)

    def get_safe_seeding(self):
        return self.dlconfig.get('downloadconfig', 'safe_seeding')

    def set_seeding_mode(self, value):
        self.dlconfig.set('downloadconfig', 'seeding_mode', value)

    def get_seeding_mode(self):
        return self.dlconfig.get('downloadconfig', 'seeding_mode')

    def set_user_stopped(self, value):
        self.dlconfig.set('downloadconfig', 'user_stopped', value)

    def get_user_stopped(self):
        return self.dlconfig.get('downloadconfig', 'user_stopped')

    def set_time_added(self, value):
        self.dlconfig.set('downloadconfig', 'time_added', value)

    def get_time_added(self):
        return self.dlconfig.get('downloadconfig', 'time_added')

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

        self.dlconfig.set('downloadconfig', 'selected_files', files)

    def get_selected_files(self):
        """ Returns the list of files selected for download.
        @return A list of strings. """
        return self.dlconfig.get('downloadconfig', 'selected_files')

    def set_max_speed(self, direct, speed):
        """ Sets the maximum upload or download speed for this Download.
        @param direct The direction (UPLOAD/DOWNLOAD)
        @param speed The speed in KB/s.
        """
        if direct == UPLOAD:
            self.dlconfig.set('downloadconfig', 'max_upload_rate', speed)
        else:
            self.dlconfig.set('downloadconfig', 'max_download_rate', speed)

    def get_max_speed(self, direct):
        """ Returns the configured maximum speed.
        Returns the speed in KB/s. """
        if direct == UPLOAD:
            return self.dlconfig.get('downloadconfig', 'max_upload_rate')
        else:
            return self.dlconfig.get('downloadconfig', 'max_download_rate')


class DownloadStartupConfig(DownloadConfigInterface):

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
        try:
            dlconfig.read_file(filename)
        except (ParsingError, IOError, MissingSectionHeaderError):
            logger.error("Failed to open download config file: %s", filename)
            raise

        return DownloadStartupConfig(dlconfig)

    load = staticmethod(load)

    def save(self, filename):
        """ Save the DownloadStartupConfig to disk.
        @param filename  An absolute Unicode filename
        """
        # Called by any thread
        self.dlconfig.write_file(filename)

    def copy(self):
        return DownloadStartupConfig(self.dlconfig.copy())


class DefaultDownloadStartupConfig(DownloadStartupConfig):
    """
    This class is used to quickly get information about the default download startup config.
    This is used for instance when adding a new torrent to the downloads. In this case, the default
    download settings should be accessed and displayed to the user.
    """
    __single = None

    def __init__(self, dlconfig=None):

        if DefaultDownloadStartupConfig.__single:
            raise RuntimeError("DefaultDownloadStartupConfig is singleton")
        DefaultDownloadStartupConfig.__single = self

        DownloadStartupConfig.__init__(self, dlconfig=dlconfig)

        self._logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def getInstance(*args, **kw):
        if DefaultDownloadStartupConfig.__single is None:
            DefaultDownloadStartupConfig(*args, **kw)
        return DefaultDownloadStartupConfig.__single

    @staticmethod
    def delInstance(*args, **kw):
        DefaultDownloadStartupConfig.__single = None

    @staticmethod
    def load(filename):
        dlconfig = CallbackConfigParser()
        dlconfig.read_file(filename)
        return DefaultDownloadStartupConfig(dlconfig)

    def copy(self):
        config = CallbackConfigParser()
        config._sections = {'downloadconfig': copy.deepcopy(self.dlconfig._sections['downloadconfig'])}
        return DownloadStartupConfig(config)


def get_default_dest_dir():
    """ Returns the default dir to save content to.
    * If Downloads/ exists: Downloads/TriblerDownloads
        else: Home/TriblerDownloads

    """
    t_downloaddir = u"TriblerDownloads"

    # TODO(emilon): Is this here so the unit tests work?
    if os.path.isdir(t_downloaddir):
        return os.path.abspath(t_downloaddir)

    downloads_dir = os.path.join(get_home_dir(), u"Downloads")
    if os.path.isdir(downloads_dir):
        return os.path.join(downloads_dir, t_downloaddir)
    else:
        return os.path.join(get_home_dir(), t_downloaddir)


def get_default_dscfg_filename(state_dir):
    return os.path.join(state_dir, STATEDIR_DLCONFIG)
