from __future__ import absolute_import

import base64
import os

from configobj import ConfigObj

import libtorrent as lt

from six import string_types

from validate import Validator

from Tribler.Core.Utilities.install_dir import get_lib_path
from Tribler.Core.exceptions import InvalidConfigException
from Tribler.Core.osutils import get_home_dir
from Tribler.Core.simpledefs import DLMODE_NORMAL, DLMODE_VOD


SPEC_FILENAME = 'download_config.spec'
CONFIG_SPEC_PATH = os.path.join(get_lib_path(), 'Core', 'Config', SPEC_FILENAME)
NONPERSISTENT_DEFAULTS = {'mode': DLMODE_NORMAL}


class DownloadConfig(object):
    def __init__(self, config=None, state_dir=None):
        self.config = config or ConfigObj(configspec=CONFIG_SPEC_PATH, default_encoding='utf8')
        # Values that should not be stored and should be initialized to some default value
        self.nonpersistent = NONPERSISTENT_DEFAULTS.copy()
        self.state_dir = state_dir
        self.validate()

    def validate(self):
        """
        Validate the ConfigObj using Validator.

        Note that `validate()` returns `True` if the ConfigObj is correct and a dictionary with `True` and `False`
        values for keys who's validation failed if at least one key was found to be incorrect.
        """
        validator = Validator()
        validation_result = self.config.validate(validator)
        if validation_result is not True:
            raise InvalidConfigException(msg="DownloadConfig is invalid: %s" % str(validation_result))

    @staticmethod
    def load(config_path=None):
        return DownloadConfig(ConfigObj(infile=config_path, file_error=True,
                                        configspec=CONFIG_SPEC_PATH, default_encoding='utf-8'))

    def copy(self):
        return DownloadConfig(ConfigObj(self.config, configspec=CONFIG_SPEC_PATH, default_encoding='utf-8'))

    def write(self, filename):
        self.config.filename = filename
        self.config.write()

    def set_dest_dir(self, path):
        """ Sets the directory where to save this Download.
        @param path A path of a directory.
        """
        # If something is saved inside the Tribler state dir, it should use relative path
        if self.state_dir:
            base_path = self.state_dir
            if base_path == os.path.commonprefix([path, base_path]):
                path = os.path.relpath(path, base_path)
        assert isinstance(path, string_types), path
        self.config['download_defaults']['saveas'] = path

    def get_dest_dir(self):
        """ Gets the directory where to save this Download.
        """
        dest_dir = self.config['download_defaults']['saveas']
        if not dest_dir:
            dest_dir = get_default_dest_dir()
            self.set_dest_dir(dest_dir)

        # This is required to support relative paths
        if not os.path.isabs(dest_dir):
            dest_dir = os.path.join(self.state_dir, dest_dir)

        return dest_dir

    def get_corrected_filename(self):
        """ Gets the directory name where to save this torrent
        """
        return self.config['download_defaults']['correctedfilename']

    def set_corrected_filename(self, correctedfilename):
        """ Sets the directory name where to save this torrent
        @param correctedfilename name for multifile directory
        """
        self.config['download_defaults']['correctedfilename'] = correctedfilename

    def set_mode(self, mode):
        """ Sets the mode of this download.
        @param mode DLMODE_NORMAL/DLMODE_VOD """
        self.nonpersistent['mode'] = mode

    def get_mode(self):
        """ Returns the mode of this download.
        @return DLMODE_NORMAL/DLMODE_VOD """
        return self.nonpersistent['mode']

    def set_hops(self, hops):
        self.config['download_defaults']['hops'] = hops

    def get_hops(self):
        return self.config['download_defaults']['hops']

    def set_safe_seeding(self, value):
        self.config['download_defaults']['safe_seeding'] = value

    def get_safe_seeding(self):
        return self.config['download_defaults']['safe_seeding']

    def set_seeding_mode(self, value):
        self.config['download_defaults']['seeding_mode'] = value

    def get_seeding_mode(self):
        return self.config['download_defaults']['seeding_mode']

    def set_seeding_time(self, value):
        self.config['download_defaults']['seeding_time'] = value

    def get_seeding_time(self):
        return self.config['download_defaults']['seeding_time']

    def set_seeding_ratio(self, value):
        self.config['download_defaults']['seeding_ratio'] = value

    def get_seeding_ratio(self):
        return self.config['download_defaults']['seeding_ratio']

    def set_credit_mining(self, value):
        self.config['download_defaults']['credit_mining'] = value

    def get_credit_mining(self):
        return bool(self.config['download_defaults']['credit_mining'])

    def set_user_stopped(self, value):
        self.config['download_defaults']['user_stopped'] = value

    def get_user_stopped(self):
        return self.config['download_defaults']['user_stopped']

    def set_share_mode(self, value):
        self.config['download_defaults']['share_mode'] = value

    def get_share_mode(self):
        return self.config['download_defaults']['share_mode']

    def set_time_added(self, value):
        self.config['download_defaults']['time_added'] = value

    def get_time_added(self):
        return self.config['download_defaults']['time_added']

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
        if isinstance(files, str):  # convenience
            files = [files]

        if self.get_mode() == DLMODE_VOD and len(files) > 1:
            raise ValueError("In Video-On-Demand mode only 1 file can be selected for download")

        self.config['download_defaults']['selected_files'] = files

    def get_selected_files(self):
        """ Returns the list of files selected for download.
        @return A list of strings. """
        return self.config['download_defaults']['selected_files']

    def set_channel_download(self, value):
        self.config['download_defaults']['channel_download'] = value

    def get_channel_download(self):
        return bool(self.config['download_defaults']['channel_download'])

    def set_add_to_channel(self, value):
        self.config['download_defaults']['add_to_channel'] = value

    def get_add_to_channel(self):
        return bool(self.config['download_defaults']['add_to_channel'])

    def set_bootstrap_download(self, value):
        self.config['download_defaults']['bootstrap_download'] = value

    def get_bootstrap_download(self):
        return self.config['download_defaults']['bootstrap_download']

    def set_metainfo(self, metainfo):
        self.config['state']['metainfo'] = base64.b64encode(lt.bencode(metainfo)).decode('utf-8')

    def get_metainfo(self):
        return lt.bdecode(base64.b64decode(self.config['state']['metainfo'].encode('utf-8')))

    def set_engineresumedata(self, engineresumedata):
        self.config['state']['engineresumedata'] = base64.b64encode(lt.bencode(engineresumedata)).decode('utf-8')

    def get_engineresumedata(self):
        return lt.bdecode(base64.b64decode(self.config['state']['engineresumedata'].encode('utf-8')))


def get_default_dest_dir():
    """
    Returns the default dir to save content to.

    If Downloads/ exists: Downloads/TriblerDownloads
    else: Home/TriblerDownloads
    """
    download_dir = u"TriblerDownloads"

    # TODO: Is this here so the unit tests work?
    if os.path.isdir(download_dir):
        return os.path.abspath(download_dir)

    downloads_dir = os.path.join(get_home_dir(), u"Downloads")
    if os.path.isdir(downloads_dir):
        return os.path.join(downloads_dir, download_dir)
    return os.path.join(get_home_dir(), download_dir)
