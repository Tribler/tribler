CREATE_TABLES = """
    CREATE TABLE IF NOT EXISTS processes (
        rowid INTEGER PRIMARY KEY AUTOINCREMENT,
        row_version INTEGER NOT NULL DEFAULT 0,
        pid INTEGER NOT NULL,
        kind TEXT NOT NULL,
        "primary" INT NOT NULL,
        canceled INT NOT NULL,
        app_version TEXT NOT NULL,
        started_at INT NOT NULL,
        creator_pid INT,
        api_port INT,
        finished_at INT,
        exit_code INT,
        error_msg TEXT
    )
"""

DELETE_OLD_RECORDS = """
    DELETE FROM processes
    WHERE "primary" = 0  -- never delete current primary processes
      AND (
        finished_at < strftime('%s') - (60 * 60 * 24) * 30 -- delete record if a process finished more than 30 days ago
        OR rowid NOT IN ( 
            SELECT rowid FROM processes ORDER BY rowid DESC LIMIT 100 -- only keep last 100 processes  
        )
    )
"""
