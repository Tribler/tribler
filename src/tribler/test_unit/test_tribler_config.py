from ipv8.test.base import TestBase

from tribler.tribler_config import DEFAULT_CONFIG, TriblerConfigManager


class TestTriblerConfigManager(TestBase):
    """
    Tests for the TriblerConfigManager.
    """

    def test_get_default_fallback(self) -> None:
        """
        Test if ``get`` falls back to the default config values.
        """
        config = TriblerConfigManager()

        self.assertEqual(60, config.get("libtorrent/download_defaults/seeding_time"))

    def test_get_default_fallback_half_tree(self) -> None:
        """
        Test if ``get`` falls back to the default config values, when part of the path exists.
        """
        config = TriblerConfigManager()
        config.set("libtorrent/port", 42)

        self.assertEqual(60, config.get("libtorrent/download_defaults/seeding_time"))

    def test_get_directory(self) -> None:
        """
        Test if ``get`` of a directory returns the entire dict.
        """
        config = TriblerConfigManager()

        self.assertEqual(DEFAULT_CONFIG["api"], config.get("api"))

    def test_get_set_explicit(self) -> None:
        """
        Test if ``get`` can retrieve explicitly set config values.
        """
        config = TriblerConfigManager()
        config.set("libtorrent/download_defaults/seeding_time", 42)

        self.assertEqual(42, config.get("libtorrent/download_defaults/seeding_time"))
