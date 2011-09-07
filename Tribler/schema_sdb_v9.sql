-- Tribler SQLite Database
-- Version: 8
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
  torrent_id  integer NOT NULL,
  -- V2: Patch for BuddyCast 4
  click_position INTEGER DEFAULT -1,
  reranking_strategy INTEGER DEFAULT -1
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

CREATE UNIQUE INDEX infohash_idx
  ON Torrent
  (infohash);

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

CREATE INDEX Torrent_name_idx 
  ON Torrent
  (name);

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

CREATE TABLE ClicklogTerm (
                    term_id INTEGER PRIMARY KEY AUTOINCREMENT DEFAULT 0,
                    term VARCHAR(255) NOT NULL,
                    times_seen INTEGER DEFAULT 0 NOT NULL
                    );
CREATE INDEX idx_terms_term ON ClicklogTerm(term);  





--v4: Path for BuddyCast 5. Adding Popularity table

CREATE TABLE Popularity (
                         torrent_id INTEGER,
                         peer_id INTEGER,
                         msg_receive_time NUMERIC,
                         size_calc_age NUMERIC,
                         num_seeders INTEGER DEFAULT 0,
                         num_leechers INTEGER DEFAULT 0,
                         num_of_sources INTEGER DEFAULT 0
                     );

CREATE INDEX Message_receive_time_idx 
  ON Popularity 
   (msg_receive_time);

CREATE INDEX Size_calc_age_idx 
  ON Popularity 
   (size_calc_age);

CREATE INDEX Number_of_seeders_idx 
  ON Popularity 
   (num_seeders);

CREATE INDEX Number_of_leechers_idx 
  ON Popularity 
   (num_leechers);

CREATE UNIQUE INDEX Popularity_idx
  ON Popularity
   (torrent_id, peer_id, msg_receive_time);

----------------------------------------

CREATE TABLE InvertedIndex (
word               text NOT NULL,
torrent_id         integer
);

CREATE INDEX word_idx
on InvertedIndex
(word);

CREATE UNIQUE INDEX invertedindex_idx
on InvertedIndex
(word,torrent_id);
--------------------------------------

-- v5 Subtitles DB
CREATE TABLE Metadata (
  metadata_id integer PRIMARY KEY ASC AUTOINCREMENT NOT NULL,
  publisher_id text NOT NULL,
  infohash text NOT NULL,
  description text,
  timestamp integer NOT NULL,
  signature text NOT NULL,
  UNIQUE (publisher_id, infohash),
  FOREIGN KEY (publisher_id, infohash) 
    REFERENCES ChannelCast(publisher_id, infohash) 
    ON DELETE CASCADE -- the fk constraint is not enforced by sqlite
);

CREATE INDEX infohash_md_idx
on Metadata(infohash);

CREATE INDEX pub_md_idx
on Metadata(publisher_id);


CREATE TABLE Subtitles (
  metadata_id_fk integer,
  subtitle_lang text NOT NULL,
  subtitle_location text,
  checksum text NOT NULL,
  UNIQUE (metadata_id_fk,subtitle_lang),
  FOREIGN KEY (metadata_id_fk) 
    REFERENCES Metadata(metadata_id) 
    ON DELETE CASCADE, -- the fk constraint is not enforced by sqlite
  
  -- ISO639-2 uses 3 characters for lang codes
  CONSTRAINT lang_code_length 
    CHECK ( length(subtitle_lang) == 3 ) 
);


CREATE INDEX metadata_sub_idx
on Subtitles(metadata_id_fk);

-- Stores the subtitles that peers have as an integer bitmask
 CREATE TABLE SubtitlesHave (
    metadata_id_fk integer,
    peer_id text NOT NULL,
    have_mask integer NOT NULL,
    received_ts integer NOT NULL, --timestamp indicating when the mask was received
    UNIQUE (metadata_id_fk, peer_id),
    FOREIGN KEY (metadata_id_fk)
      REFERENCES Metadata(metadata_id)
      ON DELETE CASCADE, -- the fk constraint is not enforced by sqlite

    -- 32 bit unsigned integer
    CONSTRAINT have_mask_length
      CHECK (have_mask >= 0 AND have_mask < 4294967296)
);

CREATE INDEX subtitles_have_idx
on SubtitlesHave(metadata_id_fk);

-- this index can boost queries
-- ordered by timestamp on the SubtitlesHave DB
CREATE INDEX subtitles_have_ts
on SubtitlesHave(received_ts);

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

