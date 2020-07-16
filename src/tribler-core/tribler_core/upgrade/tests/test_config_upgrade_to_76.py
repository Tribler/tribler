import os
import shutil

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.tests.tools.base_test import TriblerCoreTest
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.upgrade.config_converter import convert_config_to_tribler76


class TestConfigUpgradeto76(TriblerCoreTest):
    """
    Contains tests that test the config conversion from 7.5
    """
    CONFIG_PATH = TESTS_DATA_DIR / "config_files"

    def test_convert_tribler_conf_76(self):
        """
        Tests conversion of the Tribler 7.5 config
        """
        os.makedirs(self.state_dir)
        shutil.copy2(self.CONFIG_PATH / 'triblerd75.conf', self.state_dir / 'triblerd.conf')
        convert_config_to_tribler76(self.state_dir)
        new_config = TriblerConfig(self.state_dir, self.state_dir / 'triblerd.conf')
        self.assertEqual(new_config.get_api_key(), '7671750ba34423c97dc3c6763041e4cb')
        self.assertEqual(new_config.get_api_http_port(), 8085)
        self.assertEqual(new_config.get_api_http_enabled(), True)
        self.assertEqual(new_config.get_api_https_enabled(), False)
