from io import StringIO
from pathlib import Path
from unittest.mock import Mock, call, patch

from configobj import ConfigObj
from ipv8.test.base import TestBase
from validate import Validator

from tribler.core.libtorrent.download_manager.download_config import SPEC_CONTENT, DownloadConfig


class TestDownloadConfig(TestBase):
    """
    Tests for the DownloadConfig class.
    """

    def setUp(self) -> None:
        """
        Create a new config with a memory spec.
        """
        defaults = ConfigObj(StringIO(SPEC_CONTENT))
        conf = ConfigObj()
        conf.configspec = defaults
        conf.validate(Validator())

        self.download_config = DownloadConfig(conf)
        self.download_config.set_dest_dir(Path(""))

    def test_set_dest_dir(self) -> None:
        """
        Test if the destination directory is correctly.
        """
        self.download_config.set_dest_dir(Path("bla"))

        self.assertEqual(Path("bla"), self.download_config.get_dest_dir())

    def test_set_hops(self) -> None:
        """
        Test if the hops are correctly.
        """
        self.download_config.set_hops(4)

        self.assertEqual(4, self.download_config.get_hops())

    def test_set_safe_seeding(self) -> None:
        """
        Test if safe seeding setting is set correctly.
        """
        self.download_config.set_safe_seeding(False)

        self.assertFalse(self.download_config.get_safe_seeding())

    def test_set_selected_files(self) -> None:
        """
        Test if the selected files are set correctly.
        """
        self.download_config.set_selected_files([1])

        self.assertEqual([1], self.download_config.get_selected_files())

    def test_set_bootstrap_download(self) -> None:
        """
        Test if the bootstrap download flag is set correctly.
        """
        self.download_config.set_bootstrap_download(True)

        self.assertTrue(self.download_config.get_bootstrap_download())

    def test_set_user_stopped(self) -> None:
        """
        Test if the user stopped flag is set correctly.
        """
        self.download_config.set_user_stopped(False)

        self.assertFalse(self.download_config.get_user_stopped())

    def test_downloadconfig_copy(self) -> None:
        """
        Test if the download config can be copied.
        """
        dlcfg_copy = self.download_config.copy()

        self.assertEqual(0, dlcfg_copy.get_hops())
        self.assertEqual(self.download_config.get_dest_dir(), dlcfg_copy.get_dest_dir())

    def test_download_save_load(self) -> None:
        """
        Test if configs can be written.
        """
        fake_write = Mock()
        with patch.object(self.download_config.config, "write", fake_write):
            self.download_config.write(Path("fake_output"))

        self.assertEqual(call(), fake_write.call_args)
