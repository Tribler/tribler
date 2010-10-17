-- Tribler SQLite Database
-- Version: 6
--
-- History:
--   v1: Published as part of Tribler 4.5
--   v2: Published as part of Tribler 5.0
--   v3: Published as part of Next-Share M16
--   v4: Published as part of Tribler 5.2
--   v5: Published as part of Next-Share M30 for subtitles integration
--   v6: Published as part of Tribler 5.3

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
  is_local	       integer DEFAULT 0
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


-- V2: Patch for VoteCast
            
CREATE TABLE VoteCast (
mod_id text,
voter_id text,
vote integer,
time_stamp integer
);

CREATE INDEX mod_id_idx
on VoteCast 
(mod_id);

CREATE INDEX voter_id_idx
on VoteCast 
(voter_id);

CREATE UNIQUE INDEX votecast_idx
ON VoteCast
(mod_id, voter_id);


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



-- v4: Patch for ChannelCast, Search

CREATE TABLE ChannelCast (
publisher_id text,
publisher_name text,
infohash text,
torrenthash text,
torrentname text,
time_stamp integer,
signature text
);

-- WHY NO CONSTRAINT ON PUBLISHER_ID, INFOHASH? 
-- WHY THESE INDEXES?

CREATE INDEX pub_id_idx
on ChannelCast
(publisher_id);

CREATE INDEX pub_name_idx
on ChannelCast
(publisher_name);

CREATE INDEX infohash_ch_idx
on ChannelCast
(infohash);

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

-- v6: Patch for ChannelCast

CREATE UNIQUE INDEX publisher_id_infohash_idx
on ChannelCast
(publisher_id,infohash);


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

INSERT INTO MyInfo VALUES ('version', 7);

COMMIT TRANSACTION init_values;

