import base64
from pathlib import Path

from configobj import ConfigObj

import libtorrent as lt

from validate import Validator

from tribler_core.exceptions import InvalidConfigException
from tribler_core.utilities import path_util
from tribler_core.utilities.install_dir import get_lib_path
from tribler_core.utilities.osutils import get_home_dir
from tribler_core.utilities.path_util import str_path
from tribler_core.utilities.utilities import bdecode_compat

SPEC_FILENAME = 'download_config.spec'
CONFIG_SPEC_PATH = get_lib_path() / 'modules' / 'libtorrent' / SPEC_FILENAME
NONPERSISTENT_DEFAULTS = {}


class DownloadConfig:
    def __init__(self, config=None, state_dir=None):
        self.config = config or ConfigObj(configspec=str(CONFIG_SPEC_PATH), default_encoding='utf8')
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
        return DownloadConfig(ConfigObj(infile=str_path(config_path), file_error=True,
                                        configspec=str(CONFIG_SPEC_PATH), default_encoding='utf-8'))

    def copy(self):
        return DownloadConfig(ConfigObj(self.config, configspec=str(CONFIG_SPEC_PATH), default_encoding='utf-8'),
                              state_dir=self.state_dir)

    def write(self, filename):
        self.config.filename = str_path(filename)
        self.config.write()

    def set_dest_dir(self, path):
        """ Sets the directory where to save this Download.
        @param path A path of a directory.
        """
        # If something is saved inside the Tribler state dir, it should use relative path
        path = Path(path)
        if self.state_dir:
            base_path = self.state_dir
            path = path_util.norm_path(base_path, path)
        self.config['download_defaults']['saveas'] = str(path)

    def get_dest_dir(self):
        """ Gets the directory where to save this Download.
        """
        dest_dir = self.config['download_defaults']['saveas']
        if not dest_dir:
            dest_dir = get_default_dest_dir()
            self.set_dest_dir(dest_dir)

        # This is required to support relative paths
        if not path_util.isabs(dest_dir):
            dest_dir = self.state_dir / dest_dir

        return Path(dest_dir)

    def set_hops(self, hops):
        self.config['download_defaults']['hops'] = hops

    def get_hops(self):
        return self.config['download_defaults']['hops']

    def set_safe_seeding(self, value):
        self.config['download_defaults']['safe_seeding'] = value

    def get_safe_seeding(self):
        return self.config['download_defaults']['safe_seeding']

    def set_user_stopped(self, value):
        self.config['download_defaults']['user_stopped'] = value

    def get_user_stopped(self):
        return self.config['download_defaults']['user_stopped']

    def set_share_mode(self, value):
        self.config['download_defaults']['share_mode'] = value

    def get_share_mode(self):
        return self.config['download_defaults']['share_mode']

    def set_upload_mode(self, value):
        self.config['download_defaults']['upload_mode'] = value

    def get_upload_mode(self):
        return self.config['download_defaults']['upload_mode']

    def set_time_added(self, value):
        self.config['download_defaults']['time_added'] = value

    def get_time_added(self):
        return self.config['download_defaults']['time_added']

    def set_selected_files(self, file_indexes):
        """ Select which files in the torrent to download.
        @param file_indexes List of file indexes as ordered in the torrent (e.g. [0,1])
        """
        self.config['download_defaults']['selected_file_indexes'] = file_indexes

    def get_selected_files(self):
        """ Returns the list of files selected for download.
        @return A list of file indexes. """
        return self.config['download_defaults']['selected_file_indexes']

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
        return bdecode_compat(base64.b64decode(self.config['state']['metainfo'].encode('utf-8')))

    def set_engineresumedata(self, engineresumedata):
        self.config['state']['engineresumedata'] = base64.b64encode(lt.bencode(engineresumedata)).decode('utf-8')

    def get_engineresumedata(self):
        return bdecode_compat(base64.b64decode(self.config['state']['engineresumedata'].encode('utf-8')))


def get_default_dest_dir():
    """
    Returns the default dir to save content to.

    If Downloads/ exists: Downloads/TriblerDownloads
    else: Home/TriblerDownloads
    """
    download_dir = Path("TriblerDownloads")

    # TODO: Is this here so the unit tests work?
    if download_dir.is_dir():
        return path_util.abspath(download_dir)

    downloads_dir = get_home_dir() / u"Downloads"
    if downloads_dir.is_dir():
        return downloads_dir / download_dir
    return get_home_dir() / download_dir
