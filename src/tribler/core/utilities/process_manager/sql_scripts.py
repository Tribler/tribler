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
        shutdown_request_pid INT,
        shutdown_requested_at INT, 
        finished_at INT,
        exit_code INT,
        error_msg TEXT
    )
"""
