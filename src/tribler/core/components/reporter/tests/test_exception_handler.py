import dataclasses
from dataclasses import asdict
from socket import gaierror
from unittest.mock import MagicMock, Mock, patch

import pytest

from tribler.core.components.reporter.exception_handler import CoreExceptionHandler
from tribler.core.components.reporter.reported_error import ReportedError
from tribler.core.sentry_reporter import sentry_reporter
from tribler.core.sentry_reporter.sentry_reporter import SentryReporter
from tribler.core.utilities.db_corruption_handling.base import DatabaseIsCorrupted


# pylint: disable=protected-access, redefined-outer-name
# fmt: off

@pytest.fixture
def exception_handler():
    return CoreExceptionHandler()


def raise_error(error):  # pylint: disable=inconsistent-return-statements
    try:
        raise error
    except error.__class__ as e:
        return e


def test_is_ignored(exception_handler):
    # test that CoreExceptionHandler ignores specific exceptions

    # by exception type
    assert exception_handler._is_ignored(gaierror())
    assert exception_handler._is_ignored(ConnectionResetError())

    # by exception type and error code
    assert exception_handler._is_ignored(OSError(113, 'Arbitrary error message'))
    assert exception_handler._is_ignored(OSError(0, 'Arbitrary error message'))

    # by exception type and regex
    assert exception_handler._is_ignored(RuntimeError('A message with the following substring: invalid info-hash'))
    assert not exception_handler._is_ignored(RuntimeError('Another message without a substring'))


def test_is_not_ignored(exception_handler):
    # test that CoreExceptionHandler do not ignore exceptions out of
    # IGNORED_ERRORS_BY_TYPE, IGNORED_ERRORS_BY_CODE and IGNORED_ERRORS_BY_SUBSTRING

    # AttributeError is not in the IGNORED_ERRORS_BY_TYPE, IGNORED_ERRORS_BY_CODE or IGNORED_ERRORS_BY_SUBSTRING
    assert not exception_handler._is_ignored(AttributeError())

    # OSError with code 1 is not in the IGNORED_ERRORS_BY_CODE
    assert not exception_handler._is_ignored(OSError(1, 'Arbitrary error message'))

    # RuntimeError is in IGNORED_ERRORS_BY_REGEX, but the message does not contain "invalid info-hash" substring
    assert not exception_handler._is_ignored(RuntimeError('Arbitrary error message'))


def test_create_exception_from(exception_handler):
    # test that CoreExceptionHandler can create an Exception from a string
    assert isinstance(exception_handler._create_exception_from('Any'), Exception)


def test_get_long_text_from(exception_handler):
    # test that CoreExceptionHandler can generate stacktrace from an Exception
    error = raise_error(AttributeError('Any'))
    actual_string = exception_handler._get_long_text_from(error)
    assert 'raise_error' in actual_string


@patch(f'{sentry_reporter.__name__}.{SentryReporter.__name__}.{SentryReporter.event_from_exception.__name__}',
       new=MagicMock(return_value={'sentry': 'event'}))
def test_unhandled_error_observer_exception(exception_handler):
    # test that unhandled exception, represented by Exception, reported to the GUI
    context = {'exception': raise_error(AttributeError('Any')), 'Any key': 'Any value'}
    exception_handler.report_callback = MagicMock()
    exception_handler.unhandled_error_observer(None, context)
    exception_handler.report_callback.assert_called()

    # get the argument that has been passed to the report_callback
    reported_error = exception_handler.report_callback.call_args_list[-1][0][0]
    assert reported_error.type == 'AttributeError'
    assert reported_error.text == 'Any'
    assert 'raise_error' in reported_error.long_text
    assert reported_error.event == {'sentry': 'event'}
    assert reported_error.context == "{'Any key': 'Any value'}"
    assert reported_error.should_stop


@patch('tribler.core.components.reporter.exception_handler.get_global_process_manager')
def test_unhandled_error_observer_database_corrupted(get_global_process_manager, exception_handler):
    # test that database corruption exception reported to the GUI
    exception = DatabaseIsCorrupted('db_path_string')
    exception_handler.report_callback = MagicMock()
    exception_handler.unhandled_error_observer(None, {'exception': exception})

    get_global_process_manager().sys_exit.assert_called_once_with(99, exception)
    exception_handler.report_callback.assert_not_called()


def test_unhandled_error_observer_only_message(exception_handler):
    # test that unhandled exception, represented by message, reported to the GUI
    context = {'message': 'Any'}
    exception_handler.report_callback = MagicMock()
    exception_handler.unhandled_error_observer(None, context)
    exception_handler.report_callback.assert_called()

    # get the argument that has been passed to the report_callback
    reported_error = exception_handler.report_callback.call_args_list[-1][0][0]
    assert reported_error.type == 'Exception'
    assert reported_error.text == 'Received error without exception: Any'
    assert reported_error.long_text == 'Exception: Received error without exception: Any\n'
    assert not reported_error.event
    assert reported_error.context == '{}'
    assert reported_error.should_stop
    assert reported_error.additional_information == {}


