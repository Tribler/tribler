
EXITCODE_OK = 0  # Normal exit code.
EXITCODE_APPLICATION_ERROR = 1  # Generic error code for application errors.

# Valid range for custom errors is 1..127
EXITCODE_DATABASE_IS_CORRUPTED = 99  # If the Core process finishes with this error, the GUI process restarts it.
EXITCODE_ANOTHER_GUI_PROCESS_IS_RUNNING = 98  # A normal situation when a user double-clicks on the torrent file.
EXITCODE_ANOTHER_CORE_PROCESS_IS_RUNNING = 97  # Should not happen if process locking is working correctly.


exit_codes = {}


for name, value in list(globals().items()):
    if name.startswith('EXITCODE_'):
        exit_codes[value] = name
