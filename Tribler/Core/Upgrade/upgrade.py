import logging
import os
import shutil
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.CacheDB.db_versions import LATEST_DB_VERSION, LOWEST_SUPPORTED_DB_VERSION
from Tribler.Core.Upgrade.config_converter import convert_config_to_tribler71
from Tribler.Core.Upgrade.db_upgrader import DBUpgrader
from Tribler.Core.Upgrade.pickle_converter import PickleConverter
from Tribler.Core.Upgrade.torrent_upgrade65 import TorrentMigrator65
from Tribler.Core.simpledefs import NTFY_UPGRADER, NTFY_FINISHED, NTFY_STARTED, NTFY_UPGRADER_TICK
from Tribler.dispersy.util import call_on_reactor_thread, blocking_call_on_reactor_thread


# Database versions:
#   *earlier versions are no longer supported
#   17   is used by Tribler 5.9.x - 6.0
#   18   is used by Tribler 6.1.x - 6.2.0
#   22   is used by Tribler 6.3.x
#   23   is used by Tribler 6.4


class TriblerUpgrader(object):

    def __init__(self, session, db):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session
        self.db = db

        self.notified = False
        self.is_done = False
        self.failed = True

        self.current_status = u"Initializing"

    def run(self):
        """
        Run the upgrader if it is enabled in the config.

        Note that by default, upgrading is enabled in the config. It is then disabled
        after upgrading to Tribler 7.
        """
        self.current_status = u"Checking Tribler version..."
        if self.session.config.get_upgrader_enabled():
            failed, has_to_upgrade = self.check_should_upgrade_database()
            if has_to_upgrade and not failed:
                self.notify_starting()
                self.upgrade_database_to_current_version()

                # Convert old (pre 6.3 Tribler) pickle files to the newer .state format
                pickle_converter = PickleConverter(self.session)
                pickle_converter.convert()

            if self.failed:
                self.notify_starting()
                self.stash_database()

            self.upgrade_to_tribler7()

    def update_status(self, status_text):
        self.session.notifier.notify(NTFY_UPGRADER_TICK, NTFY_STARTED, None, status_text)
        self.current_status = status_text

    def upgrade_to_tribler7(self):
        """
        This method performs actions necessary to upgrade to Tribler 7.
        """
        self.session.config = convert_config_to_tribler71()
        self.session.config.set_trustchain_enabled(True)
        self.session.config.set_upgrader_enabled(False)
        self.session.config.write()

    def notify_starting(self):
        """
        Broadcast a notification (event) that the upgrader is starting doing work
        after a check has established work on the db is required.
        Will only fire once.
        """
        if not self.notified:
            self.notified = True
            self.session.notifier.notify(NTFY_UPGRADER, NTFY_STARTED, None)

    def notify_done(self):
        """
        Broadcast a notification (event) that the upgrader is done.
        """
        self.session.notifier.notify(NTFY_UPGRADER, NTFY_FINISHED, None)

    @blocking_call_on_reactor_thread
    def check_should_upgrade_database(self):
        self.failed = True
        should_upgrade = False
        if self.db.version > LATEST_DB_VERSION:
            msg = u"The on-disk tribler database is newer than your tribler version. Your database will be backed up."
            self.current_status = msg
            self._logger.info(msg)
        elif self.db.version < LOWEST_SUPPORTED_DB_VERSION:
            msg = u"Database is too old %s < %s" % (self.db.version, LOWEST_SUPPORTED_DB_VERSION)
            self.current_status = msg
        elif self.db.version == LATEST_DB_VERSION:
            self._logger.info(u"tribler is in the latest version, no need to upgrade")
            self.failed = False
            self.is_done = True
            self.notify_done()
        else:
            should_upgrade = True
            self.failed = False

        return (self.failed, should_upgrade)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def upgrade_database_to_current_version(self):
        """ Checks the database version and upgrade if it is not the latest version.
        """
        try:
            from Tribler.Core.leveldbstore import LevelDbStore
            torrent_store = LevelDbStore(self.session.config.get_torrent_store_dir())
            torrent_migrator = TorrentMigrator65(
                self.session.config.get_torrent_collecting_dir(), self.session.config.get_state_dir(),
                torrent_store=torrent_store, status_update_func=self.update_status)
            yield torrent_migrator.start_migrate()

            db_migrator = DBUpgrader(
                self.session, self.db, torrent_store=torrent_store, status_update_func=self.update_status)
            yield db_migrator.start_migrate()

            # Import all the torrent files not in the database, we do this in
            # case we have some unhandled torrent files left due to
            # bugs/crashes, etc.
            self.update_status("Recovering unregistered torrents...")
            yield db_migrator.reimport_torrents()

            yield torrent_store.close()
            del torrent_store

            self.failed = False
            self.is_done = True
        except Exception as e:
            self._logger.exception(u"failed to upgrade: %s", e)

    @call_on_reactor_thread
    def stash_database(self):
        self.db.close()
        old_dir = os.path.dirname(self.db.sqlite_db_path)
        new_dir = u'%s_backup_%d' % (old_dir, LATEST_DB_VERSION)
        shutil.move(old_dir, new_dir)
        os.makedirs(old_dir)
        self.db.initialize()
        self.is_done = True
        self.notify_done()
