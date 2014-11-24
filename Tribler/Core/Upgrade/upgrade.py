import logging
import os

from Tribler.dispersy.util import call_on_reactor_thread
from Tribler.Core.CacheDB.db_versions import LOWEST_SUPPORTED_DB_VERSION, LATEST_DB_VERSION
from Tribler.Core.Upgrade.upgrade64 import TorrentMigrator64


# Database versions:
#   *earlier versions are no longer supported
#   17   is used by Tribler 5.9.x - 6.0
#   18   is used by Tribler 6.1.x - 6.2.0
#   22   is used by Tribler 6.3.x
#   23   is used by Tribler 6.4


class VersionNoLongerSupportedError(Exception):
    pass


class DatabaseUpgradeError(Exception):
    pass


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
                # version 17 -> 18
                if self.db.version == 17:
                    self._upgrade_17_to_18()

                # version 18 -> 22
                if self.db.version == 18:
                    self._upgrade_18_to_22()

                # version 22 -> 23
                if self.db.version == 22:
                    # TODO(emilon): TorrentMigrator64 shouldn't upgrade the database
                    # as it breaks the case where the DB version is older than 17.
                    migrator = TorrentMigrator64(self.session, self.db, status_update_func=self.update_status)
                    migrator.start_migrate()

                # check if we managed to upgrade to the latest DB version.
                if self.db.version == LATEST_DB_VERSION:
                    self.current_status = u"Done."
                    self.failed = False
                else:
                    if self.db.version < LOWEST_SUPPORTED_DB_VERSION:
                        msg = u"Database is too old %s < %s" % (self.db.version, LOWEST_SUPPORTED_DB_VERSION)
                        self.update_status(msg)
                        raise VersionNoLongerSupportedError(msg)
                    else:
                        msg = u"Database upgrade failed: %s -> %s" % (self.db.version, LATEST_DB_VERSION)
                        self.update_status(msg)
                        raise DatabaseUpgradeError(msg)

            except Exception as e:
                self.failed = True
                self._logger.error(u"failed to upgrade: %s", e)
                raise

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

    def _upgrade_17_to_18(self):
        self.current_status = u"Upgrading database from v%s to v%s..." % (17, 18)

        self.db.execute(u"""
DROP TABLE IF EXISTS BarterCast;
DROP INDEX IF EXISTS bartercast_idx;
INSERT OR IGNORE INTO MetaDataTypes ('name') VALUES ('swift-thumbnails');
INSERT OR IGNORE INTO MetaDataTypes ('name') VALUES ('video-info');
""")
        # update database version
        self.db.write_version(18)

    def _upgrade_18_to_22(self):
        self.current_status = u"Upgrading database from v%s to v%s..." % (18, 22)

        self.db.execute(u"""
DROP INDEX IF EXISTS Torrent_swift_hash_idx;

DROP VIEW IF EXISTS Friend;

ALTER TABLE Peer RENAME TO __Peer_tmp;
CREATE TABLE IF NOT EXISTS Peer (
    peer_id    integer PRIMARY KEY AUTOINCREMENT NOT NULL,
    permid     text NOT NULL,
    name       text,
    thumbnail  text
);

INSERT INTO Peer (peer_id, permid, name, thumbnail) SELECT peer_id, permid, name, thumbnail FROM __Peer_tmp;

DROP TABLE IF EXISTS __Peer_tmp;

ALTER TABLE Torrent ADD COLUMN last_tracker_check integer DEFAULT 0;
ALTER TABLE Torrent ADD COLUMN tracker_check_retries integer DEFAULT 0;
ALTER TABLE Torrent ADD COLUMN next_tracker_check integer DEFAULT 0;

CREATE TABLE IF NOT EXISTS TrackerInfo (
  tracker_id  integer PRIMARY KEY AUTOINCREMENT,
  tracker     text    UNIQUE NOT NULL,
  last_check  numeric DEFAULT 0,
  failures    integer DEFAULT 0,
  is_alive    integer DEFAULT 1
);

CREATE TABLE IF NOT EXISTS TorrentTrackerMapping (
  torrent_id  integer NOT NULL,
  tracker_id  integer NOT NULL,
  FOREIGN KEY (torrent_id) REFERENCES Torrent(torrent_id),
  FOREIGN KEY (tracker_id) REFERENCES TrackerInfo(tracker_id),
  PRIMARY KEY (torrent_id, tracker_id)
);

INSERT OR IGNORE INTO TrackerInfo (tracker) VALUES ('no-DHT');
INSERT OR IGNORE INTO TrackerInfo (tracker) VALUES ('DHT');

DROP INDEX IF EXISTS torrent_biterm_phrase_idx;
DROP TABLE IF EXISTS TorrentBiTermPhrase;
DROP INDEX IF EXISTS termfrequency_freq_idx;
DROP TABLE IF EXISTS TermFrequency;
DROP INDEX IF EXISTS Torrent_insert_idx;
DROP INDEX IF EXISTS Torrent_info_roothash_idx;

DROP TABLE IF EXISTS ClicklogSearch;
DROP INDEX IF EXISTS idx_search_term;
DROP INDEX IF EXISTS idx_search_torrent;
""")
        # update database version
        self.db.write_version(22)
