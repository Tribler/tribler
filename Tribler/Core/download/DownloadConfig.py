"""
Controls how a TorrentDef is downloaded (rate, where on disk, etc.).
"""
import logging
import os
from configobj import ConfigObj

from types import StringType

from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.osutils import get_home_dir
from Tribler.Core.simpledefs import DLMODE_VOD

logger = logging.getLogger(__name__)

DEFAULT_DESTINATION_DIR = u"TriblerDownloads"


class DownloadConfig(object):
    """
    A configuration object which holds per-torrent configuration parameters.

    Examples of these parameters are the destination directory, whether
    this download is for video on demand and whether safe seeding is enabled.
    """

    def __init__(self, config=None):
        """
        Create a new DownloadConfig instance.

        First, all default values are loaded using the more general TriblerConfig. Then,
        values are updated if a config is given as argument.

        :param config: a dictionary or ConfigObj instance
        """
        # Create a new ConfigObj out of the section with defaults in the TriblerConfig
        self.config = ConfigObj(TriblerConfig().config["download_defaults"])
        # If options are given, update with these options
        if config:
            self.config.merge(config)

    def copy(self):
        """
        Create a copy of this DownloadConfig.

        :return: a new DownloadConfig with the exact same config options set
        """
        return DownloadConfig(self.config.copy())

    def save(self, filename):
        """
        Save to disk.

        :param filename: an absolute path
        """
        with open(filename, 'w') as output_file:
            self.config.write(output_file)

    def set_destination_dir(self, path):
        """
        Sets the directory where to save this download. This should be an absolute path.

        :param path: a path of a directory.
        """
        self.config['destination_dir'] = path

    def get_destination_dir(self):
        """
        Gets the absolute path of the directory where to save this download.

        If the destination directory is not yet set, the path is created from
        a default and set in the config.

        :return: the currently set destination directory
        """
        if 'destination_dir' in self.config and self.config['destination_dir']:
            return self.config['destination_dir']

        destination_dir = DownloadConfig.get_default_destination_dir()
        self.set_destination_dir(destination_dir)
        return destination_dir

    def has_corrected_filename(self):
        return 'correctedfilename' in self.config

    def get_corrected_filename(self):
        """
        Gets the directory name where to save this torrent.
        """
        return self.config['correctedfilename']

    def set_corrected_filename(self, corrected_filename):
        """
        Sets the directory name where to save this torrent

        :param corrected_filename: name for multifile directory
        """
        self.config['correctedfilename'] = corrected_filename

    def has_mode(self):
        return 'mode' in self.config

    def set_mode(self, mode):
        """
        Sets the mode of this download.

        :param mode: DLMODE_NORMAL or DLMODE_VOD
        """
        self.config['mode'] = mode

    def get_mode(self):
        """
        Returns the mode of this download.

        :return: DLMODE_NORMAL or DLMODE_VOD
        """
        return self.config['mode']

    def set_number_hops(self, value):
        self.config['number_hops'] = value

    def get_number_hops(self):
        return self.config['number_hops']

    def set_safe_seeding_enabled(self, value):
        self.config['safe_seeding_enabled'] = value

    def get_safe_seeding_enabled(self):
        return self.config['safe_seeding_enabled']

    def set_seeding_mode(self, value):
        self.config['seeding_mode'] = value

    def get_seeding_mode(self):
        return self.config['seeding_mode']

    def set_seeding_ratio(self, value):
        self.config['seeding_ratio'] = value

    def get_seeding_ratio(self):
        return self.config['seeding_ratio']

    def set_seeding_time(self, value):
        self.config['seeding_time'] = value

    def get_seeding_time(self):
        return self.config['seeding_time']

    def has_time_added(self):
        return 'time_added' in self.config

    def set_time_added(self, value):
        self.config['time_added'] = value

    def get_time_added(self):
        return self.config['time_added']

    def set_selected_files(self, files):
        """
        Select which files in the torrent to download.

        The filenames must be the names as they appear in the content def, including
        encoding. Trivially, when the torrent contains a file 'sjaak.avi' the files
        parameter must be 'sjaak.avi'. When the content def is a torrent def
        and contains multiple files and is named 'filecollection', the files
        parameter must be
            os.path.join('filecollection','sjaak.avi')

        :param files: a single filename or a list of filenames (e.g.
        ['harry.avi','sjaak.avi']). Not Unicode strings!
        """
        # TODO: can't check if files exists, don't have tdef here.... bugger
        if isinstance(files, StringType):  # convenience
            files = [files]

        if self.has_mode() and self.get_mode() == DLMODE_VOD and len(files) > 1:
            raise ValueError("In Video-On-Demand mode only 1 file can be selected for download")

        self.config['selected_files'] = files

    def get_selected_files(self):
        """
        Returns the list of files selected for download.

        :return: a list of strings.
        """
        return self.config['selected_files']

    def values(self):
        """
        Returns
        :return:
        """

    @staticmethod
    def get_default_destination_dir():
        """
        Returns the default destination directory to save content to.

        Returns an absolute path of the default destination directory.
        If there is a "Downloads" directory in the home folder, the
        destination directory is created as a subdirectory of that folder.

        :return: the absolute path of the default destination directory
        """
        # TODO: Is this here so the unit tests work?
        if os.path.isdir(DEFAULT_DESTINATION_DIR):
            return os.path.abspath(DEFAULT_DESTINATION_DIR)

        # Make it a subdirectory of the "Downloads" directory if it exists
        downloads_dir = os.path.join(get_home_dir(), u"Downloads")
        if os.path.isdir(downloads_dir):
            return os.path.join(downloads_dir, DEFAULT_DESTINATION_DIR)
        else:
            return os.path.join(get_home_dir(), DEFAULT_DESTINATION_DIR)
