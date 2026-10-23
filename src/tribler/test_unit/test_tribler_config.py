from unittest.mock import Mock

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

    def test_set_on_old(self) -> None:
        """
        Test if we can set a key on an old dict that is missing it.
        """
        config = TriblerConfigManager()
        config.configuration = {k: v for k, v in config.configuration.items() if k != "rss"}

        config.set("rss/enabled", True)

        self.assertTrue(config.get("rss/enabled"))

    def test_set_ui_missing(self) -> None:
        """
        Test if we can set a key in a missing ui entry.
        """
        config = TriblerConfigManager()

        config.set("ui/a/b/c", 42)

        self.assertEqual(42, config.configuration["ui"]["a"]["b"]["c"])  # Passed by copy, not ``get()``!

    def test_trigger_exact(self) -> None:
        """
        Check if a changed setting leads to a callback.
        """
        modified = Mock()
        config = TriblerConfigManager()
        config.set("ui/a/b/c", 7)
        config.add_trigger("ui/a/b/c", modified)

        config.set("ui/a/b/c", 42)

        self.assertEqual("ui/a/b/c", modified.call_args.args[0])
        self.assertEqual(7, modified.call_args.args[1])
        self.assertEqual(42, modified.call_args.args[2])

    def test_trigger_parent(self) -> None:
        """
        Check if a changed setting in a child path leads to a callback.
        """
        modified = Mock()
        config = TriblerConfigManager()
        config.set("ui/a/b/c", 7)
        config.add_trigger("ui/a/b", modified)

        config.set("ui/a/b/c", 42)

        self.assertEqual("ui/a/b/c", modified.call_args.args[0])
        self.assertEqual(7, modified.call_args.args[1])
        self.assertEqual(42, modified.call_args.args[2])

    def test_trigger_deep(self) -> None:
        """
        Check if a changed setting in a subchild path leads to a callback.
        """
        modified = Mock()
        config = TriblerConfigManager()
        config.set("ui/a/b/c", 7)
        config.add_trigger("ui", modified)

        config.set("ui/a/b/c", 42)

        self.assertEqual("ui/a/b/c", modified.call_args.args[0])
        self.assertEqual(7, modified.call_args.args[1])
        self.assertEqual(42, modified.call_args.args[2])

    def test_trigger_changed(self) -> None:
        """
        Check if setting an unchanged setting leads to no callback.
        """
        modified = Mock()
        config = TriblerConfigManager()
        config.set("ui/a/b/c", 7)
        config.add_trigger("ui/a/b/c", modified)

        config.set("ui/a/b/c", 7)

        self.assertIsNone(modified.call_args)
