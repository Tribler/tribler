-- Tribler SQLite Database
-- Version: 9
--
-- History:
--   v1: Published as part of Tribler 4.5
--   v2: Published as part of Tribler 5.0
--   v3: Published as part of Next-Share M16
--   v4: Published as part of Tribler 5.2
--   v5: Published as part of Next-Share M30 for subtitles integration
--   v7: Published as part of Tribler 5.3
--   v8: Published as part of Tribler 5.4
--   v8: Published as part of Tribler 5.5/6.0?
--   v9: Published as part of Tribler 5.5

-- 
-- See Tribler/Core/CacheDB/sqlitecachedb.py updateDB() for exact version diffs.
--
-- v4: ChannelCast is an extension of the concept of ModerationCast, with 
--     an additional integrity measure. 'torrenthash' field is used to protect 
--     the integrity of the torrent file created by the publisher, from fake-
--     tracker attack, by including sha1 hash of the dictionary corresponding 
--     to the entire torrent.
--
--     'InvertedIndex' table is used for precise keyword matching than 
--     substring search that was used previously.

BEGIN TRANSACTION create_table;

----------------------------------------

CREATE TABLE BarterCast (
  peer_id_from  integer,
  peer_id_to    integer,
  downloaded    numeric,
  uploaded      numeric,
  last_seen     numeric,
  value         numeric
);

CREATE UNIQUE INDEX bartercast_idx
  ON BarterCast
  (peer_id_from, peer_id_to);

----------------------------------------

CREATE TABLE Category (
  category_id    integer PRIMARY KEY NOT NULL,
  name           text NOT NULL,
  description    text
);

----------------------------------------

CREATE TABLE MyInfo (
  entry  PRIMARY KEY,
  value  text
);

----------------------------------------

CREATE TABLE MyPreference (
  torrent_id     integer PRIMARY KEY NOT NULL,
  destination_path text NOT NULL,
  progress       numeric,
  creation_time  integer NOT NULL,
  -- V2: Patch for BuddyCast 4
  click_position INTEGER DEFAULT -1,
  reranking_strategy INTEGER DEFAULT -1
);

----------------------------------------

CREATE TABLE Peer (
  peer_id              integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  permid               text NOT NULL,
  name                 text,
  ip                   text,
  port                 integer,
  thumbnail            text,
  oversion             integer,
  similarity           numeric DEFAULT 0,
  friend               integer DEFAULT 0,
  superpeer            integer DEFAULT 0,
  last_seen            numeric DEFAULT 0,
  last_connected       numeric,
  last_buddycast       numeric,
  connected_times      integer DEFAULT 0,
  buddycast_times      integer DEFAULT 0,
  num_peers            integer,
  num_torrents         integer,
  num_prefs            integer,
  num_queries          integer,
  -- V3: Addition for local peer discovery
  is_local	       integer DEFAULT 0,
  -- V6 P2P Services (ProxyService)
  services              integer DEFAULT 0
);

CREATE UNIQUE INDEX permid_idx
  ON Peer
  (permid);

----------------------------------------

CREATE TABLE Torrent (
  torrent_id       integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  infohash		   text NOT NULL,
  name             text,
  torrent_file_name text,
  length           integer,
  creation_date    integer,
  num_files        integer,
  thumbnail        integer,
  insert_time      numeric,
  secret           integer,
  relevance        numeric DEFAULT 0,
  source_id        integer,
  category_id      integer,
  status_id        integer,
  num_seeders      integer,
  num_leechers     integer,
  comment          text,
  dispersy_id      integer,
  swift_hash        text,
  swift_torrent_hash text,
  tracker_check_retries integer DEFAULT 0,
  last_tracker_check    numeric DEFAULT 0,
  trackers              text
);

CREATE UNIQUE INDEX infohash_idx
  ON Torrent
  (infohash);

CREATE INDEX Torrent_insert_idx 
  ON Torrent 
  (insert_time, swift_torrent_hash);

CREATE INDEX Torrent_info_roothash_idx
  ON Torrent
  (infohash, swift_torrent_hash);

 -- Arno, 2012-07-05: speed up
CREATE UNIQUE INDEX Torrent_swift_hash_idx
  ON Torrent
  (swift_hash);

-- Arno, 2012-07-30: speed up on_torrent_collect_response
CREATE UNIQUE INDEX Torrent_swift_torrent_hash_idx
  ON Torrent
  (swift_torrent_hash);


----------------------------------------

CREATE TABLE TorrentSource (
  source_id    integer PRIMARY KEY NOT NULL,
  name         text NOT NULL,
  description  text
);

