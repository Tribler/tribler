import os
from configobj import ConfigObj
from Tribler.Core.simpledefs import STATEDIR_CONFIG


class TriblerConfig(object):

    def __init__(self, session):
        config_path = os.path.join(session.get_state_dir(), STATEDIR_CONFIG)
        self.config = ConfigObj(config_path)

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
