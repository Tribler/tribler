from pathlib import Path
from unittest.mock import Mock, mock_open, patch

from ipv8.test.base import TestBase

from tribler.core.libtorrent.download_manager.download_config import DownloadConfig, DownloadPriority


class TestDownloadConfig(TestBase):
    """
    Tests for the DownloadConfig class.
    """

    def setUp(self) -> None:
        """
        Create a new config with a memory spec.
        """
        self.download_config = DownloadConfig(DownloadConfig.get_parser())
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
        # Precondition: torrent must be properly initialized with files
        self.download_config.set_file_priorities(
            [DownloadPriority.NO_DOWNLOAD] * 10)

        self.download_config.set_selected_files([1, 7])

        self.assertEqual([1, 7], self.download_config.get_selected_files())
        self.assertEqual([0, 4, 0, 0, 0, 0, 0, 4, 0, 0], self.download_config.get_file_priorities())

    def test_set_selected_files_pre_init(self) -> None:
        """
        Test if selected files can be temporarily stored before priorities are initialized
        (e.g. magnet link args).
        """
        self.download_config.set_selected_files([1, 7])

        self.assertEqual([1, 7], self.download_config.get_selected_files())
        self.assertIsNone(self.download_config.get_file_priorities())

    def test_set_selected_files_none_pre_init(self) -> None:
        """
        Test if setting None before initialization successfully clears any pre-selection.
        """
        self.download_config.set_selected_files([1, 7])
        self.download_config.set_selected_files(None)

        self.assertIsNone(self.download_config.get_selected_files())
        self.assertIsNone(self.download_config.get_file_priorities())

    def test_set_selected_files_no_overwrite_priority(self) -> None:
        """
        Test that files with a pre-set priority are not overridden.
        """
        # Precondition: torrent must be properly initialized with files
        self.download_config.set_file_priorities(
            [DownloadPriority.HIGH, DownloadPriority.LOW, DownloadPriority.MEDIUM, DownloadPriority.NO_DOWNLOAD])

        self.download_config.set_selected_files([0, 1, 2, 3])

        self.assertEqual([0, 1, 2, 3], self.download_config.get_selected_files())
        self.assertEqual([7, 1, 4, 4], self.download_config.get_file_priorities())

    def test_set_selected_files_clear_priority_on_remove(self) -> None:
        """
        Test that files that are deselected are set to NO_DOWNLOAD.
        """
        # Precondition: torrent must be properly initialized with files
        self.download_config.set_file_priorities(
            [DownloadPriority.HIGH, DownloadPriority.LOW, DownloadPriority.MEDIUM, DownloadPriority.NO_DOWNLOAD])

        self.download_config.set_selected_files([0, 2])

        self.assertEqual([0, 2], self.download_config.get_selected_files())
        self.assertEqual([7, 0, 4, 0], self.download_config.get_file_priorities())

    def test_get_file_priorities_empty(self) -> None:
        """
        Test if get_file_priorities returns None when not initialized.
        """
        self.assertIsNone(self.download_config.get_file_priorities())

    def test_set_file_priorities(self) -> None:
        """
        Test if file priorities are set correctly.
        """
        self.download_config.set_file_priorities([DownloadPriority.MEDIUM, DownloadPriority.HIGH, DownloadPriority.LOW])

        self.assertEqual([4, 7, 1], self.download_config.get_file_priorities())

    def test_set_file_priority(self) -> None:
        """
        Test if a single file priority is updated correctly.
        """
        self.download_config.set_file_priorities(
            [DownloadPriority.MEDIUM, DownloadPriority.MEDIUM, DownloadPriority.MEDIUM])

        self.download_config.set_file_priority(1, DownloadPriority.HIGH)

        self.assertEqual([4, 7, 4], self.download_config.get_file_priorities())
        self.assertEqual(DownloadPriority.HIGH, self.download_config.get_file_priority(1))

    def test_clear_file_priorities(self) -> None:
        """
        Test if file priorities are properly cleared (all set to NO_DOWNLOAD).
        """
        self.download_config.set_file_priorities([DownloadPriority.MEDIUM, DownloadPriority.HIGH, DownloadPriority.LOW])

        self.download_config.clear_file_priorities()

        self.assertEqual([0, 0, 0], self.download_config.get_file_priorities())

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

        with patch("builtins.open", mock_open(mock=fake_write)):
            self.download_config.write("fake_output")

        name, mode = fake_write.call_args.args
        self.assertEqual("fake_output", name)
        self.assertEqual("w", mode)

    def test_set_seeding_ratio(self) -> None:
        """
        Test if the individual seeding ratio is set correctly.
        """
        self.download_config.set_seeding_ratio(12.34)

        self.assertEqual(12.34, self.download_config.get_seeding_ratio())

    def test_clear_seeding_ratio(self) -> None:
        """
        Test if the individual seeding ratio can be set to follow the default again.
        """
        self.download_config.set_seeding_ratio(12.34)
        self.download_config.set_seeding_ratio(None)

        self.assertIsNone(self.download_config.get_seeding_ratio())
