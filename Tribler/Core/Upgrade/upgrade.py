import logging

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

    def update_status(self, status_text):
        self.current_status = status_text

    def check_and_upgrade(self):
        """ Checks the database version and upgrade if it is not the latest version.
        """
        if self.db.version == LATEST_DB_VERSION:
            self._logger.info(u"Tribler is in the latest version, no need to upgrade")
            return

        # check if we support the version
        if self.db.version < LOWEST_SUPPORTED_DB_VERSION:
            msg = u"Version no longer supported: %s < %s" % (self.db.version, LOWEST_SUPPORTED_DB_VERSION)
            raise VersionNoLongerSupportedError(msg)

        # start upgrade
        self._start_upgrade()

        # make sure that after upgrade, we have the latest database version
        if self.db.version != LATEST_DB_VERSION:
            msg = u"Final version is not the latest version: %s, latest is %s" % (self.db.version, LATEST_DB_VERSION)
            raise DatabaseUpgradeError(msg)

    def _start_upgrade(self):
        # version 17 -> 18
        if self.db.version == 17:
            self._upgrade_17_to_18()

        # version 18 -> 22
        if self.db.version == 18:
            self._upgrade_18_to_22()

        # version 22 -> 23
        if self.db.version == 22:
            migrator = TorrentMigrator64(self.session, self.db, status_update_func=self.update_status)
            migrator.start_migrate()

    def _upgrade_17_to_18(self):
        self.current_status = u"Upgrading database from v%s to v%s..." % (17, 18)

        self.db.execute(u"""
DROP TABLE IF EXISTS BarterCast;
DROP INDEX IF EXISTS bartercast_idx;
INSERT INTO MetaDataTypes ('name') VALUES ('swift-thumbnails');
INSERT INTO MetaDataTypes ('name') VALUES ('video-info');
""")
        # update database version
        self.db.write_version(18)

    def _upgrade_18_to_22(self):
        self.current_status = u"Upgrading database from v%s to v%s..." % (18, 22)

        self.db.execute(u"""
DROP INDEX IF EXISTS Torrent_swift_hash_idx;

DROP VIEW Friend;

ALTER TABLE Peer RENAME TO __Peer_tmp
CREATE TABLE Peer (
    peer_id    integer PRIMARY KEY AUTOINCREMENT NOT NULL,
    permid     text NOT NULL,
    name       text,
    thumbnail  text
);

INSERT INTO Peer (peer_id, permid, name, thumbnail) SELECT peer_id, permid, name, thumbnail FROM __Peer_tmp;

DROP TABLE __Peer_tmp;

ALTER TABLE Torrent ADD COLUMN last_tracker_check integer DEFAULT 0;
ALTER TABLE Torrent ADD COLUMN tracker_check_retries integer DEFAULT 0;
ALTER TABLE Torrent ADD COLUMN next_tracker_check integer DEFAULT 0;

CREATE TABLE TrackerInfo (
  tracker_id  integer PRIMARY KEY AUTOINCREMENT,
  tracker     text    UNIQUE NOT NULL,
  last_check  numeric DEFAULT 0,
  failures    integer DEFAULT 0,
  is_alive    integer DEFAULT 1
);

CREATE TABLE TorrentTrackerMapping (
  torrent_id  integer NOT NULL,
  tracker_id  integer NOT NULL,
  FOREIGN KEY (torrent_id) REFERENCES Torrent(torrent_id),
  FOREIGN KEY (tracker_id) REFERENCES TrackerInfo(tracker_id),
  PRIMARY KEY (torrent_id, tracker_id)
);

INSERT INTO TrackerInfo (tracker) VALUES ('no-DHT');
INSERT INTO TrackerInfo (tracker) VALUES ('DHT');

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
