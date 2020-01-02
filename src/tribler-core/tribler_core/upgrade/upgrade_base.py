
from configobj import ConfigObj

from tribler_core.config.tribler_config import CONFIG_SPEC_PATH, TriblerConfig
from tribler_core.session import Session
from tribler_core.tests.tools.base_test import TriblerCoreTest
from tribler_core.utilities.path_util import Path


class MockTorrentStore(object):
            pass


class AbstractUpgrader(TriblerCoreTest):

    DATABASES_DIR = Path(__file__).parent / u"../data/upgrade_databases/"

    async def setUp(self):
        await super(AbstractUpgrader, self).setUp()
        self.config = TriblerConfig(ConfigObj(configspec=CONFIG_SPEC_PATH.to_text()))
        self.config.set_state_dir(self.getStateDir())
        self.session = Session(self.config)
