from __future__ import annotations

import logging
import traceback
from pathlib import Path
from typing import Optional

import configobj
from configobj import ParseError
from pydantic import BaseSettings, Extra, PrivateAttr

from tribler_core.modules.bandwidth_accounting.settings import BandwidthAccountingSettings
from tribler_core.modules.libtorrent.settings import DownloadDefaultsSettings, LibtorrentSettings
from tribler_core.modules.metadata_store.settings import ChantSettings
from tribler_core.modules.popularity.settings import PopularityCommunitySettings
from tribler_core.modules.resource_monitor.settings import ResourceMonitorSettings
from tribler_core.modules.settings import BootstrapSettings, DHTSettings, DiscoveryCommunitySettings, Ipv8Settings, \
    TrustchainSettings, WatchFolderSettings
from tribler_core.modules.torrent_checker.settings import TorrentCheckerSettings
from tribler_core.modules.tunnel.community.settings import TunnelCommunitySettings
from tribler_core.restapi.settings import APISettings
from tribler_core.settings import ErrorHandlingSettings, GeneralSettings

logger = logging.getLogger('Tribler Config')


class TriblerConfigSections(BaseSettings):
    """ Base Tribler config class that contains section listing

    A corresponding class that contains methods (load, save etc.) see below.
    """

    class Config:
        extra = Extra.ignore  # ignore extra attributes during model initialization

    general: GeneralSettings = GeneralSettings()
    error_handling: ErrorHandlingSettings = ErrorHandlingSettings()
    tunnel_community: TunnelCommunitySettings = TunnelCommunitySettings()
    bandwidth_accounting: BandwidthAccountingSettings = BandwidthAccountingSettings()
    bootstrap: BootstrapSettings = BootstrapSettings()
    ipv8: Ipv8Settings = Ipv8Settings()
    discovery_community: DiscoveryCommunitySettings = DiscoveryCommunitySettings()
    dht: DHTSettings = DHTSettings()
    trustchain: TrustchainSettings = TrustchainSettings()
    watch_folder: WatchFolderSettings = WatchFolderSettings()
    chant: ChantSettings = ChantSettings()
    torrent_checking: TorrentCheckerSettings = TorrentCheckerSettings()
    libtorrent: LibtorrentSettings = LibtorrentSettings()
    download_defaults: DownloadDefaultsSettings = DownloadDefaultsSettings()
    api: APISettings = APISettings()
    resource_monitor: ResourceMonitorSettings = ResourceMonitorSettings()
    popularity_community: PopularityCommunitySettings = PopularityCommunitySettings()


class TriblerConfig(TriblerConfigSections):
    """ Tribler config class that contains common logic for manipulating with a config.
    """
    _state_dir: Path = PrivateAttr()
    _file: Optional[Path] = PrivateAttr()  # a last file saved during write-load operations
    _error: Optional[Exception] = PrivateAttr()

    def __init__(self, *args, state_dir: Path = None, file: Path = None, error: str = None, **kwargs):
        """ Constructor

        Args:
            *args: Arguments that will be passed to the `BaseSettings` constructor.
            state_dir: Tribler's state dir. Will be used for calculated relative paths.
            file: A config file.
            error: A last error.
            **kwargs: Arguments that will be passed to the `BaseSettings` constructor.
        """
        super().__init__(*args, **kwargs)
        logger.info(f'Init. State dir: {state_dir}. File: {file}')

        self.set_state_dir(state_dir)
        self.set_file(file)

        self._error = error

    @staticmethod
    def load(file: Path, state_dir: Path, reset_config_on_error: bool = False) -> TriblerConfig:
        """ Load a config from a file

        Args:
            file: A path to the config file.
            state_dir: A Tribler's state dir.
            reset_config_on_error: Ф flag that shows whether it is necessary to
                create a new config in case of an error.

        Returns: `TriblerConfig` instance.
        """
        logger.info(f'Load: {file}. State dir: {state_dir}. Reset config on error: {reset_config_on_error}')
        error = None
        config = None

        try:
            dictionary = configobj.ConfigObj(infile=str(file))
            config = TriblerConfig.parse_obj(dictionary)
            config.set_state_dir(state_dir)
            config.set_file(file)
        except (ParseError, ValueError) as e:
            logger.error(e)
            if not reset_config_on_error:
                raise
            error = traceback.format_exc()

        if error:
            logger.info('Resetting a config')
            config = TriblerConfig(state_dir=state_dir, file=file, error=error)
            config.write(file=file)

        return config

    def write(self, file: Path = None):
        """Save a config to a file

        Args:
            file: Path to the config. In case it is omitted, last file will be used.
        """
        if not file:
            file = self._file  # try to remember a file from the last load-write

        logger.info(f'Write: {file}')
        self._file = file

        if not file:
            return

        parent = Path(file).parent
        if not parent.exists():
            logger.info(f'Create folder: {parent}')
            parent.mkdir(parents=True)

        dictionary = self.dict(exclude_defaults=True)
        conf = configobj.ConfigObj(dictionary)
        conf.filename = str(file)
        conf.write()

    @property
    def error(self) -> Optional[str]:
        return self._error

    @property
    def state_dir(self) -> Optional[Path]:
        return self._state_dir

    def set_state_dir(self, val):
        self._state_dir = Path(val) if val is not None else None

    @property
    def file(self) -> Optional[Path]:
        return self._file

    def set_file(self, val):
        self._file = Path(val) if val is not None else None
