-- Tribler SQLite Database
-- Version: 1

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

CREATE TABLE Infohash (
  torrent_id  integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  infohash    text NOT NULL
);

CREATE UNIQUE INDEX infohash_idx
  ON Infohash
  (infohash);

----------------------------------------

CREATE TABLE MyInfo (
  entry  PRIMARY KEY,
  value  text
);

CREATE UNIQUE INDEX MyInfo_entry_idx
  ON MyInfo
  (entry);

----------------------------------------

CREATE TABLE MyPreference (
  torrent_id     integer PRIMARY KEY NOT NULL,
  destination_path text NOT NULL,
  progress       numeric,
  creation_time  integer NOT NULL
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
  similarity           numeric,
  friend               integer,
  superpeer            integer,
  last_seen            numeric,
  last_connected       numeric,
  last_buddycast       numeric,
  connected_times      integer,
  buddycast_times      integer,
  num_peers            integer,
  num_torrents         integer,
  num_prefs            integer,
  num_queries          integer
);

CREATE UNIQUE INDEX permid_idx
  ON Peer
  (permid);

CREATE INDEX Peer_name_idx
  ON Peer
  (name);

CREATE INDEX Peer_ip_idx
  ON Peer
  (ip);

CREATE INDEX Peer_similarity_idx
  ON Peer
  (similarity);

CREATE INDEX Peer_last_seen_idx
  ON Peer
  (last_seen);

CREATE INDEX Peer_last_connected_idx
  ON Peer
  (last_connected);

CREATE INDEX Peer_num_peers_idx
  ON Peer
  (num_peers);

CREATE INDEX Peer_num_torrents_idx
  ON Peer
  (num_torrents);

----------------------------------------

CREATE TABLE Preference (
  peer_id     integer NOT NULL,
  torrent_id  integer NOT NULL
);

CREATE INDEX Preference_peer_id_idx
  ON Preference
  (peer_id);

CREATE INDEX Preference_torrent_id_idx
  ON Preference
  (torrent_id);

CREATE UNIQUE INDEX pref_idx
  ON Preference
  (peer_id, torrent_id);

----------------------------------------

CREATE TABLE Torrent (
  torrent_id       integer PRIMARY KEY NOT NULL,
  name             text,
  torrent_file_name text,
  length           integer,
  creation_date    integer,
  num_files        integer,
  thumbnail        integer,
  insert_time      numeric,
  secret           integer,
  relevance        numeric,
  source_id        integer,
  category_id      integer,
  status_id        integer,
  num_seeders      integer,
  num_leechers     integer,
  comment          text
);

CREATE INDEX Torrent_length_idx
  ON Torrent
  (length);

CREATE INDEX Torrent_creation_date_idx
  ON Torrent
  (creation_date);

CREATE INDEX Torrent_relevance_idx
  ON Torrent
  (relevance);

CREATE INDEX Torrent_num_seeders_idx
  ON Torrent
  (num_seeders);

CREATE INDEX Torrent_num_leechers_idx
  ON Torrent
  (num_leechers);

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

CREATE UNIQUE INDEX torrent_tracker_idx
  ON TorrentTracker
  (torrent_id, tracker);
  
----------------------------------------

CREATE VIEW SuperPeer AS SELECT * FROM Peer WHERE superpeer=1;

CREATE VIEW Friend AS SELECT * FROM Peer WHERE friend=1;

COMMIT TRANSACTION create_table;

----------------------------------------

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

INSERT INTO MyInfo VALUES ('version', 1);
