from pathlib import Path

from configobj import ConfigObj

from tribler_core.config.tribler_config import CONFIG_SPEC_PATH, TriblerConfig
from tribler_core.session import Session
from tribler_core.tests.tools.base_test import TriblerCoreTest


class MockTorrentStore:
            pass


class AbstractUpgrader(TriblerCoreTest):

    DATABASES_DIR = Path(__file__).parent / "../data/upgrade_databases/"

    async def setUp(self):
        await super(AbstractUpgrader, self).setUp()
        self.config = TriblerConfig(ConfigObj(configspec=str(CONFIG_SPEC_PATH)))
        self.config.set_state_dir(self.getStateDir())
        self.session = Session(self.config)
