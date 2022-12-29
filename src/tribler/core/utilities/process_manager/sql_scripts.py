CREATE_TABLES = """
    CREATE TABLE IF NOT EXISTS processes (
        rowid INTEGER PRIMARY KEY AUTOINCREMENT,
        row_version INTEGER NOT NULL DEFAULT 0, -- incremented every time the row is updated
        pid INTEGER NOT NULL, -- process ID
        kind TEXT NOT NULL, -- process type, 'core' or 'gui'
        "primary" INT NOT NULL, -- 1 means the process is considered to be the "main" process of the specified kind
        canceled INT NOT NULL, -- 1 means that another process is already working as primary, so this process is stopped 
        app_version TEXT NOT NULL, -- the Tribler version
        started_at INT NOT NULL, -- unix timestamp of the time when the process was started
        creator_pid INT,  -- for a Core process this is the pid of the corresponding GUI process
        api_port INT,  -- Core API port, for GUI process this is a suggested port that Core can use
        finished_at INT,  -- unix timestamp of the time when the process was finished
        exit_code INT, -- for completed process this is the exit code, 0 means successful run without termination
        error_msg TEXT -- a description of an exception that possibly led to the process termination
    )
"""

DELETE_OLD_RECORDS = """
    DELETE FROM processes -- delete all non-primary records that are older than 30 days or not in the 100 last records
    WHERE "primary" = 0  -- never delete current primary processes
      AND (
        finished_at < strftime('%s') - (60 * 60 * 24) * 30 -- delete record if a process finished more than 30 days ago
        OR rowid NOT IN ( 
            SELECT rowid FROM processes ORDER BY rowid DESC LIMIT 100 -- only keep last 100 processes  
        )
    )
"""

SELECT_COLUMNS = 'rowid, row_version, pid, kind, "primary", canceled, app_version, ' \
                 'started_at, creator_pid, api_port, finished_at, exit_code, error_msg'
