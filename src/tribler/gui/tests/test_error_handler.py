from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from tribler.core.components.reporter.reported_error import ReportedError
from tribler.core.sentry_reporter.sentry_reporter import SentryReporter, SentryStrategy
from tribler.gui.error_handler import ErrorHandler
from tribler.gui.exceptions import CoreConnectTimeoutError, CoreCrashedError


# pylint: disable=redefined-outer-name, protected-access, function-redefined, unused-argument

@pytest.fixture
def error_handler():
    handler = ErrorHandler(MagicMock())
    handler.app_manager.quitting_app = False
    return handler


@pytest.fixture
def reported_error():
    return ReportedError(type='Exception', text='text', event={})


class TestError(Exception):
    pass


@patch('tribler.gui.error_handler.FeedbackDialog')
def test_gui_error_tribler_stopped(mocked_feedback_dialog: MagicMock, error_handler: ErrorHandler):
    # test that while tribler_stopped is True FeedbackDialog is not called
    error_handler._tribler_core_stopped = True
    error_handler.gui_error(TestError, TestError("error text"), None)
    mocked_feedback_dialog.assert_not_called()


@patch('tribler.gui.error_handler.FeedbackDialog')
@patch.object(SentryReporter, 'global_strategy', create=True,
              new=PropertyMock(return_value=SentryStrategy.SEND_SUPPRESSED))
def test_gui_error_suppressed(mocked_feedback_dialog: MagicMock, error_handler: ErrorHandler):
    error_handler.gui_error(TestError, TestError('error_text'), None)
    mocked_feedback_dialog.assert_not_called()
    assert not error_handler._handled_exceptions


@patch('tribler.gui.error_handler.FeedbackDialog')
def test_gui_info_type_in_handled_exceptions(mocked_feedback_dialog: MagicMock, error_handler: ErrorHandler):
    # test that if exception type in _handled_exceptions then FeedbackDialog is not called
    error_handler._handled_exceptions = {TestError}
    error_handler.gui_error(TestError, TestError("error text"), None)
    mocked_feedback_dialog.assert_not_called()
    assert len(error_handler._handled_exceptions) == 1


@patch('tribler.gui.error_handler.FeedbackDialog')
@patch.object(ErrorHandler, '_stop_tribler')
@patch.object(ErrorHandler, '_restart_tribler_core')
def test_gui_core_connect_timeout_error(mocked_restart_tribler, mocked_stop_tribler,
                                        mocked_feedback_dialog: MagicMock,
                                        error_handler: ErrorHandler):
    # test that in case of CoreConnectTimeoutError Tribler should stop it's work
    error_handler.gui_error(CoreConnectTimeoutError, None, None)

    mocked_feedback_dialog.assert_called_once()
    mocked_stop_tribler.assert_not_called()
    mocked_restart_tribler.assert_called_once()


@patch('tribler.gui.error_handler.FeedbackDialog')
@patch.object(ErrorHandler, '_stop_tribler')
@patch.object(ErrorHandler, '_restart_tribler_core')
def test_gui_core_crashed_error(mocked_restart_tribler: MagicMock, mocked_stop_tribler: MagicMock,
                                mocked_feedback_dialog: MagicMock,
                                error_handler: ErrorHandler):

    # test that in case of CoreRuntimeError Tribler should stop it's work
    error_handler.gui_error(CoreCrashedError, None, None)

    mocked_feedback_dialog.assert_called_once()
    mocked_stop_tribler.assert_not_called()
    mocked_restart_tribler.assert_called_once()


@patch('tribler.gui.error_handler.FeedbackDialog')
@patch.object(ErrorHandler, '_stop_tribler')
def test_gui_is_not_core_exception(mocked_stop_tribler: MagicMock, mocked_feedback_dialog: MagicMock,
                                   error_handler: ErrorHandler):
    # test that gui_error creates FeedbackDialog without stopping the Tribler's work
    error_handler.gui_error(Exception, None, None)

    mocked_feedback_dialog.assert_called_once()
    mocked_stop_tribler.assert_not_called()


@patch('tribler.gui.error_handler.FeedbackDialog')
def test_core_info_type_in_handled_exceptions(mocked_feedback_dialog: MagicMock, error_handler: ErrorHandler,
                                              reported_error: ReportedError):
    # test that if exception type in _handled_exceptions then FeedbackDialog is not called
    error_handler._handled_exceptions = {reported_error.type}
    error_handler.core_error(reported_error)
    mocked_feedback_dialog.assert_not_called()
    assert len(error_handler._handled_exceptions) == 1


@patch('tribler.gui.error_handler.FeedbackDialog')
def test_core_should_stop(mocked_feedback_dialog: MagicMock, error_handler: ErrorHandler,
                          reported_error: ReportedError):
    # test that in case of "should_stop=True", Tribler should stop it's work
    error_handler._stop_tribler = MagicMock()
    reported_error.should_stop = True
    error_handler.core_error(reported_error)
    error_handler._stop_tribler.assert_called_once()


@patch('tribler.gui.error_handler.FeedbackDialog')
def test_core_error(mocked_feedback_dialog: MagicMock, error_handler: ErrorHandler,
                    reported_error: ReportedError):
    # test that core_error creates FeedbackDialog
    error_handler.core_error(reported_error)
    mocked_feedback_dialog.assert_called_once()
