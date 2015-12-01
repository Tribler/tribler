import logging
import os
import shutil
import thread
from twisted.internet.defer import inlineCallbacks
from Tribler.Core.CacheDB.db_versions import LATEST_DB_VERSION, LOWEST_SUPPORTED_DB_VERSION
from Tribler.Core.Upgrade.db_upgrader import DBUpgrader, VersionNoLongerSupportedError
from Tribler.Core.Upgrade.torrent_upgrade65 import TorrentMigrator65
from Tribler.dispersy.util import call_on_reactor_thread


# Database versions:
#   *earlier versions are no longer supported
#   17   is used by Tribler 5.9.x - 6.0
#   18   is used by Tribler 6.1.x - 6.2.0
#   22   is used by Tribler 6.3.x
#   23   is used by Tribler 6.4


class TriblerUpgrader(object):

    _singleton = None
    _singleton_lock = thread.allocate_lock()

    @classmethod
    def get_singleton(cls, *args, **kargs):
        if cls._singleton is None:
            cls._singleton_lock.acquire()
            try:
                if cls._singleton is None:
                    cls._singleton = cls(*args, **kargs)
            finally:
                cls._singleton_lock.release()
        return cls._singleton

    def __init__(self, session):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session
        self.db = session.sqlite_db

        self.current_status = u"Checking Tribler version..."
        self.is_done = False
        self.failed = True

    def update_status(self, status_text):
        self.current_status = status_text

    def check_should_upgrade(self):
        failed = False
        should_upgrade = False
        if self.db.version > LATEST_DB_VERSION:
            msg = u"The on-disk tribler database is newer than your tribler version. Your database will be backed up."
            self.current_status = msg
            self._logger.info(msg)
            failed = True
        elif self.db.version < LOWEST_SUPPORTED_DB_VERSION:
            msg = u"Database is too old %s < %s" % (self.db.version, LOWEST_SUPPORTED_DB_VERSION)
            self.current_status = msg
            failed = True
        elif self.db.version == LATEST_DB_VERSION:
            self._logger.info(u"tribler is in the latest version, no need to upgrade")
            failed = False
        else:
            should_upgrade = True

        return (failed, should_upgrade)


    @call_on_reactor_thread
    @inlineCallbacks
    def upgrade_database_to_current_version(self, failed):
        """ Checks the database version and upgrade if it is not the latest version.
        """
        try:
            from Tribler.Core.leveldbstore import LevelDbStore
            torrent_store = LevelDbStore(self.session.get_torrent_store_dir())
            torrent_migrator = TorrentMigrator65(
                self.session, self.db, torrent_store=torrent_store, status_update_func=self.update_status)
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
        except Exception as e:
            self._logger.exception(u"failed to upgrade: %s", e)

    @call_on_reactor_thread
    def stash_database(self):
        self._stash_database_away()

    def _stash_database_away(self):
        self.db.close()
        old_dir = os.path.dirname(self.db.sqlite_db_path)
        new_dir = u'%s_backup_%d' % (old_dir, LATEST_DB_VERSION)
        shutil.move(old_dir, new_dir)
        os.makedirs(old_dir)
        self.db.initialize()
