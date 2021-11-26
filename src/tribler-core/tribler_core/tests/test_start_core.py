from unittest.mock import MagicMock, patch

from tribler_core.start_core import start_tribler_core
from tribler_core.utilities.path_util import Path

# pylint: disable=
# fmt: off


@patch('tribler_common.logger.load_logger_config', new=MagicMock())
@patch('tribler_core.start_core.set_process_priority', new=MagicMock())
@patch('tribler_core.start_core.check_and_enable_code_tracing', new=MagicMock())
@patch('asyncio.get_event_loop', new=MagicMock())
@patch('tribler_core.start_core.TriblerConfig.load', new=MagicMock())
@patch('tribler_core.start_core.core_session')
def test_start_tribler_core_no_exceptions(mocked_core_session):
    # test that base logic of tribler core runs without exceptions
    start_tribler_core(1, 'key', Path('.'), False)
    mocked_core_session.assert_called_once()
