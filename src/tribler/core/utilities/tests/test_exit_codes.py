from unittest.mock import patch

from tribler.core.utilities.exit_codes import get_error_name


@patch('tribler.core.utilities.exit_codes.check_win_errors', True)
def test_exit_codes():
    assert get_error_name(0) == 'EXITCODE_OK'
    assert get_error_name(1) == 'EXITCODE_APPLICATION_ERROR'
    assert get_error_name(99) == 'EXITCODE_DATABASE_IS_CORRUPTED'
    assert get_error_name(98) == 'EXITCODE_ANOTHER_GUI_PROCESS_IS_RUNNING'
    assert get_error_name(97) == 'EXITCODE_ANOTHER_CORE_PROCESS_IS_RUNNING'

    assert get_error_name(-1073741819) == 'STATUS_ACCESS_VIOLATION'
    assert get_error_name(-1073740940) == 'STATUS_HEAP_CORRUPTION'

    with patch('os.strerror', side_effect=ValueError):
        assert get_error_name(1000000) == 'Unknown error'
