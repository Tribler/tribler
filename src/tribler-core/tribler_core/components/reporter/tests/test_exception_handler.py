from socket import gaierror
from unittest.mock import MagicMock, patch

import pytest

from tribler_common.sentry_reporter import sentry_reporter
from tribler_common.sentry_reporter.sentry_reporter import SentryReporter

from tribler_core.components.reporter.exception_handler import CoreExceptionHandler

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access
# fmt: off

def raise_error(error):  # pylint: disable=inconsistent-return-statements
    try:
        raise error
    except error.__class__ as e:
        return e


async def test_is_ignored():
    # test that CoreExceptionHandler ignores specific exceptions

    # by type
    assert CoreExceptionHandler._is_ignored(OSError(113, 'Any'))
    assert CoreExceptionHandler._is_ignored(ConnectionResetError(10054, 'Any'))

    # by class
    assert CoreExceptionHandler._is_ignored(gaierror('Any'))

    # by class and substring
    assert CoreExceptionHandler._is_ignored(RuntimeError('Message that contains invalid info-hash'))


async def test_is_not_ignored():
    # test that CoreExceptionHandler do not ignore exceptions out of
    # IGNORED_ERRORS_BY_CODE and IGNORED_ERRORS_BY_SUBSTRING
    assert not CoreExceptionHandler._is_ignored(OSError(1, 'Any'))
    assert not CoreExceptionHandler._is_ignored(RuntimeError('Any'))
    assert not CoreExceptionHandler._is_ignored(AttributeError())


async def test_create_exception_from():
    # test that CoreExceptionHandler can create an Exception from a string
    assert isinstance(CoreExceptionHandler._create_exception_from('Any'), Exception)


async def test_get_long_text_from():
    # test that CoreExceptionHandler can generate stacktrace from an Exception
    error = raise_error(AttributeError('Any'))
    actual_string = CoreExceptionHandler._get_long_text_from(error)
    assert 'raise_error' in actual_string


@patch(f'{sentry_reporter.__name__}.{SentryReporter.__name__}.{SentryReporter.event_from_exception.__name__}',
       new=MagicMock(return_value={'sentry': 'event'}))
async def test_unhandled_error_observer_exception():
    # test that unhandled exception, represented by Exception, reported to the GUI
    context = {'exception': raise_error(AttributeError('Any')), 'Any key': 'Any value'}
    CoreExceptionHandler.report_callback = MagicMock()
    CoreExceptionHandler.unhandled_error_observer(None, context)
    CoreExceptionHandler.report_callback.assert_called()

    # get the argument that has been passed to the report_callback
    reported_error = CoreExceptionHandler.report_callback.call_args_list[-1][0][0]
    assert reported_error.type == 'AttributeError'
    assert reported_error.text == 'Any'
    assert 'raise_error' in reported_error.long_text
    assert reported_error.event == {'sentry': 'event'}
    assert reported_error.context == "{'Any key': 'Any value'}"
    assert reported_error.should_stop
    assert reported_error.requires_user_consent


async def test_unhandled_error_observer_only_message():
    # test that unhandled exception, represented by message, reported to the GUI
    context = {'message': 'Any'}
    CoreExceptionHandler.report_callback = MagicMock()
    CoreExceptionHandler.unhandled_error_observer(None, context)
    CoreExceptionHandler.report_callback.assert_called()

    # get the argument that has been passed to the report_callback
    reported_error = CoreExceptionHandler.report_callback.call_args_list[-1][0][0]
    assert reported_error.type == 'Exception'
    assert reported_error.text == 'Received error without exception: Any'
    assert reported_error.long_text == 'Exception: Received error without exception: Any\n'
    assert not reported_error.event
    assert reported_error.context == '{}'
    assert reported_error.should_stop
    assert reported_error.requires_user_consent


async def test_unhandled_error_observer_ignored():
    # test that exception from list IGNORED_ERRORS_BY_CODE never sends to the GUI
    context = {'exception': OSError(113, '')}
    CoreExceptionHandler.report_callback = MagicMock()
    with patch.object(CoreExceptionHandler._logger, 'warning') as mocked_warning:
        CoreExceptionHandler.unhandled_error_observer(None, context)
        mocked_warning.assert_called_once()
    CoreExceptionHandler.report_callback.assert_not_called()
