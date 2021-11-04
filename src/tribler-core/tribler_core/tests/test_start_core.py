from unittest.mock import MagicMock, patch

import pytest

from tribler_core.components.reporter.exception_handler import CoreExceptionHandler
from tribler_core.settings import ErrorHandlingSettings
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
@patch('tribler_core.start_core.TriblerConfig.load')
async def test_start_tribler_core_requires_user_consent(mocked_config):
    # test that CoreExceptionHandler sets `requires_user_consent` in regarding the Tribler's config
    class MockedTriblerConfig(MagicMock):
        error_handling = ErrorHandlingSettings(core_error_reporting_requires_user_consent=False)

    mocked_config.return_value = MockedTriblerConfig()
    start_tribler_core('.', 1, 'key', '.', False)
    assert not CoreExceptionHandler.requires_user_consent
