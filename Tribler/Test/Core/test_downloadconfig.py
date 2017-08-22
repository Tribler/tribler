import os

from nose.tools import raises

from Tribler.Core.download.DownloadConfig import DownloadConfig
from Tribler.Core.simpledefs import DLMODE_VOD
from Tribler.Test.Core.base_test import TriblerCoreTest


class TestConfigParser(TriblerCoreTest):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    CONFIG_FILES_DIR = os.path.abspath(os.path.join(FILE_DIR, u"data/config_files/"))

    def tearDown(self, annotate=True):
        super(TestConfigParser, self).tearDown(annotate=annotate)

    def test_downloadconfig(self):
        dlcfg = DownloadConfig()

        self.assertIsInstance(dlcfg.get_destination_dir(), unicode)
        dlcfg.set_destination_dir(self.session_base_dir)
        self.assertEqual(dlcfg.get_destination_dir(), self.session_base_dir)

        dlcfg.set_corrected_filename("foobar")
        self.assertEqual(dlcfg.get_corrected_filename(), "foobar")

        dlcfg.set_mode(1)
        self.assertEqual(dlcfg.get_mode(), 1)

        dlcfg.set_number_hops(4)
        self.assertEqual(dlcfg.get_number_hops(), 4)

        dlcfg.set_safe_seeding_enabled(False)
        self.assertFalse(dlcfg.get_safe_seeding_enabled())

        dlcfg.set_seeding_mode("abcd")
        self.assertEqual(dlcfg.get_seeding_mode(), "abcd")

        dlcfg.set_selected_files("foo.bar")
        self.assertEqual(dlcfg.get_selected_files(), ["foo.bar"])

    @raises(ValueError)
    def test_downloadconfig_set_vod_multiple_files(self):
        dlcfg = DownloadConfig()
        dlcfg.set_mode(DLMODE_VOD)
        dlcfg.set_selected_files(["foo.txt", "bar.txt"])

    def test_downloadconfig_copy(self):
        dlcfg = DownloadConfig()
        dlcfg_copy = dlcfg.copy()

        self.assertEqual(dlcfg_copy.get_number_hops(), 1)

    def test_startup_download_save_load(self):
        dlcfg = DownloadConfig()
        file_path = os.path.join(self.session_base_dir, "downloadconfig.conf")
        dlcfg.save(file_path)

    def test_get_default_destination_dir(self):
        self.assertIsInstance(DownloadConfig.get_default_destination_dir(), unicode)
