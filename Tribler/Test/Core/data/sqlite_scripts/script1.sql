BEGIN TRANSACTION create_table;

----------------------------------------

CREATE TABLE MyPreference (
  torrent_id     integer PRIMARY KEY NOT NULL,
  destination_path text NOT NULL,
  creation_time  integer NOT NULL
);

-------------------------------------

COMMIT TRANSACTION create_table;
