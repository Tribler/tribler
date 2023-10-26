import pytest
from pony.orm import db_session

from tribler.core.components.database.db.tribler_database import TriblerDatabase
from tribler.core.components.ipv8.adapters_tests import TriblerTestBase


# pylint: disable=protected-access

class TestTriblerDatabase(TriblerTestBase):
    def setUp(self):
        super().setUp()
        self.db = TriblerDatabase()

    async def tearDown(self):
        if self._outcome.errors:
            self.dump_db()

        await super().tearDown()

    @db_session
    def dump_db(self):
        print('\nPeer:')
        self.db.instance.Peer.select().show()
        print('\nResource:')
        self.db.instance.Resource.select().show()
        print('\nStatement')
        self.db.instance.Statement.select().show()
        print('\nStatementOp')
        self.db.instance.StatementOp.select().show()
        print('\nMisc')
        self.db.instance.Misc.select().show()
        print('\nTorrentHealth')
        self.db.instance.TorrentHealth.select().show()
        print('\nTracker')
        self.db.instance.Tracker.select().show()

    @db_session
    def test_set_misc(self):
        """Test that set_misc works as expected"""
        self.db.set_misc(key='string', value='value')
        self.db.set_misc(key='integer', value=1)
        assert self.db.get_misc(key='string') == 'value'
        assert self.db.get_misc(key='integer') == '1'

    @db_session
    def test_non_existent_misc(self):
        """Test that get_misc returns proper values"""
        # None if the key does not exist
        assert not self.db.get_misc(key='non existent')

        # A value if the key does exist
        assert self.db.get_misc(key='non existent', default=42) == 42

    @db_session
    def test_default_version(self):
        """ Test that the default version is equal to `CURRENT_VERSION`"""
        assert self.db.version == TriblerDatabase.CURRENT_VERSION

    @db_session
    def test_version_getter_and_setter(self):
        """ Test that the version getter and setter work as expected"""
        self.db.version = 42
        assert self.db.version == 42

    @db_session
    def test_version_getter_unsupported_type(self):
        """ Test that the version getter raises a TypeError if the type is not supported"""
        with pytest.raises(TypeError):
            self.db.version = 'string'
