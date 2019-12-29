
from configobj import ConfigObj

from Tribler.Core.Config.tribler_config import CONFIG_SPEC_PATH, TriblerConfig
from Tribler.Core.Session import Session
from Tribler.Core.Utilities.path_util import Path
from Tribler.Test.Core.base_test import TriblerCoreTest


class MockTorrentStore(object):
            pass


class AbstractUpgrader(TriblerCoreTest):

    DATABASES_DIR = Path(__file__).parent / u"../data/upgrade_databases/"

    async def setUp(self):
        await super(AbstractUpgrader, self).setUp()
        self.config = TriblerConfig(ConfigObj(configspec=CONFIG_SPEC_PATH.to_text()))
        self.config.set_state_dir(self.getStateDir())
        self.session = Session(self.config)