def test_unhandled_error_observer_store_unreported_error(exception_handler):
    context = {'message': 'Any'}
    exception_handler.unhandled_error_observer(None, context)
    assert exception_handler.unreported_error


def test_unhandled_error_observer_false_should_stop(exception_handler):
    # Test passing negative value for should_stop flag through the context dict
    context = {'message': 'Any', 'should_stop': False}
    exception_handler.unhandled_error_observer(None, context)
    assert exception_handler.unreported_error.should_stop is False


def test_unhandled_error_observer_additional_information(exception_handler):
    # test that additional information is passed to the `report_callback`
    exception_handler.report_callback = MagicMock()
    exception_handler.sentry_reporter.additional_information['a'] = 1
    exception_handler.unhandled_error_observer(None, {})

    reported_error = exception_handler.report_callback.call_args_list[-1][0][0]

    assert reported_error.additional_information == {'a': 1}
    assert asdict(reported_error)  # default dict could produce TypeError: first argument must be callable or None


def test_unhandled_error_observer_ignored(exception_handler):
    # test that exception from list IGNORED_ERRORS_BY_CODE never sends to the GUI
    context = {'exception': OSError(113, '')}
    exception_handler.report_callback = MagicMock()
    with patch.object(exception_handler.logger, 'warning') as mocked_warning:
        exception_handler.unhandled_error_observer(None, context)
        mocked_warning.assert_called_once()
    exception_handler.report_callback.assert_not_called()


@patch.object(SentryReporter, 'ignore_logger', new=Mock(side_effect=ValueError))
@patch.object(SentryReporter, 'capture_exception')
def test_unhandled_error_observer_inner_exception(mocked_capture_exception: Mock,
                                                  exception_handler: CoreExceptionHandler):
    with pytest.raises(ValueError):
        exception_handler.unhandled_error_observer({}, {})
    mocked_capture_exception.assert_called_once()


def test_get_file_path_with_no_crash_dir(exception_handler):
    """
    Test that get_file_path returns None if crash_dir is not set.
    """
    reported_error = ReportedError('type', 'text', {})
    assert exception_handler.crash_dir is None
    path = exception_handler.get_file_path(reported_error)
    assert path is None


def test_get_file_path(exception_handler, tmp_path):
    """
    Test that get_file_path returns the correct path.
    """
    reported_error = ReportedError('type', 'text', {})
    exception_handler.crash_dir = tmp_path
    path = exception_handler.get_file_path(reported_error)

    assert exception_handler.crash_dir.exists()
    assert path == tmp_path / reported_error.get_filename()


def test_save_to_file(exception_handler, tmp_path):
    """
    Test that save_to_file saves the correct data to the correct file.
    """
    reported_error = ReportedError('type', 'text', {})
    exception_handler.crash_dir = tmp_path

    exception_handler.save_to_file(reported_error)

    path = exception_handler.get_file_path(reported_error)
    assert path.exists()
    assert path.read_text() == reported_error.serialize(should_stop=False)


def test_delete_saved_file(exception_handler, tmp_path):
    """
    Test that delete_saved_file deletes the correct file.
    """
    reported_error = ReportedError('type', 'text', {})
    exception_handler.crash_dir = tmp_path

    exception_handler.save_to_file(reported_error)

    path = exception_handler.get_file_path(reported_error)
    assert path.exists()

    exception_handler.delete_saved_file(reported_error)

    assert not path.exists()


def test_get_saved_errors(exception_handler, tmp_path):
    """
    Test that get_saved_errors returns the correct list of errors.
    """
    reported_error = ReportedError('type', 'text', {})
    exception_handler.crash_dir = tmp_path

    exception_handler.save_to_file(reported_error)
    file_path = exception_handler.get_file_path(reported_error)

    saved_errors = exception_handler.get_saved_errors()
    assert saved_errors == [(file_path, dataclasses.replace(reported_error, should_stop=False))]


def test_get_saved_errors_multiple_files(exception_handler, tmp_path):
    """
    Test that get_saved_errors returns the correct list of errors.
    """
    exception_handler.crash_dir = tmp_path

    reported_error = ReportedError('type', 'text', {})
    reported_error_file_path = exception_handler.get_file_path(reported_error)

    reported_error2 = ReportedError('type2', 'text2', {})
    reported_error2_file_path = exception_handler.get_file_path(reported_error2)

    exception_handler.save_to_file(reported_error)
    exception_handler.save_to_file(reported_error2)

    saved_errors = exception_handler.get_saved_errors()
    assert (reported_error_file_path, reported_error.serialized_copy()) in saved_errors
    assert (reported_error2_file_path, reported_error2.serialized_copy()) in saved_errors
