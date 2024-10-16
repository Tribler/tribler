from __future__ import annotations

from ipv8.test.base import TestBase

from tribler.core.recommender.manager import Manager


class TestManager(TestBase):
    """
    Tests for the database manager.
    """

    def setUp(self) -> None:
        """
        Create a new memory-based manager.
        """
        self.manager = Manager(":memory:")

    def test_add_query(self) -> None:
        """
        Test if queries can be added and retrieved.
        """
        self.manager.add_query('{"key":"value"}')

        result = self.manager.get_query(1)
        size = self.manager.get_total_queries()

        self.assertEqual(1, size)
        self.assertEqual(1, result.rowid)
        self.assertEqual(1, result.version)
        self.assertEqual('{"key":"value"}', result.json)

    def test_get_total_queries(self) -> None:
        """
        Test if multiple queries are counted correctly.
        """
        self.manager.add_query('{"key":"value"}')
        self.manager.add_query('{"key":"value"}')
        self.manager.add_query('{"key2":"value2"}')

        size = self.manager.get_total_queries()

        self.assertEqual(3, size)
