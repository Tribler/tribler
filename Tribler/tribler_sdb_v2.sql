-- Tribler SQLite Database
-- Version: 2

BEGIN TRANSACTION create_table;

----------------------------------------

CREATE TABLE IF NOT EXISTS BarterCast (
  peer_id_from  integer,
  peer_id_to    integer,
  downloaded    numeric,
  uploaded      numeric,
  last_seen     numeric,
  value         numeric
);

CREATE UNIQUE INDEX IF NOT EXISTS bartercast_idx
  ON BarterCast
  (peer_id_from, peer_id_to);

----------------------------------------

CREATE TABLE IF NOT EXISTS Category (
  category_id    integer PRIMARY KEY NOT NULL,
  name           text NOT NULL,
  description    text
);

----------------------------------------

CREATE TABLE IF NOT EXISTS MyInfo (
  entry  PRIMARY KEY,
  value  text
);

----------------------------------------

CREATE TABLE IF NOT EXISTS MyPreference (
  torrent_id     integer PRIMARY KEY NOT NULL,
  destination_path text NOT NULL,
  progress       numeric,
  creation_time  integer NOT NULL
);

----------------------------------------

CREATE TABLE IF NOT EXISTS Peer (
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
  num_queries          integer
);

CREATE UNIQUE INDEX IF NOT EXISTS permid_idx
  ON Peer
  (permid);

CREATE INDEX IF NOT EXISTS Peer_name_idx
  ON Peer
  (name);

CREATE INDEX IF NOT EXISTS Peer_ip_idx
  ON Peer
  (ip);

CREATE INDEX IF NOT EXISTS Peer_similarity_idx
  ON Peer
  (similarity);

CREATE INDEX IF NOT EXISTS Peer_last_seen_idx
  ON Peer
  (last_seen);

CREATE INDEX IF NOT EXISTS Peer_last_connected_idx
  ON Peer
  (last_connected);

CREATE INDEX IF NOT EXISTS Peer_num_peers_idx
  ON Peer
  (num_peers);

CREATE INDEX IF NOT EXISTS Peer_num_torrents_idx
  ON Peer
  (num_torrents);

----------------------------------------

CREATE TABLE IF NOT EXISTS Preference (
  peer_id     integer NOT NULL,
  torrent_id  integer NOT NULL
);

CREATE INDEX IF NOT EXISTS Preference_peer_id_idx
  ON Preference
  (peer_id);

CREATE INDEX IF NOT EXISTS Preference_torrent_id_idx
  ON Preference
  (torrent_id);

CREATE UNIQUE INDEX IF NOT EXISTS pref_idx
  ON Preference
  (peer_id, torrent_id);

----------------------------------------

CREATE TABLE IF NOT EXISTS Torrent (
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
  comment          text
);

CREATE UNIQUE INDEX IF NOT EXISTS infohash_idx
  ON Torrent
  (infohash);

CREATE INDEX IF NOT EXISTS Torrent_length_idx
  ON Torrent
  (length);

CREATE INDEX IF NOT EXISTS Torrent_creation_date_idx
  ON Torrent
  (creation_date);

CREATE INDEX IF NOT EXISTS Torrent_relevance_idx
  ON Torrent
  (relevance);

CREATE INDEX IF NOT EXISTS Torrent_num_seeders_idx
  ON Torrent
  (num_seeders);

CREATE INDEX IF NOT EXISTS Torrent_num_leechers_idx
  ON Torrent
  (num_leechers);

CREATE INDEX IF NOT EXISTS Torrent_name_idx 
  ON Torrent
  (name);

----------------------------------------

CREATE TABLE IF NOT EXISTS TorrentSource (
  source_id    integer PRIMARY KEY NOT NULL,
  name         text NOT NULL,
  description  text
);

CREATE UNIQUE INDEX IF NOT EXISTS torrent_source_idx
  ON TorrentSource
  (name);

----------------------------------------

CREATE TABLE IF NOT EXISTS TorrentStatus (
  status_id    integer PRIMARY KEY NOT NULL,
  name         text NOT NULL,
  description  text
);

----------------------------------------

CREATE TABLE IF NOT EXISTS TorrentTracker (
  torrent_id   integer NOT NULL,
  tracker      text NOT NULL,
  announce_tier    integer,
  ignored_times    integer,
  retried_times    integer,
  last_check       numeric
);

CREATE UNIQUE INDEX IF NOT EXISTS torrent_tracker_idx
  ON TorrentTracker
  (torrent_id, tracker);

----------------------------------------

CREATE TABLE IF NOT EXISTS ModerationCast (
mod_id text,
mod_name text,
infohash text not NULL,
time_stamp integer,
media_type text,
quality text,
tags text,
signature integer
);

CREATE INDEX IF NOT EXISTS moderationcast_idx
ON ModerationCast
(mod_id);

----------------------------------------

CREATE TABLE IF NOT EXISTS Moderators (
mod_id integer,
status integer,
time_stamp integer
);

CREATE UNIQUE INDEX IF NOT EXISTS moderators_idx
ON Moderators
(mod_id);

----------------------------------------

CREATE TABLE IF NOT EXISTS VoteCast (
mod_id text,
voter_id integer,
vote text,
time_stamp integer
);

CREATE UNIQUE INDEX IF NOT EXISTS votecast_idx
ON VoteCast
(mod_id, voter_id);

----------------------------------------

CREATE VIEW IF NOT EXISTS SuperPeer AS SELECT * FROM Peer WHERE superpeer=1;

CREATE VIEW IF NOT EXISTS Friend AS SELECT * FROM Peer WHERE friend=1;

CREATE VIEW IF NOT EXISTS CollectedTorrent AS SELECT * FROM Torrent WHERE torrent_file_name IS NOT NULL;

COMMIT TRANSACTION create_table;

----------------------------------------

BEGIN TRANSACTION init_values;

INSERT OR IGNORE INTO Category VALUES (1, 'Video', 'Video Files');
INSERT OR IGNORE INTO Category VALUES (2, 'VideoClips', 'Video Clips');
INSERT OR IGNORE INTO Category VALUES (3, 'Audio', 'Audio');
INSERT OR IGNORE INTO Category VALUES (4, 'Compressed', 'Compressed');
INSERT OR IGNORE INTO Category VALUES (5, 'Document', 'Documents');
INSERT OR IGNORE INTO Category VALUES (6, 'Picture', 'Pictures');
INSERT OR IGNORE INTO Category VALUES (7, 'xxx', 'XXX');
INSERT OR IGNORE INTO Category VALUES (8, 'other', 'Other');

INSERT OR IGNORE INTO TorrentStatus VALUES (0, 'unknown', NULL);
INSERT OR IGNORE INTO TorrentStatus VALUES (1, 'good', NULL);
INSERT OR IGNORE INTO TorrentStatus VALUES (2, 'dead', NULL);

INSERT OR IGNORE INTO TorrentSource VALUES (0, '', 'Unknown');
INSERT OR IGNORE INTO TorrentSource VALUES (1, 'BC', 'Received from other user');

INSERT OR REPLACE INTO MyInfo VALUES ('version', 2);

COMMIT TRANSACTION init_values;
