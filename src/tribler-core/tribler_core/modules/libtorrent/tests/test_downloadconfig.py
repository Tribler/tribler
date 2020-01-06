from pathlib import Path

from configobj import ConfigObjError

from nose.tools import raises

from tribler_core.modules.libtorrent.download_config import DownloadConfig, get_default_dest_dir
from tribler_core.tests.tools.base_test import TriblerCoreTest
from tribler_core.tests.tools.common import TESTS_DATA_DIR


class TestConfigParser(TriblerCoreTest):

    CONFIG_FILES_DIR = TESTS_DATA_DIR / "config_files"

    def test_downloadconfig(self):
        dlcfg = DownloadConfig()

        self.assertIsInstance(dlcfg.get_dest_dir(), Path)
        dlcfg.set_dest_dir(self.session_base_dir)
        self.assertEqual(dlcfg.get_dest_dir(), self.session_base_dir)

        dlcfg.set_hops(4)
        self.assertEqual(dlcfg.get_hops(), 4)

        dlcfg.set_safe_seeding(False)
        self.assertFalse(dlcfg.get_safe_seeding())

        dlcfg.set_selected_file_indexes([1])
        self.assertEqual(dlcfg.get_selected_file_indexes(), [1])

        dlcfg.set_channel_download(True)
        self.assertTrue(dlcfg.get_channel_download())

        dlcfg.set_add_to_channel(True)
        self.assertTrue(dlcfg.get_add_to_channel())

        dlcfg.set_bootstrap_download(True)
        self.assertTrue(dlcfg.get_bootstrap_download())

    def test_downloadconfig_copy(self):
        dlcfg = DownloadConfig()
        dlcfg_copy = dlcfg.copy()

        self.assertEqual(dlcfg_copy.get_hops(), 0)
        self.assertEqual(dlcfg_copy.state_dir, dlcfg.state_dir)

    def test_download_save_load(self):
        dlcfg = DownloadConfig()
        file_path = self.session_base_dir / "downloadconfig.conf"
        dlcfg.write(file_path)
        dlcfg.load(file_path)

    @raises(ConfigObjError)
    def test_download_load_corrupt(self):
        dlcfg = DownloadConfig()
        dlcfg.load(self.CONFIG_FILES_DIR / "corrupt_download_config.conf")

    def test_get_default_dest_dir(self):
        self.assertIsInstance(get_default_dest_dir(), Path)

    def test_default_download_config_load(self):
        with open(self.session_base_dir / "dlconfig.conf", 'wb') as conf_file:
            conf_file.write(b"[Tribler]\nabc=def")

        dcfg = DownloadConfig.load(self.session_base_dir / "dlconfig.conf")
        self.assertEqual(dcfg.config['Tribler']['abc'], 'def')

    def test_user_stopped(self):
        dlcfg = DownloadConfig()
        dlcfg.set_user_stopped(False)
        self.assertFalse(dlcfg.get_user_stopped())

        dlcfg.set_user_stopped(True)
        self.assertTrue(dlcfg.get_user_stopped())
