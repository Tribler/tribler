from __future__ import annotations

import logging
import traceback
from pathlib import Path
from typing import Optional

import configobj
from configobj import ParseError

from pydantic import PrivateAttr

from tribler_core.config.tribler_config_sections import TriblerConfigSections

logger = logging.getLogger('Tribler Config')


class TriblerConfig(TriblerConfigSections):
    """ Tribler config class that contains common logic for manipulating with a config.
    """
    _state_dir: Path = PrivateAttr()
    _file: Optional[Path] = PrivateAttr()  # a last file saved during write-load operations
    _error: Optional[Exception] = PrivateAttr()

    # Special configuration options related to the operation mode of the Core
    upgrader_enabled: bool = True
    gui_test_mode: bool = False

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

        dictionary = self.dict(exclude_defaults=True,
                               exclude={'upgrader_enabled': ...,
                                        'gui_test_mode': ...,
                                        'tunnel_community': {'socks5_listen_ports': ...},
                                        'libtorrent': {'anon_proxy_server_ports': ...,
                                                       'anon_proxy_type': ...,
                                                       'anon_proxy_auth': ...,
                                                       'anon_listen_port': ...,
                                                       'anon_proxy_server_ip': ...}})
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
