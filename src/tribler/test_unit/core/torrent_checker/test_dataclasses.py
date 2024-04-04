import sys

from ipv8.test.base import TestBase

from tribler.core.torrent_checker.dataclasses import HealthInfo


class TestHealthInfo(TestBase):
    """
    Tests for the HealthInfo class.
    """

    def test_is_valid_no_seeders(self) -> None:
        """
        Test if health info with negative seeders is invalid.
        """
        health = HealthInfo(b"\x00" * 20, -1, 200)

        self.assertFalse(health.is_valid())

    def test_is_valid_no_leechers(self) -> None:
        """
        Test if health info with negative leechers is invalid.
        """
        health = HealthInfo(b"\x00" * 20, 200, -1)

        self.assertFalse(health.is_valid())

    def test_is_valid_old(self) -> None:
        """
        Test if old info is invalid.
        """
        health = HealthInfo(b"\x00" * 20, 200, 200, last_check=sys.maxsize)

        self.assertFalse(health.is_valid())

    def test_is_valid_healthy(self) -> None:
        """
        Test if health info with recent healthy seeders and leechers is valid.
        """
        health = HealthInfo(b"\x00" * 20, 200, 200)

        self.assertTrue(health.is_valid())

    def test_old_old(self) -> None:
        """
        Test if health info that is old is flagged as old.
        """
        health = HealthInfo(b"\x00" * 20, 200, 200, last_check=0)

        self.assertTrue(health.old())

    def test_old_new(self) -> None:
        """
        Test if health info that is new is not flagged as old.
        """
        health = HealthInfo(b"\x00" * 20, 200, 200)

        self.assertFalse(health.old())

    def test_older_than(self) -> None:
        """
        Test if old health info is older than new health info.
        """
        health = HealthInfo(b"\x00" * 20, 200, 200, last_check=0)

        self.assertTrue(health.older_than(HealthInfo(b"\x00" * 20, 200, 200)))

    def test_much_older_than(self) -> None:
        """
        Test if very old health info is older than new health info.
        """
        health = HealthInfo(b"\x00" * 20, 200, 200, last_check=0)

        self.assertTrue(health.much_older_than(HealthInfo(b"\x00" * 20, 200, 200)))

    def test_should_replace_unrelated(self) -> None:
        """
        Test if trying to replace unrelated health info raises an error.
        """
        health = HealthInfo(b"\x00" * 20, 200, 200)

        with self.assertRaises(ValueError):
            health.should_replace(HealthInfo(b"\x01" * 20, 200, 200))

    def test_should_replace_invalid(self) -> None:
        """
        Test if invalid health info should not replace anything.
        """
        health = HealthInfo(b"\x00" * 20, -1, 200)

        self.assertFalse(health.should_replace(HealthInfo(b"\x00" * 20, 200, 200)))

    def test_should_replace_own_self_checked(self) -> None:
        """
        Test if self-checked health info should replace equal self-checked health info.
        """
        health = HealthInfo(b"\x00" * 20, 200, 200, self_checked=True)

        self.assertFalse(health.should_replace(HealthInfo(b"\x00" * 20, 200, 200, self_checked=True)))

    def test_should_replace_not_self_checked_old(self) -> None:
        """
        Test if self-checked health info should replace old non-self-checked health info.
        """
        health = HealthInfo(b"\x00" * 20, 200, 200, self_checked=True)

        self.assertTrue(health.should_replace(HealthInfo(b"\x00" * 20, 200, 200, last_check=0)))

    def test_should_replace_not_self_checked_lower(self) -> None:
        """
        Test if self-checked health info should replace non-self-checked health info with less seeders/leechers.
        """
        health = HealthInfo(b"\x00" * 20, 200, 200, self_checked=True)

        self.assertTrue(health.should_replace(HealthInfo(b"\x00" * 20, 100, 200)))

    def test_should_replace_old(self) -> None:
        """
        Test if newer health info should replace older health info.
        """
        health = HealthInfo(b"\x00" * 20, 200, 200)

        self.assertTrue(health.should_replace(HealthInfo(b"\x00" * 20, 200, 200, last_check=0)))

    def test_should_replace_self_checked(self) -> None:
        """
        Test if health info should replace self-checked health info.
        """
        health = HealthInfo(b"\x00" * 20, 200, 200)

        self.assertFalse(health.should_replace(HealthInfo(b"\x00" * 20, 200, 200, self_checked=True)))

    def test_should_replace_equivalent_lower(self) -> None:
        """
        Test if health info should replace other health info with less seeders/leechers.
        """
        health = HealthInfo(b"\x00" * 20, 200, 200)

        self.assertTrue(health.should_replace(HealthInfo(b"\x00" * 20, 100, 200)))
