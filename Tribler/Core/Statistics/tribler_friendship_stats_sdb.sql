-- Tribler Friendship Statistics Database

BEGIN TRANSACTION create_table;

----------------------------------------

CREATE TABLE FriendshipStatistics (
  source_permid        text NOT NULL,
  target_permid        text NOT NULL,
  isForwarder          integer DEFAULT 0,
  request_time         numeric,
  response_time        numeric,
  no_of_attempts       integer DEFAULT 0,
  no_of_helpers		   integer DEFAULT 0,
  modified_on		   numeric,
  crawled_permid       text NOT NULL DEFAULT client
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

-- Version 1: Initial version, published in Tribler 4.5.0
-- Version 2: Added crawled_permid to FriendshipStatistics table.
INSERT INTO MyInfo VALUES ('version', 2);

COMMIT TRANSACTION init_values;