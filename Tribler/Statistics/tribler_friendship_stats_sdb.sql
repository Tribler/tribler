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
  modified_on		   numeric
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

COMMIT TRANSACTION init_values;