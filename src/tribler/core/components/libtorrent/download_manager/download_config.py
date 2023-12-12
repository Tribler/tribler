import base64
from typing import Dict, Optional

from configobj import ConfigObj
from validate import Validator

from tribler.core.components.libtorrent.settings import DownloadDefaultsSettings, get_default_download_dir
from tribler.core.components.libtorrent.utils.libtorrent_helper import libtorrent as lt
from tribler.core.exceptions import InvalidConfigException
from tribler.core.utilities.install_dir import get_lib_path
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.utilities import bdecode_compat

SPEC_FILENAME = 'download_config.spec'
CONFIG_SPEC_PATH = get_lib_path() / 'components/libtorrent/download_manager' / SPEC_FILENAME
NONPERSISTENT_DEFAULTS = {}


def _from_dict(value: Dict) -> str:
    binary = lt.bencode(value)
    base64_bytes = base64.b64encode(binary)
    return base64_bytes.decode('utf-8')


def _to_dict(value: str) -> Optional[Dict]:
    binary = value.encode('utf-8')
    # b'==' is added to avoid incorrect padding
    base64_bytes = base64.b64decode(binary + b'==')
    return bdecode_compat(base64_bytes)


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
            raise InvalidConfigException(f"DownloadConfig is invalid: {str(validation_result)}")

    @staticmethod
    def load(config_path=None):
        return DownloadConfig(ConfigObj(infile=Path.fix_win_long_file(config_path), file_error=True,
                                        configspec=str(CONFIG_SPEC_PATH), default_encoding='utf-8'))

    @staticmethod
    def from_defaults(settings: DownloadDefaultsSettings, state_dir=None):
        config = DownloadConfig(state_dir=state_dir)

        config.set_hops(settings.number_hops)
        config.set_safe_seeding(settings.safeseeding_enabled)
        config.set_dest_dir(settings.saveas)

        return config

    def copy(self):
        return DownloadConfig(ConfigObj(self.config, configspec=str(CONFIG_SPEC_PATH), default_encoding='utf-8'),
                              state_dir=self.state_dir)

    def write(self, filename: Path):
        self.config.filename = Path.fix_win_long_file(filename)
        self.config.write()

    def set_dest_dir(self, path):
        """ Sets the directory where to save this Download.
        @param path A path of a directory.
        """
        # If something is saved inside the Tribler state dir, it should use relative path
        path = Path(path).normalize_to(self.state_dir)
        self.config['download_defaults']['saveas'] = str(path)

    def get_dest_dir(self):
        """ Gets the directory where to save this Download.
        """
        dest_dir = self.config['download_defaults']['saveas']
        if not dest_dir:
            dest_dir = get_default_download_dir()
            self.set_dest_dir(dest_dir)

        # This is required to support relative paths
        if not Path(dest_dir).is_absolute():
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

    def set_bootstrap_download(self, value):
        self.config['download_defaults']['bootstrap_download'] = value

    def get_bootstrap_download(self):
        return self.config['download_defaults']['bootstrap_download']

    def set_metainfo(self, metainfo: Dict):
        self.config['state']['metainfo'] = _from_dict(metainfo)

    def get_metainfo(self) -> Optional[Dict]:
        return _to_dict(self.config['state']['metainfo'])

    def set_engineresumedata(self, engineresumedata: Dict):
        self.config['state']['engineresumedata'] = _from_dict(engineresumedata)

    def get_engineresumedata(self) -> Optional[Dict]:
        return _to_dict(self.config['state']['engineresumedata'])
