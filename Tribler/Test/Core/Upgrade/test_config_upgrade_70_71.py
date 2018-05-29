import os
import shutil
from ConfigParser import RawConfigParser

from Tribler.Core.simpledefs import STATEDIR_DLPSTATE_DIR
from configobj import ConfigObj

from Tribler.Core.Config.tribler_config import TriblerConfig, CONFIG_SPEC_PATH
from Tribler.Core.Upgrade.config_converter import add_libtribler_config, add_tribler_config, convert_config_to_tribler71
from Tribler.Test.Core.base_test import TriblerCoreTest


class TestConfigUpgrade70to71(TriblerCoreTest):
    """
    Contains all tests that test the config conversion from 70 to 71.
    """
    from Tribler.Test import Core
    CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(Core.__file__)), "data/config_files/")

    def test_read_test_tribler_conf(self):
        """
        Test upgrading a Tribler configuration from 7.0 to 7.1
        """
        old_config = RawConfigParser()
        old_config.read(os.path.join(self.CONFIG_PATH, "tribler70.conf"))
        new_config = TriblerConfig()
        result_config = add_tribler_config(new_config, old_config)
        self.assertEqual(result_config.get_default_safeseeding_enabled(), True)

    def test_read_test_libtribler_conf(self):
        """
        Test upgrading a libtribler configuration from 7.0 to 7.1
        """
        os.environ['TSTATEDIR'] = self.session_base_dir
        old_config = RawConfigParser()
        old_config.read(os.path.join(self.CONFIG_PATH, "libtribler70.conf"))
        new_config = TriblerConfig()
        result_config = add_libtribler_config(new_config, old_config)
        self.assertEqual(result_config.get_permid_keypair_filename(), "/anon/TriblerDir.gif")
        self.assertEqual(result_config.get_tunnel_community_socks5_listen_ports(), [1, 2, 3, 4, 5, 6])
        self.assertTrue(result_config.get_metadata_store_dir().endswith("/home/.Tribler/testFile"))
        self.assertEqual(result_config.get_anon_proxy_settings(), (2, ("127.0.0.1", [5, 4, 3, 2, 1]), ''))
        self.assertEqual(result_config.get_credit_mining_sources(), ['source1', 'source2'])
        self.assertEqual(result_config.get_log_dir(), '/a/b/c')

    def test_read_test_corr_tribler_conf(self):
        """
        Adding corrupt values should result in the default value.

        Note that this test might fail if there is already an upgraded config stored in the default
        state directory. The code being tested here however shouldn't be ran if that config already exists.
        :return:
        """
        old_config = RawConfigParser()
        old_config.read(os.path.join(self.CONFIG_PATH, "triblercorrupt70.conf"))
        new_config = TriblerConfig()
        result_config = add_tribler_config(new_config, old_config)
        self.assertEqual(result_config.get_default_anonymity_enabled(), True)

    def test_read_test_corr_libtribler_conf(self):
        """
        Adding corrupt values should result in the default value.

        Note that this test might fail if there is already an upgraded config stored in the default
        state directory. The code being tested here however shouldn't be ran if that config already exists.
        :return:
        """
        old_config = RawConfigParser()
        old_config.read(os.path.join(self.CONFIG_PATH, "libtriblercorrupt70.conf"))
        new_config = TriblerConfig(ConfigObj(configspec=CONFIG_SPEC_PATH))

        result_config = add_libtribler_config(new_config, old_config)

        self.assertTrue(result_config.get_permid_keypair_filename().endswith("ec.pem"))
        self.assertTrue(len(result_config.get_tunnel_community_socks5_listen_ports()), 5)
        self.assertTrue(result_config.get_metadata_store_dir().endswith("collected_metadata"))
        self.assertEqual(result_config.get_anon_proxy_settings(), (2, ('127.0.0.1', [-1, -1, -1, -1, -1]), ''))
        self.assertEqual(result_config.get_credit_mining_sources(), new_config.get_credit_mining_sources())

    def test_upgrade_pstate_files(self):
        """
        Test whether the existing pstate files are correctly updated to 7.1.
        """
        os.makedirs(os.path.join(self.state_dir, STATEDIR_DLPSTATE_DIR))

        src_path = os.path.join(self.CONFIG_PATH, "download_pstate_70.state")
        shutil.copyfile(src_path, os.path.join(self.state_dir, STATEDIR_DLPSTATE_DIR, "download.state"))

        old_config = RawConfigParser()
        old_config.read(os.path.join(self.CONFIG_PATH, "tribler70.conf"))
        convert_config_to_tribler71(old_config, state_dir=self.state_dir)

        # Verify whether the section is correctly renamed
        download_config = RawConfigParser()
        download_config.read(os.path.join(self.state_dir, STATEDIR_DLPSTATE_DIR, "download.state"))
        self.assertTrue(download_config.has_section("download_defaults"))
        self.assertFalse(download_config.has_section("downloadconfig"))

        # Do the upgrade again, it should not fail
        convert_config_to_tribler71(old_config, state_dir=self.state_dir)
