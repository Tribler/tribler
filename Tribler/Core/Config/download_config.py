import base64

from configobj import ConfigObj

import libtorrent as lt

from validate import Validator

from Tribler.Core.Utilities import path_util
from Tribler.Core.Utilities.install_dir import get_lib_path
from Tribler.Core.Utilities.path_util import Path
from Tribler.Core.Utilities.utilities import bdecode_compat
from Tribler.Core.exceptions import InvalidConfigException
from Tribler.Core.osutils import get_home_dir
from Tribler.Core.simpledefs import DLMODE_NORMAL, DLMODE_VOD

SPEC_FILENAME = 'download_config.spec'
CONFIG_SPEC_PATH = get_lib_path() / 'Core' / 'Config' / SPEC_FILENAME
NONPERSISTENT_DEFAULTS = {'mode': DLMODE_NORMAL}


class DownloadConfig(object):
    def __init__(self, config=None, state_dir=None):
        self.config = config or ConfigObj(configspec=CONFIG_SPEC_PATH.to_text(), default_encoding='utf8')
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
        return DownloadConfig(ConfigObj(infile=config_path.to_text(), file_error=True,
                                        configspec=CONFIG_SPEC_PATH.to_text(), default_encoding='utf-8'))

    def copy(self):
        return DownloadConfig(ConfigObj(self.config, configspec=CONFIG_SPEC_PATH.to_text(), default_encoding='utf-8'))

    def write(self, filename):
        self.config.filename = filename
        self.config.write()

    def set_dest_dir(self, path):
        """ Sets the directory where to save this Download.
        @param path A path of a directory.
        """
        # If something is saved inside the Tribler state dir, it should use relative path
        path = path_util.Path(path)
        if self.state_dir:
            base_path = self.state_dir
            path = path_util.norm_path(base_path, path)
        self.config['download_defaults']['saveas'] = path.to_text()

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

        return path_util.Path(dest_dir)

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

    def set_upload_mode(self, value):
        self.config['download_defaults']['upload_mode'] = value

    def get_upload_mode(self):
        return self.config['download_defaults']['upload_mode']

    def set_time_added(self, value):
        self.config['download_defaults']['time_added'] = value

    def get_time_added(self):
        return self.config['download_defaults']['time_added']

    def set_selected_files(self, files):
        """ Select which files in the torrent to download. The filenames must
        be the names as they appear in the content def, including encoding.

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
