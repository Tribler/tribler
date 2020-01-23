from __future__ import absolute_import

import os

from configobj import ConfigObj

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Config.tribler_config import CONFIG_SPEC_PATH, TriblerConfig
from Tribler.Core.Session import Session
from Tribler.Test.Core.base_test import TriblerCoreTest


class MockTorrentStore(object):
            pass


class AbstractUpgrader(TriblerCoreTest):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    DATABASES_DIR = os.path.abspath(os.path.join(FILE_DIR, u"../data/upgrade_databases/"))

    @inlineCallbacks
    def setUp(self):
        yield super(AbstractUpgrader, self).setUp()
        self.config = TriblerConfig(ConfigObj(configspec=CONFIG_SPEC_PATH))
        self.config.set_root_state_dir(self.getRootStateDir())
        self.session = Session(self.config)
