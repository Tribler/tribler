from ipv8.test.base import TestBase
from pony.orm import db_session

from tribler.core.database.tribler_database import TriblerDatabase


class TestTriblerDatabase(TestBase):
    """
    Tests for the TriblerDatabase class.
    """

    def setUp(self) -> None:
        """
        Create a database instance.
        """
        super().setUp()
        self.db = TriblerDatabase(":memory:")

    @db_session
    def test_set_misc(self) -> None:
        """
        Test if set_misc works as expected.
        """
        self.db.set_misc(key='string', value='value')
        self.db.set_misc(key='integer', value="1")

        self.assertEqual("value", self.db.get_misc(key='string'))
        self.assertEqual("1", self.db.get_misc(key='integer'))

    @db_session
    def test_non_existent_misc(self) -> None:
        """
        Test if get_misc returns proper values.
        """
        self.assertIsNone(self.db.get_misc(key="non existent"))
        self.assertEqual("42", self.db.get_misc(key="non existent", default="42"))

    @db_session
    def test_default_version(self) -> None:
        """
        Test if the default version is equal to ``CURRENT_VERSION``.
        """
        self.assertEqual(TriblerDatabase.CURRENT_VERSION, self.db.version)

    @db_session
    def test_version_getter_and_setter(self) -> None:
        """
        Test if the version getter and setter work as expected.
        """
        self.db.version = 42

        self.assertEqual(42, self.db.version)

    @db_session
    def test_version_getter_unsupported_type(self) -> None:
        """
        Test if the version getter raises a TypeError if the type is not supported.
        """
        with self.assertRaises(TypeError):
            self.db.version = 'string'
