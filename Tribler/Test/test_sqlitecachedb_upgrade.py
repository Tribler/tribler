import sys

from Tribler.Core.Session import Session
from Tribler.Test.bak_tribler_sdb import init_bak_tribler_sdb
from Tribler.Test.test_as_server import AbstractServer
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestSqliteCacheDB(AbstractServer):

    @blocking_call_on_reactor_thread
    def setUp(self):
        super(TestSqliteCacheDB, self).setUp()

    @blocking_call_on_reactor_thread
    def tearDown(self):
        if Session.has_instance():  # Upgrading will create a session instance
            Session.del_instance()

        AbstractServer.tearDown(self)

    def test_perform_upgrade(self):
        dbpath = init_bak_tribler_sdb('bak_old_tribler.sdb', destination_path=self.getStateDir(), overwrite=True)

        # TODO(emilon): Replace this with the database decorator when the database stuff gets its own thread again
        @blocking_call_on_reactor_thread
        def do_db():
            self.sqlitedb = SQLiteCacheDB.getInstance()
            self.sqlitedb.initDB(dbpath)
        do_db()
        self.sqlitedb.waitForUpdateComplete()
