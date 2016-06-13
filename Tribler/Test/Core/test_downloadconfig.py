import os

from nose.tools import raises

from Tribler.Core.DownloadConfig import DownloadConfigInterface, DownloadStartupConfig, get_default_dest_dir, \
    get_default_dscfg_filename, DefaultDownloadStartupConfig
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.simpledefs import DLMODE_VOD, UPLOAD, DOWNLOAD
from Tribler.Test.Core.base_test import TriblerCoreTest


class TestConfigParser(TriblerCoreTest):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    CONFIG_FILES_DIR = os.path.abspath(os.path.join(FILE_DIR, u"data/config_files/"))

    def tearDown(self, annotate=True):
        super(TestConfigParser, self).tearDown(annotate=annotate)

        # Make sure we don't leave a DefaultDownloadStartupConfig instance behind
        DefaultDownloadStartupConfig.delInstance()

    def test_downloadconfig(self):
        dlconf = CallbackConfigParser()
        dlconf.add_section('downloadconfig')
        dlconf.set('downloadconfig', 'hops', 5)
        dlcfg = DownloadConfigInterface(dlconf)

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

        dlcfg.set_selected_files("foo.bar")
        self.assertEqual(dlcfg.get_selected_files(), ["foo.bar"])

        dlcfg.set_max_speed(UPLOAD, 1337)
        dlcfg.set_max_speed(DOWNLOAD, 1338)
        self.assertEqual(dlcfg.get_max_speed(UPLOAD), 1337)
        self.assertEqual(dlcfg.get_max_speed(DOWNLOAD), 1338)

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

    @raises(IOError)
    def test_startup_download_load_corrupt(self):
        dlcfg = DownloadStartupConfig()
        dlcfg.load(os.path.join(self.CONFIG_FILES_DIR, "corrupt_download_config.conf"))

    def test_get_default_dest_dir(self):
        self.assertIsInstance(get_default_dest_dir(), unicode)
        self.assertIsInstance(get_default_dscfg_filename(""), str)

    @raises(RuntimeError)
    def test_default_download_startup_config_init(self):
        _ = DefaultDownloadStartupConfig.getInstance()
        DefaultDownloadStartupConfig()

    def test_default_download_startup_config_load(self):
        with open(os.path.join(self.session_base_dir, "dlconfig.conf"), 'wb') as conf_file:
            conf_file.write("[Tribler]\nabc=def")

        ddsc = DefaultDownloadStartupConfig.load(os.path.join(self.session_base_dir, "dlconfig.conf"))
        self.assertEqual(ddsc.dlconfig.get('Tribler', 'abc'), 'def')
