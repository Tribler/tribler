import os
from configobj import ConfigObj
from validate import Validator
from Tribler.Core.Utilities.install_dir import get_lib_path
from Tribler.Core.simpledefs import STATEDIR_CONFIG


CONFIGSPEC_PATH = os.path.join(get_lib_path(), 'Core', 'Config', 'config.spec')


class TriblerConfig(object):

    def __init__(self, session):
        config_path = os.path.join(session.get_state_dir(), STATEDIR_CONFIG)
        self.config = ConfigObj(config_path, configspec=CONFIGSPEC_PATH)

        validator = Validator()
        self.config.validate(validator, copy=True)
        self.config.write()

        if "user_download_states" not in self.config:
            self.config["user_download_states"] = {}

    def get_download_state(self, infohash):
        if infohash.encode('hex') in self.config["user_download_states"]:
            return self.config["user_download_states"][infohash.encode('hex')]
        return None

    def remove_download_state(self, infohash):
        if infohash.encode('hex') in self.config["user_download_states"]:
            del self.config["user_download_states"][infohash.encode('hex')]
            self.config.write()

    def set_download_state(self, infohash, value):
        self.config["user_download_states"][infohash.encode('hex')] = value
        self.config.write()

    def get_download_states(self):
        return dict((key.decode('hex'), value) for key, value in self.config["user_download_states"].iteritems())

    #
    # General
    #
    def set_family_filter_enabled(self, value):
        self.config['general']['family_filter'] = value
        self.config.write()

    def get_family_filter_enabled(self):
        return self.config['general']['family_filter']