CREATE UNIQUE INDEX torrent_source_idx
  ON TorrentSource
  (name);

----------------------------------------

CREATE TABLE TorrentStatus (
  status_id    integer PRIMARY KEY NOT NULL,
  name         text NOT NULL,
  description  text
);

----------------------------------------

CREATE TABLE TorrentTracker (
  torrent_id   integer NOT NULL,
  tracker      text NOT NULL,
  announce_tier    integer,
  ignored_times    integer,
  retried_times    integer,
  last_check       numeric
);

CREATE TABLE TrackerInfo (
  tracker     text    PRIMARY KEY,
  last_check  numeric DEFAULT 0,
  failures    integer DEFAULT 0,
  is_alive    integer DEFAULT 1
);

CREATE UNIQUE INDEX torrent_tracker_idx
  ON TorrentTracker
  (torrent_id, tracker);

CREATE INDEX torrent_tracker_last_idx ON TorrentTracker (tracker, last_check );

----------------------------------------

CREATE VIEW Friend AS SELECT * FROM Peer WHERE friend=1;

CREATE VIEW CollectedTorrent AS SELECT * FROM Torrent WHERE torrent_file_name IS NOT NULL;

-- V2: Patch for BuddyCast 4

CREATE TABLE ClicklogSearch (
                     peer_id INTEGER DEFAULT 0,
                     torrent_id INTEGER DEFAULT 0,
                     term_id INTEGER DEFAULT 0,
                     term_order INTEGER DEFAULT 0
                     );
CREATE INDEX idx_search_term ON ClicklogSearch (term_id);
CREATE INDEX idx_search_torrent ON ClicklogSearch (torrent_id);

-------------------------------------

-- v7: TermFrequency and TorrentBiTermPhrase
--     for "Network Buzz" feature;
--     Also UserEventLog table for user studies.

CREATE TABLE TermFrequency (
  term_id        integer PRIMARY KEY AUTOINCREMENT DEFAULT 0,
  term           text NOT NULL,
  freq           integer,
  UNIQUE (term)
);

CREATE INDEX termfrequency_freq_idx
  ON TermFrequency
  (freq);

CREATE TABLE TorrentBiTermPhrase (
  torrent_id     integer PRIMARY KEY NOT NULL,
  term1_id       integer,
  term2_id       integer,
  UNIQUE (torrent_id),
  FOREIGN KEY (torrent_id)
    REFERENCES Torrent(torrent_id),
  FOREIGN KEY (term1_id)
    REFERENCES TermFrequency(term_id),
  FOREIGN KEY (term2_id)
    REFERENCES TermFrequency(term_id)
);
CREATE INDEX torrent_biterm_phrase_idx
  ON TorrentBiTermPhrase
  (term1_id, term2_id);

CREATE TABLE UserEventLog (
  timestamp      numeric,
  type           integer,
  message        text
);

----------------------------------------
-- v8: BundlerPreference

CREATE TABLE BundlerPreference (
  query         text PRIMARY KEY,
  bundle_mode   integer
);

----------------------------------------
-- v9: Open2Edit replacing ChannelCast tables

CREATE TABLE IF NOT EXISTS _Channels (
  id                        integer         PRIMARY KEY ASC,
  dispersy_cid              text,       
  peer_id                   integer,
  name                      text            NOT NULL,
  description               text,
  modified                  integer         DEFAULT (strftime('%s','now')),
  inserted                  integer         DEFAULT (strftime('%s','now')),
  deleted_at                integer,
  nr_torrents               integer         DEFAULT 0,
  nr_spam                   integer         DEFAULT 0,
  nr_favorite               integer         DEFAULT 0
);
CREATE VIEW Channels AS SELECT * FROM _Channels WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS _ChannelTorrents (
  id                        integer         PRIMARY KEY ASC,
  dispersy_id               integer,
  torrent_id                integer         NOT NULL,
  channel_id                integer         NOT NULL,
  peer_id                   integer,
  name                      text,
  description               text,
  time_stamp                integer,
  modified                  integer         DEFAULT (strftime('%s','now')),
  inserted                  integer         DEFAULT (strftime('%s','now')),
  deleted_at                integer,
  FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
);
CREATE VIEW ChannelTorrents AS SELECT * FROM _ChannelTorrents WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS TorChannelIndex ON _ChannelTorrents(channel_id);
CREATE INDEX IF NOT EXISTS ChannelTorIndex ON _ChannelTorrents(torrent_id);
CREATE INDEX IF NOT EXISTS ChannelTorChanIndex ON _ChannelTorrents(torrent_id, channel_id);

