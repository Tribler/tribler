"""
Configuration object for the Tribler Core.
"""
import logging
import traceback
from pathlib import Path

from configobj import ConfigObj, ParseError
from validate import Validator

from tribler_core.config.config_registry import SPECIFICATION_REGISTRY
from tribler_core.exceptions import InvalidConfigException


# fmt: off


class TriblerConfig:
    def __init__(self, state_dir=Path()):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f'Init. State dir: {state_dir}')

        self.error = None
        self.file = None
        self.config = None

        self.state_dir = state_dir
        self.create_empty_config()

    def create_empty_config(self):
        self.logger.info('Create an empty config')

        self.config = TriblerConfig._load()
        self.validate()

    def load(self, file: Path = None, reset_config_on_error=False):
        self.logger.info(f'Load: {file}. Reset config on error: {reset_config_on_error}')
        self.file = file
        self.error = None

        try:
            self.config = TriblerConfig._load(file)
        except ParseError:
            self.error = traceback.format_exc()
            self.logger.warning(f'Error: {self.error}')

            if not reset_config_on_error:
                raise

        if self.error and reset_config_on_error:
            self.logger.info('Create a default config')

            self.config = TriblerConfig._load(None)
            self.write(file=file)

        return self.validate()

    @staticmethod
    def _load(file=None):
        full_specification = []

        # merge specifications
        for specification in SPECIFICATION_REGISTRY:
            with open(specification, encoding='utf-8') as f:
                full_specification.extend(f.readlines())

        file = str(file) if file else None
        return ConfigObj(infile=file, configspec=full_specification, default_encoding='utf-8')

    def write(self, file: Path = None):
        if not file:
            file = self.file  # try to remember a file from the last load

        self.logger.info(f'Write: {file}')

        if not file:
            return

        parent = Path(file).parent
        if not parent.exists():
            self.logger.info(f'Create folder: {parent}')
            parent.mkdir(parents=True)

        self.config.filename = file
        self.config.write()

    def validate(self):
        result = self.config.validate(Validator())
        self.logger.info(f'Validation result: {result}')

        if result is not True:
            raise InvalidConfigException(msg=f"TriblerConfig is invalid: {str(result)}")

        return self

    def copy(self):
        self.logger.info('Copy')

        new_config = TriblerConfig(self.state_dir)
        new_config.config = ConfigObj(infile=self.config.copy(),
                                      configspec=self.config.configspec,
                                      default_encoding='utf-8')

        for section in self.config:
            new_config.config[section] = self.config[section].copy()

        return new_config

    @property
    def state_dir(self):
        return self._state_dir

    @state_dir.setter
    def state_dir(self, value):
        self._state_dir = Path(value)

    def put_path(self, section_name, property_name, value):
        """Save a relative path if 'value' is relative to state_dir.
        Save an absolute path overwise.
        """
        if value is not None:
            # try to put a relative path (if it possible)
            try:
                value = Path(value).relative_to(self.state_dir)
            except ValueError:  # `path` is not in the subpath of `self.state_dir`
                pass
            value = str(value)

        self.config[section_name][property_name] = value
        return self

    def get_path(self, section_name, property_name):
        """Get a path.

        Returns: an absolute path.
        """
        value = self.config[section_name][property_name]
        if value is None:
            return None

        path = Path(self.config[section_name][property_name])

        if path.is_absolute():
            return path

        return self.state_dir / path

    def put(self, section_name, property_name, value):
        self.config[section_name][property_name] = value
        return self

    def get(self, section_name, property_name):
        return self.config[section_name][property_name]
