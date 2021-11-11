from unittest.mock import MagicMock, patch

import pytest

from tribler_core.start_core import start_tribler_core

pytestmark = pytest.mark.asyncio


# pylint: disable=
# fmt: off

class MockedProcessChecker(MagicMock):
    already_running = False


@patch('tribler_core.load_logger_config', new=MagicMock())
@patch('tribler_core.start_core.VersionHistory', new=MagicMock())
@patch('tribler_core.start_core.set_process_priority', new=MagicMock())
@patch('tribler_core.start_core.check_and_enable_code_tracing', new=MagicMock())
@patch('tribler_core.start_core.core_session', new=MagicMock())
@patch('tribler_core.start_core.ProcessChecker', new=MockedProcessChecker())
@patch('asyncio.get_event_loop', new=MagicMock())
@patch('tribler_core.start_core.TriblerConfig.load', new=MagicMock())
@patch.object(MockedProcessChecker, 'remove_lock_file', create=True)
async def test_start_tribler_core_no_exceptions(mocked_remove_lock_file):
    # test that base logic of tribler core runs without exceptions
    start_tribler_core('.', 1, 'key', '.', False)
    mocked_remove_lock_file.assert_called_once()