CREATE TABLE IF NOT EXISTS _Playlists (
  id                        integer         PRIMARY KEY ASC,
  channel_id                integer         NOT NULL,
  dispersy_id               integer         NOT NULL,
  peer_id                   integer,
  playlist_id               integer,
  name                      text            NOT NULL,
  description               text,
  modified                  integer         DEFAULT (strftime('%s','now')),
  inserted                  integer         DEFAULT (strftime('%s','now')),
  deleted_at                integer,
  UNIQUE (dispersy_id),
  FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
);
CREATE VIEW Playlists AS SELECT * FROM _Playlists WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS PlayChannelIndex ON _Playlists(channel_id);

CREATE TABLE IF NOT EXISTS _PlaylistTorrents (
  id                    integer         PRIMARY KEY ASC,
  dispersy_id           integer         NOT NULL,
  peer_id               integer,
  playlist_id           integer,
  channeltorrent_id     integer,
  deleted_at            integer,
  FOREIGN KEY (playlist_id) REFERENCES Playlists(id) ON DELETE CASCADE,
  FOREIGN KEY (channeltorrent_id) REFERENCES ChannelTorrents(id) ON DELETE CASCADE
);
CREATE VIEW PlaylistTorrents AS SELECT * FROM _PlaylistTorrents WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS PlayTorrentIndex ON _PlaylistTorrents(playlist_id);

CREATE TABLE IF NOT EXISTS _Comments (
  id                    integer         PRIMARY KEY ASC,
  dispersy_id           integer         NOT NULL,
  peer_id               integer,
  channel_id            integer         NOT NULL,
  comment               text            NOT NULL,
  reply_to_id           integer,
  reply_after_id        integer,
  time_stamp            integer,
  inserted              integer         DEFAULT (strftime('%s','now')),
  deleted_at            integer,
  UNIQUE (dispersy_id),
  FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
);
CREATE VIEW Comments AS SELECT * FROM _Comments WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ComChannelIndex ON _Comments(channel_id);

