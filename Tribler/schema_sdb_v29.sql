BEGIN TRANSACTION create_table;

----------------------------------------

CREATE TABLE MyInfo (
  entry  PRIMARY KEY,
  value  text
);

----------------------------------------

CREATE TABLE MyPreference (
  torrent_id     integer PRIMARY KEY NOT NULL,
  destination_path text NOT NULL,
  creation_time  integer NOT NULL
);

----------------------------------------

CREATE TABLE Peer (
  peer_id    integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  permid     text NOT NULL,
  name       text,
  thumbnail  text
);

CREATE UNIQUE INDEX permid_idx
  ON Peer
  (permid);

----------------------------------------

CREATE TABLE Torrent (
  torrent_id       integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  infohash		   text NOT NULL,
  name             text,
  length           integer,
  creation_date    integer,
  num_files        integer,
  insert_time      numeric,
  secret           integer,
  relevance        numeric DEFAULT 0,
  category         text,
  status           text DEFAULT 'unknown',
  num_seeders      integer,
  num_leechers     integer,
  comment          text,
  dispersy_id      integer,
  is_collected     integer DEFAULT 0,
  last_tracker_check    integer DEFAULT 0,
  tracker_check_retries integer DEFAULT 0,
  next_tracker_check    integer DEFAULT 0
);

CREATE UNIQUE INDEX infohash_idx
  ON Torrent
  (infohash);

----------------------------------------

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

----------------------------------------

CREATE VIEW CollectedTorrent AS SELECT * FROM Torrent WHERE is_collected == 1;

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
  type                  text            NOT NULL,
  value                 text            NOT NULL,
  prev_modification     integer,
  prev_global_time      integer,
  time_stamp            integer         NOT NULL,
  inserted              integer         DEFAULT (strftime('%s','now')),
  deleted_at            integer,
  UNIQUE (dispersy_id)
);
CREATE VIEW ChannelMetaData AS SELECT * FROM _ChannelMetaData WHERE deleted_at IS NULL;

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

CREATE VIRTUAL TABLE FullTextIndex USING fts4(swarmname, filenames, fileextensions);

-------------------------------------

COMMIT TRANSACTION create_table;

----------------------------------------

BEGIN TRANSACTION init_values;

INSERT INTO MyInfo VALUES ('version', 28);

INSERT INTO TrackerInfo (tracker) VALUES ('no-DHT');
INSERT INTO TrackerInfo (tracker) VALUES ('DHT');

COMMIT TRANSACTION init_values;
