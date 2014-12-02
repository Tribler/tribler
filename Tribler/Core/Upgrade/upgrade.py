import logging
import os

from Tribler.Core.CacheDB.db_versions import LOWEST_SUPPORTED_DB_VERSION, LATEST_DB_VERSION
from Tribler.Core.Upgrade.db_upgrader import DBUpgrader
from Tribler.Core.Upgrade.torrent_upgrade64 import TorrentMigrator64
from Tribler.dispersy.util import call_on_reactor_thread


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

        self.current_status = u"Checking Tribler version..."
        self.is_done = False
        self.failed = True

    def update_status(self, status_text):
        self.current_status = status_text

    @call_on_reactor_thread
    def check_and_upgrade(self):
        """ Checks the database version and upgrade if it is not the latest version.
        """
        if self.db.version == LATEST_DB_VERSION:
            self._logger.info(u"tribler is in the latest version, no need to upgrade")
            self.failed = False
        else:
            # upgrade
            try:
                torrent_migrator = TorrentMigrator64(self.session, self.db, status_update_func=self.update_status)
                torrent_migrator.start_migrate()

                db_migrator = DBUpgrader(self.session, self.db, status_update_func=self.update_status)
                db_migrator.start_migrate()

                # Import all the torrent files not in the database, we do this in
                # case we have some unhandled torrent files left due to
                # bugs/crashes, etc.
                db_migrator.reimport_torrents()

                self.failed = False
            except Exception as e:
                self._logger.error(u"failed to upgrade: %s", e)

        if self.failed:
            self._stash_database_away()

        self.is_done = True

    def _stash_database_away(self):
        self.db.close()
        old_dir = os.path.dirname(self.db.sqlite_db_path)
        new_dir = u'%s_backup_%d' % (old_dir, LATEST_DB_VERSION)
        os.rename(old_dir, new_dir)
        os.makedirs(old_dir)
        self.db.initialize()
