from unittest.mock import MagicMock, patch

from tribler.core.start_core import run_tribler_core_session
from tribler.core.utilities.path_util import Path


@patch('tribler.core.logger.logger.load_logger_config', new=MagicMock())
@patch('tribler.core.start_core.set_process_priority', new=MagicMock())
@patch('tribler.core.start_core.check_and_enable_code_tracing', new=MagicMock())
@patch('asyncio.get_event_loop', new=MagicMock())
@patch('tribler.core.start_core.TriblerConfig.load', new=MagicMock())
@patch('tribler.core.start_core.core_session')
def test_start_tribler_core_no_exceptions(mocked_core_session):
    # test that base logic of tribler core runs without exceptions
    run_tribler_core_session(1, 'key', Path('.'), False)
    mocked_core_session.assert_called_once()
