from unittest.mock import patch

import pytest

from tribler_core.check_os import error_and_exit

pytestmark = pytest.mark.asyncio


# fmt: off
@patch('sys.exit')
@patch('tribler_core.check_os.show_system_popup')
async def test_error_and_exit(mocked_show_system_popup, mocked_sys_exit):
    error_and_exit('title', 'text')
    mocked_show_system_popup.assert_called_once_with('title', 'text')
    mocked_sys_exit.assert_called_once_with(1)
