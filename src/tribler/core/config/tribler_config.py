from __future__ import annotations

import logging
import traceback
from pathlib import Path
from typing import Any, Dict, Optional, Union

import configobj
from configobj import ParseError
from pydantic import BaseSettings, Extra, PrivateAttr, validate_model

from tribler.core.components.ipv8.settings import (
    BootstrapSettings,
    DHTSettings,
    DiscoveryCommunitySettings,
    Ipv8Settings,
)
from tribler.core.components.key.settings import TrustchainSettings
from tribler.core.components.libtorrent.settings import DownloadDefaultsSettings, LibtorrentSettings
from tribler.core.components.content_discovery.settings import ContentDiscoveryComponentConfig
from tribler.core.components.database.settings import ChantSettings
from tribler.core.components.resource_monitor.settings import ResourceMonitorSettings
from tribler.core.components.restapi.rest.settings import APISettings
from tribler.core.components.torrent_checker.settings import TorrentCheckerSettings
from tribler.core.components.tunnel.settings import TunnelCommunitySettings
from tribler.core.components.watch_folder.settings import WatchFolderSettings
from tribler.core.settings import GeneralSettings

logger = logging.getLogger('Tribler Config')

DEFAULT_CONFIG_NAME = 'triblerd.conf'


class TriblerConfig(BaseSettings):
    """ Tribler config class that contains common logic for manipulating with a config."""

    class Config:
        extra = Extra.ignore  # ignore extra attributes during model initialization

    general: GeneralSettings = GeneralSettings()
    tunnel_community: TunnelCommunitySettings = TunnelCommunitySettings()
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
    content_discovery_community: ContentDiscoveryComponentConfig = ContentDiscoveryComponentConfig()

    # Special configuration options related to the operation mode of the Core
    upgrader_enabled: bool = True
    gui_test_mode: bool = False

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
        if not file and state_dir:
            file = state_dir / DEFAULT_CONFIG_NAME  # assign default file name

        self.set_state_dir(state_dir)
        self.set_file(file)

        self._error = error
        logger.info(f'Init. State dir: {state_dir}. File: {file}')

    @staticmethod
    def load(state_dir: Path, file: Path = None, reset_config_on_error: bool = False) -> TriblerConfig:
        """ Load a config from a file

        Args:
            state_dir: A Tribler's state dir.
            file: A path to the config file.
            reset_config_on_error: a flag that shows whether it is necessary to
                create a new config in case of an error.
        Returns: `TriblerConfig` instance.
        """
        file = file or state_dir / DEFAULT_CONFIG_NAME
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

        dictionary = self.dict(exclude_defaults=True,
                               exclude={'upgrader_enabled': ...,
                                        'gui_test_mode': ...,
                                        'tunnel_community': {'socks5_listen_ports': ...},
                                        'libtorrent': {'anon_proxy_server_ports': ...,
                                                       'anon_proxy_type': ...,
                                                       'anon_proxy_auth': ...,
                                                       'anon_listen_port': ...,
                                                       'anon_proxy_server_ip': ...}})
        conf = configobj.ConfigObj(dictionary, encoding='utf-8')
        conf.filename = str(file)
        conf.write()

    def update_from_dict(self, config: Dict):
        """ Update (patch) current config from dictionary"""

        def update_recursively(settings: BaseSettings, attribute_name: str, attribute_value: Union[Any, Dict]):
            """ Update setting recursively from dictionary"""
            if isinstance(attribute_value, dict):
                for k, v in attribute_value.items():
                    update_recursively(getattr(settings, attribute_name), k, v)
            else:
                setattr(settings, attribute_name, attribute_value)

        for key, value in config.items():
            update_recursively(self, key, value)

        self.validate_config()

    def validate_config(self):
        """ Validate config and raise an exception in case of an error"""
        *_, error = validate_model(self.__class__, self.__dict__)
        if error:
            raise error

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