CREATE TABLE IF NOT EXISTS CommentPlaylist (
  comment_id            integer,
  playlist_id           integer,
  PRIMARY KEY (comment_id,playlist_id),
  FOREIGN KEY (playlist_id) REFERENCES Playlists(id) ON DELETE CASCADE
  FOREIGN KEY (comment_id) REFERENCES Comments(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS CoPlaylistIndex ON CommentPlaylist(playlist_id);

CREATE TABLE IF NOT EXISTS CommentTorrent (
  comment_id            integer,
  channeltorrent_id     integer,
  PRIMARY KEY (comment_id, channeltorrent_id),
  FOREIGN KEY (comment_id) REFERENCES Comments(id) ON DELETE CASCADE
  FOREIGN KEY (channeltorrent_id) REFERENCES ChannelTorrents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS CoTorrentIndex ON CommentTorrent(channeltorrent_id);

CREATE TABLE IF NOT EXISTS _Moderations (
  id                    integer         PRIMARY KEY ASC,
  dispersy_id           integer         NOT NULL,
  channel_id            integer         NOT NULL,
  peer_id               integer,
  severity              integer         NOT NULL DEFAULT (0),
  message               text            NOT NULL,
  cause                 integer         NOT NULL,
  by_peer_id            integer,
  time_stamp            integer         NOT NULL,
  inserted              integer         DEFAULT (strftime('%s','now')),
  deleted_at            integer,
  UNIQUE (dispersy_id),
  FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
);
CREATE VIEW Moderations AS SELECT * FROM _Moderations WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS MoChannelIndex ON _Moderations(channel_id);

CREATE TABLE IF NOT EXISTS _ChannelMetaData (
  id                    integer         PRIMARY KEY ASC,
  dispersy_id           integer         NOT NULL,
  channel_id            integer         NOT NULL,
  peer_id               integer,
  type_id               integer         NOT NULL,
  value                 text            NOT NULL,
  prev_modification     integer,
  prev_global_time      integer,
  time_stamp            integer         NOT NULL,
  inserted              integer         DEFAULT (strftime('%s','now')),
  deleted_at            integer,
  UNIQUE (dispersy_id),
  FOREIGN KEY (type_id) REFERENCES MetaDataTypes(id) ON DELETE CASCADE
);
CREATE VIEW ChannelMetaData AS SELECT * FROM _ChannelMetaData WHERE deleted_at IS NULL;
CREATE TABLE IF NOT EXISTS MetaDataTypes (
  id                    integer         PRIMARY KEY ASC,
  name                  text            NOT NULL,
  type                  text            NOT NULL DEFAULT('text')
);

CREATE TABLE IF NOT EXISTS MetaDataTorrent (
  metadata_id           integer,
  channeltorrent_id     integer,
  PRIMARY KEY (metadata_id, channeltorrent_id),
  FOREIGN KEY (metadata_id) REFERENCES ChannelMetaData(id) ON DELETE CASCADE
  FOREIGN KEY (channeltorrent_id) REFERENCES ChannelTorrents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS MeTorrentIndex ON MetaDataTorrent(channeltorrent_id);

CREATE TABLE IF NOT EXISTS MetaDataPlaylist (
  metadata_id           integer,
  playlist_id           integer,
  PRIMARY KEY (metadata_id,playlist_id),
  FOREIGN KEY (playlist_id) REFERENCES Playlists(id) ON DELETE CASCADE
  FOREIGN KEY (metadata_id) REFERENCES ChannelMetaData(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS MePlaylistIndex ON MetaDataPlaylist(playlist_id);

CREATE TABLE IF NOT EXISTS _ChannelVotes (
  channel_id            integer,
  voter_id              integer,
  dispersy_id           integer,
  vote                  integer,
  time_stamp            integer,
  deleted_at            integer,
  PRIMARY KEY (channel_id, voter_id)
);
CREATE VIEW ChannelVotes AS SELECT * FROM _ChannelVotes WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ChaVotIndex ON _ChannelVotes(channel_id);
CREATE INDEX IF NOT EXISTS VotChaIndex ON _ChannelVotes(voter_id);

CREATE TABLE IF NOT EXISTS TorrentFiles (
  torrent_id            integer NOT NULL,
  path                  text    NOT NULL,
  length                integer NOT NULL,
  PRIMARY KEY (torrent_id, path)
);
CREATE INDEX IF NOT EXISTS TorFileIndex ON TorrentFiles(torrent_id);

CREATE TABLE IF NOT EXISTS TorrentCollecting (
  torrent_id            integer NOT NULL,
  source                text    NOT NULL,
  PRIMARY KEY (torrent_id, source)
);
CREATE INDEX IF NOT EXISTS TorColIndex ON TorrentCollecting(torrent_id);

CREATE TABLE IF NOT EXISTS _TorrentMarkings (
  dispersy_id           integer NOT NULL,
  channeltorrent_id     integer NOT NULL,
  peer_id               integer,
  global_time           integer,
  type                  text    NOT NULL,
  time_stamp            integer NOT NULL,
  deleted_at            integer,
  UNIQUE (dispersy_id),
  PRIMARY KEY (channeltorrent_id, peer_id)
);
CREATE VIEW TorrentMarkings AS SELECT * FROM _TorrentMarkings WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS TorMarkIndex ON _TorrentMarkings(channeltorrent_id);

CREATE VIRTUAL TABLE FullTextIndex USING fts3(swarmname, filenames, fileextensions);

-------------------------------------

COMMIT TRANSACTION create_table;

----------------------------------------

BEGIN TRANSACTION init_values;

INSERT INTO Category VALUES (1, 'Video', 'Video Files');
INSERT INTO Category VALUES (2, 'VideoClips', 'Video Clips');
INSERT INTO Category VALUES (3, 'Audio', 'Audio');
INSERT INTO Category VALUES (4, 'Compressed', 'Compressed');
INSERT INTO Category VALUES (5, 'Document', 'Documents');
INSERT INTO Category VALUES (6, 'Picture', 'Pictures');
INSERT INTO Category VALUES (7, 'xxx', 'XXX');
INSERT INTO Category VALUES (8, 'other', 'Other');

INSERT INTO TorrentStatus VALUES (0, 'unknown', NULL);
INSERT INTO TorrentStatus VALUES (1, 'good', NULL);
INSERT INTO TorrentStatus VALUES (2, 'dead', NULL);

INSERT INTO TorrentSource VALUES (0, '', 'Unknown');
INSERT INTO TorrentSource VALUES (1, 'BC', 'Received from other user');

INSERT INTO MyInfo VALUES ('version', 18);

INSERT INTO MetaDataTypes ('name') VALUES ('name');
INSERT INTO MetaDataTypes ('name') VALUES ('description');
INSERT INTO MetaDataTypes ('name') VALUES ('swift-url');
INSERT INTO MetaDataTypes ('name') VALUES ('swift-thumbnails');
INSERT INTO MetaDataTypes ('name') VALUES ('video-info');

COMMIT TRANSACTION init_values;
