-- Tribler Video Playback Statistics Database

BEGIN TRANSACTION create_table;

----------------------------------------

CREATE TABLE playback_event (
  key                   text NOT NULL,
  timestamp             real NOT NULL,
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
-- Version 2: Simplified the database. Now everything is an event. Published in Tribler 5.1.0
INSERT INTO MyInfo VALUES ('version', 2);

COMMIT TRANSACTION init_values;
