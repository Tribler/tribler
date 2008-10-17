-- Tribler Seeding Statistics Database

BEGIN TRANSACTION create_table;

----------------------------------------

CREATE TABLE SeedingStats (
  timestamp  	real,
  permID		text,
  info_hash    	text,
  seeding_time	real,
  reputation	real,
  crawled      	integer
);

----------------------------------------

CREATE TABLE SeedingStatsSettings (
  version				integer PRIMARY KEY,
  crawling_interval  	integer,
  crawling_enabled		integer
);

----------------------------------------

CREATE TABLE MyInfo (
  entry  PRIMARY KEY,
  value  text
);

----------------------------------------
COMMIT TRANSACTION create_table;

----------------------------------------

BEGIN TRANSACTION init_values;

INSERT INTO MyInfo VALUES ('version', 1);
INSERT INTO SeedingStatsSettings VALUES (1, 1800, 1);

COMMIT TRANSACTION init_values;
