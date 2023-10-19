CREATE_TABLES = """
    CREATE TABLE IF NOT EXISTS processes (
        rowid INTEGER PRIMARY KEY AUTOINCREMENT,
        row_version INTEGER NOT NULL DEFAULT 0, -- incremented every time the row is updated
        uid INTEGER NOT NULL, -- process UID, an unique 32-bit randomly-generated id value (a GUID is overkill here)
        pid INTEGER NOT NULL, -- process ID. It is not guaranteed for running processes to have an unique PID
        creator_uid INT, -- for a Core process this is the UID of the corresponding GUI process 
        creator_pid INT,  -- for a Core process this is the pid of the corresponding GUI process
        kind TEXT NOT NULL, -- process type, 'core' or 'gui'
        is_primary INT NOT NULL, -- 1 means the process is considered to be the "main" process of the specified kind
        app_version TEXT NOT NULL, -- the Tribler version
        api_port INT,  -- Core API port, for GUI process this is a suggested port that Core can use
        started_at INT NOT NULL, -- unix timestamp of the time when the process was started
        last_alive_at INT NOT NULL, -- unix timestamp of the last time the process updated its row in the database
        is_finished INT,  -- 1 means the process was finished
        is_canceled INT NOT NULL, -- 1 means this process is stopped because another running process is primary 
        exit_code INT, -- for completed process this is the exit code, 0 means successful run without termination
        error_msg TEXT -- a description of an exception that possibly led to the process termination
    )
"""

DELETE_OLD_RECORDS = """
    DELETE FROM processes -- delete all non-primary records that are older than 30 days or not in the 100 last records
    WHERE is_primary = 0  -- never delete current primary processes
      AND (
        last_alive_at < strftime('%s') - (60 * 60 * 24) * 30 -- delete processes that were alive more than 30 days ago
        OR rowid NOT IN ( 
            SELECT rowid FROM processes ORDER BY rowid DESC LIMIT 100 -- only keep last 100 processes  
        )
    )
"""

SELECT_COLUMNS = 'rowid, row_version, uid, pid, creator_uid, creator_pid, kind, is_primary, ' \
                 'app_version, api_port, started_at, last_alive_at, is_finished, is_canceled, exit_code, error_msg'
