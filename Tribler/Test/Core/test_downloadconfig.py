import os
from ConfigParser import MissingSectionHeaderError
from nose.tools import raises

from Tribler.Core.DownloadConfig import DownloadConfigInterface, DownloadStartupConfig, get_default_dest_dir, \
    DefaultDownloadStartupConfig
from Tribler.Core.simpledefs import DLMODE_VOD
from Tribler.Test.Core.base_test import TriblerCoreTest


class TestConfigParser(TriblerCoreTest):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    CONFIG_FILES_DIR = os.path.abspath(os.path.join(FILE_DIR, u"data/config_files/"))

    def tearDown(self):
        super(TestConfigParser, self).tearDown()

        # Make sure we don't leave a DefaultDownloadStartupConfig instance behind
        DefaultDownloadStartupConfig.delInstance()

    def test_downloadconfig(self):
        dlcfg = DownloadConfigInterface()

        self.assertIsInstance(dlcfg.get_dest_dir(), unicode)
        dlcfg.set_dest_dir(self.session_base_dir)
        self.assertEqual(dlcfg.get_dest_dir(), self.session_base_dir)

        dlcfg.set_corrected_filename("foobar")
        self.assertEqual(dlcfg.get_corrected_filename(), "foobar")

        dlcfg.set_mode(1)
        self.assertEqual(dlcfg.get_mode(), 1)

        dlcfg.set_hops(4)
        self.assertEqual(dlcfg.get_hops(), 4)

        dlcfg.set_safe_seeding(False)
        self.assertFalse(dlcfg.get_safe_seeding())

        dlcfg.set_seeding_mode("abcd")
        self.assertEqual(dlcfg.get_seeding_mode(), "abcd")

        dlcfg.set_selected_files("foo.bar")
        self.assertEqual(dlcfg.get_selected_files(), ["foo.bar"])

    @raises(ValueError)
    def test_downloadconfig_set_vod_multiple_files(self):
        dlcfg = DownloadConfigInterface()
        dlcfg.set_mode(DLMODE_VOD)
        dlcfg.set_selected_files(["foo.txt", "bar.txt"])

    def test_downloadconfig_copy(self):
        dlcfg = DownloadConfigInterface()
        dlcfg_copy = dlcfg.copy()

        self.assertEqual(dlcfg_copy.get_hops(), 0)

    def test_downloadstartupconfig_copy(self):
        dlcfg = DownloadStartupConfig()
        dlcfg_copy = dlcfg.copy()

        self.assertEqual(dlcfg_copy.get_hops(), 0)

    def test_startup_download_save_load(self):
        dlcfg = DownloadStartupConfig()
        file_path = os.path.join(self.session_base_dir, "downloadconfig.conf")
        dlcfg.save(file_path)
        dlcfg.load(file_path)

    @raises(MissingSectionHeaderError)
    def test_startup_download_load_corrupt(self):
        dlcfg = DownloadStartupConfig()
        dlcfg.load(os.path.join(self.CONFIG_FILES_DIR, "corrupt_download_config.conf"))

    def test_get_default_dest_dir(self):
        self.assertIsInstance(get_default_dest_dir(), unicode)


    @raises(RuntimeError)
    def test_default_download_startup_config_init(self):
        _ = DefaultDownloadStartupConfig.getInstance()
        DefaultDownloadStartupConfig()

    def test_default_download_startup_config_load(self):
        with open(os.path.join(self.session_base_dir, "dlconfig.conf"), 'wb') as conf_file:
            conf_file.write("[Tribler]\nabc=def")

        ddsc = DefaultDownloadStartupConfig.load(os.path.join(self.session_base_dir, "dlconfig.conf"))
        self.assertEqual(ddsc.dlconfig.get('Tribler', 'abc'), 'def')

    def test_user_stopped(self):
        dlcfg = DownloadConfigInterface()
        dlcfg.set_user_stopped(False)
        self.assertFalse(dlcfg.get_user_stopped())

        dlcfg.set_user_stopped(True)
        self.assertTrue(dlcfg.get_user_stopped())
