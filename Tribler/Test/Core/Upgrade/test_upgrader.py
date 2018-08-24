import os
from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.Core.CacheDB.db_versions import LATEST_DB_VERSION, LOWEST_SUPPORTED_DB_VERSION
from Tribler.Core.Upgrade.upgrade import TriblerUpgrader
from Tribler.Core.simpledefs import NTFY_UPGRADER_TICK, NTFY_STARTED
from Tribler.Test.Core.Upgrade.upgrade_base import AbstractUpgrader
from Tribler.Test.tools import trial_timeout


class TestUpgrader(AbstractUpgrader):

    @inlineCallbacks
    def setUp(self):
        yield super(TestUpgrader, self).setUp()
        self.copy_and_initialize_upgrade_database('tribler_v17.sdb')
        self.upgrader = TriblerUpgrader(self.session, self.sqlitedb)

    def test_stash_database(self):
        self.upgrader.stash_database()
        old_dir = os.path.dirname(self.sqlitedb.sqlite_db_path)
        self.assertTrue(os.path.exists(u'%s_backup_%d' % (old_dir, LATEST_DB_VERSION)))
        self.assertIsNotNone(self.sqlitedb._connection)
        self.assertTrue(self.upgrader.is_done)

    def test_should_upgrade(self):
        self.sqlitedb._version = LATEST_DB_VERSION + 1
        self.assertTrue(self.upgrader.check_should_upgrade_database()[0])
        self.assertFalse(self.upgrader.check_should_upgrade_database()[1])

        self.sqlitedb._version = LOWEST_SUPPORTED_DB_VERSION - 1
        self.assertTrue(self.upgrader.check_should_upgrade_database()[0])
        self.assertFalse(self.upgrader.check_should_upgrade_database()[1])

        self.sqlitedb._version = LATEST_DB_VERSION
        self.assertFalse(self.upgrader.check_should_upgrade_database()[0])
        self.assertFalse(self.upgrader.check_should_upgrade_database()[1])

        self.sqlitedb._version = LATEST_DB_VERSION - 1
        self.assertFalse(self.upgrader.check_should_upgrade_database()[0])
        self.assertTrue(self.upgrader.check_should_upgrade_database()[1])

    def test_upgrade_with_upgrader_enabled(self):
        self.upgrader.run()

        self.assertTrue(self.upgrader.is_done)
        self.assertFalse(self.upgrader.failed)

    def test_run(self):
        """
        Test the run method of the upgrader
        """
        def check_should_upgrade():
            self.upgrader.failed = True
            return True, False
        self.upgrader.session.config.get_upgrader_enabled = lambda: True
        self.upgrader.check_should_upgrade_database = check_should_upgrade

        self.upgrader.run()
        self.assertTrue(self.upgrader.notified)

    @trial_timeout(10)
    def test_update_status_text(self):
        test_deferred = Deferred()

        def on_upgrade_tick(subject, changetype, objectID, status_text):
            self.assertEqual(status_text, "12345")
            test_deferred.callback(None)

        self.session.notifier.add_observer(on_upgrade_tick, NTFY_UPGRADER_TICK, [NTFY_STARTED])
        self.upgrader.update_status("12345")
        return test_deferred