CREATE TABLE IF NOT EXISTS Channels (
  id                        integer         PRIMARY KEY ASC,
  dispersy_cid              text,       
  peer_id                   integer,
  name                      text            NOT NULL,
  description               text,
  modified                  integer         DEFAULT (strftime('%s','now')),
  inserted                  integer         DEFAULT (strftime('%s','now')),
  nr_torrents               integer         DEFAULT 0,
  nr_spam                   integer         DEFAULT 0,
  nr_favorite               integer         DEFAULT 0
);
CREATE TABLE IF NOT EXISTS ChannelTorrents (
  id                        integer         PRIMARY KEY ASC,
  dispersy_id               integer,
  torrent_id                integer         NOT NULL,
  channel_id                integer         NOT NULL,
  name                      text,
  description               text,
  time_stamp                integer,
  modified                  integer         DEFAULT (strftime('%s','now')),
  inserted                  integer         DEFAULT (strftime('%s','now')),
  UNIQUE (torrent_id, channel_id),
  UNIQUE (dispersy_id),
  FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS TorChannelIndex ON ChannelTorrents(channel_id);
CREATE TABLE IF NOT EXISTS Playlists (
  id                        integer         PRIMARY KEY ASC,
  channel_id                integer         NOT NULL,
  dispersy_id               integer         NOT NULL,
  playlist_id               integer,
  name                      text            NOT NULL,
  description               text,
  modified                  integer         DEFAULT (strftime('%s','now')),
  inserted                  integer         DEFAULT (strftime('%s','now')),
  UNIQUE (dispersy_id),
  FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS PlayChannelIndex ON Playlists(channel_id);
CREATE TABLE IF NOT EXISTS PlaylistTorrents (
  playlist_id           integer,
  channeltorrent_id     integer,
  PRIMARY KEY (playlist_id, channeltorrent_id),
  FOREIGN KEY (playlist_id) REFERENCES Playlists(id) ON DELETE CASCADE,
  FOREIGN KEY (channeltorrent_id) REFERENCES ChannelTorrents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS PlayTorrentIndex ON PlaylistTorrents(playlist_id);

CREATE TABLE IF NOT EXISTS Comments (
  id                    integer         PRIMARY KEY ASC,
  dispersy_id           integer         NOT NULL,
  peer_id               integer,
  channel_id            integer         NOT NULL,
  comment               text            NOT NULL,
  reply_to_id           integer,
  reply_after_id        integer,
  time_stamp            integer,
  inserted              integer         DEFAULT (strftime('%s','now')),
  UNIQUE (dispersy_id),
  FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ComChannelIndex ON Comments(channel_id);

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

CREATE TABLE IF NOT EXISTS Warnings (
  id                    integer         PRIMARY KEY ASC,
  dispersy_id           integer         NOT NULL,
  channel_id            integer         NOT NULL,
  peer_id               integer,
  by_peer_id            integer         NOT NULL,
  severity              integer         NOT NULL DEFAULT (1),
  message               text            NOT NULL,
  cause                 integer         NOT NULL,
  time_stamp            integer         NOT NULL,
  UNIQUE (dispersy_id),
  FOREIGN KEY (channel_id) REFERENCES Channels(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS WaChannelIndex ON Warnings(channel_id);

CREATE TABLE IF NOT EXISTS ChannelMetaData (
  id                    integer         PRIMARY KEY ASC,
  dispersy_id           integer         NOT NULL,
  channel_id            integer         NOT NULL,
  type_id               integer         NOT NULL,
  value                 text            NOT NULL,
  prev_modification     integer,
  prev_global_time      integer,
  inserted              integer         DEFAULT (strftime('%s','now')),
  UNIQUE (dispersy_id),
  FOREIGN KEY (type_id) REFERENCES MetaDataTypes(id) ON DELETE CASCADE
);
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

CREATE TABLE IF NOT EXISTS ChannelVotes (
  channel_id            integer,
  voter_id              integer,
  dispersy_id           integer,
  vote                  integer,
  time_stamp            integer,
  UNIQUE (dispersy_id),
  PRIMARY KEY (channel_id, voter_id)
);
CREATE INDEX IF NOT EXISTS ChaVotIndex ON ChannelVotes(channel_id);
CREATE INDEX IF NOT EXISTS VotChaIndex ON ChannelVotes(voter_id);

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

CREATE TABLE IF NOT EXISTS TorrentMarkings (
  dispersy_id           integer NOT NULL,
  channeltorrent_id     integer NOT NULL,
  peer_id               integer,
  global_time           integer,
  type                  text    NOT NULL,
  time_stamp            integer NOT NULL,
  UNIQUE (dispersy_id),
  PRIMARY KEY (channeltorrent_id, peer_id)
);
CREATE INDEX IF NOT EXISTS TorMarkIndex ON TorrentMarkings(channeltorrent_id);



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

INSERT INTO MyInfo VALUES ('version', 9);

INSERT INTO MetaDataTypes ('name') VALUES ('name');
INSERT INTO MetaDataTypes ('name') VALUES ('description');

COMMIT TRANSACTION init_values;
