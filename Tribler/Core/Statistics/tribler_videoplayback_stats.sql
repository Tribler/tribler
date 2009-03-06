-- Tribler Video Playback Statistics Database

BEGIN TRANSACTION create_table;

----------------------------------------

CREATE TABLE playback_info (
  key                   text PRIMARY KEY NOT NULL,
  timestamp             real NOT NULL,
  piece_size            integer,
  num_pieces            integer,
  bitrate               integer,
  nat                   text
);

CREATE INDEX playback_info_idx 
  ON playback_info (timestamp);

----------------------------------------

CREATE TABLE playback_event (
  key                   text NOT NULL,
  timestamp             real NOT NULL,
  origin                text NOT NULL,
  event                 text NOT NULL
);  

CREATE INDEX playback_event_idx 
  ON playback_event (key, timestamp);

----------------------------------------

CREATE TABLE MyInfo (
  entry  PRIMARY KEY,
  value  text
);

----------------------------------------

COMMIT TRANSACTION create_table;

----------------------------------------

BEGIN TRANSACTION init_values;

-- Version 1: Initial version, published in Tribler 5.0.0
INSERT INTO MyInfo VALUES ('version', 1);

COMMIT TRANSACTION init_values;
