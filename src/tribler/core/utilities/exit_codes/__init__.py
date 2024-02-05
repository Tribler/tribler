import os

from tribler.core.utilities.exit_codes.tribler_exit_codes import exit_codes

# pylint: disable=import-outside-toplevel


check_win_errors = os.name == 'nt'


def get_error_name(error_code: int) -> str:
    if error_code in exit_codes:
        return exit_codes[error_code]

    if check_win_errors:
        # Local import to avoid loading Windows error codes on non-Windows platforms.
        from tribler.core.utilities.exit_codes.win_error_codes import win_errors

        if error_code in win_errors:
            return win_errors[error_code].name

    try:
        return os.strerror(error_code)
    except ValueError:
        # On platforms where strerror() returns NULL when given an unknown error number, ValueError is raised.
        return 'Unknown error'
