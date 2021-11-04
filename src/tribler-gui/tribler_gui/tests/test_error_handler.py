from unittest.mock import MagicMock, patch

import pytest

from tribler_common.reported_error import ReportedError

from tribler_gui.error_handler import ErrorHandler
from tribler_gui.event_request_manager import CoreConnectTimeoutError

pytestmark = pytest.mark.asyncio


# pylint: disable=redefined-outer-name, protected-access, function-redefined, unused-argument
# fmt: off

@pytest.fixture
def error_handler():
    return ErrorHandler(MagicMock())


@pytest.fixture
def reported_error():
    return ReportedError(type='Exception', text='text', event={})


@patch('tribler_gui.error_handler.FeedbackDialog')
async def test_gui_error_tribler_stopped(mocked_feedback_dialog: MagicMock, error_handler: ErrorHandler):
    # test that while tribler_stopped is True FeedbackDialog is not called
    error_handler._tribler_stopped = True
    error_handler.gui_error()
    mocked_feedback_dialog.assert_not_called()


@patch('tribler_gui.error_handler.FeedbackDialog')
async def test_gui_info_type_in_handled_exceptions(mocked_feedback_dialog: MagicMock, error_handler: ErrorHandler):
    # test that if exception type in _handled_exceptions then FeedbackDialog is not called
    error_handler._handled_exceptions = {AssertionError}
    error_handler.gui_error(AssertionError, None, None)
    mocked_feedback_dialog.assert_not_called()
    assert len(error_handler._handled_exceptions) == 1


@patch('tribler_gui.error_handler.FeedbackDialog')
async def test_gui_is_core_timeout_exception(mocked_feedback_dialog: MagicMock, error_handler: ErrorHandler):
    # test that in case of CoreConnectTimeoutError Tribler should stop it's work
    error_handler._stop_tribler = MagicMock()
    error_handler.gui_error(CoreConnectTimeoutError, None, None)
    error_handler._stop_tribler.assert_called_once()


@patch('tribler_gui.error_handler.FeedbackDialog')
async def test_gui_is_core_timeout_exception(mocked_feedback_dialog: MagicMock, error_handler: ErrorHandler):
    # test that gui_error creates FeedbackDialog
    error_handler.gui_error(Exception, None, None)
    mocked_feedback_dialog.assert_called_once()


@patch('tribler_gui.error_handler.FeedbackDialog')
async def test_core_info_type_in_handled_exceptions(mocked_feedback_dialog: MagicMock, error_handler: ErrorHandler,
                                                    reported_error: ReportedError):
    # test that if exception type in _handled_exceptions then FeedbackDialog is not called
    error_handler._handled_exceptions = {reported_error.type}
    error_handler.core_error(reported_error)
    mocked_feedback_dialog.assert_not_called()
    assert len(error_handler._handled_exceptions) == 1


@patch('tribler_gui.error_handler.FeedbackDialog')
async def test_core_should_stop(mocked_feedback_dialog: MagicMock, error_handler: ErrorHandler,
                                reported_error: ReportedError):
    # test that in case of "should_stop=True", Tribler should stop it's work
    error_handler._stop_tribler = MagicMock()
    reported_error.should_stop = True
    error_handler.core_error(reported_error)
    error_handler._stop_tribler.assert_called_once()


@patch('tribler_gui.error_handler.FeedbackDialog')
async def test_core_error(mocked_feedback_dialog: MagicMock, error_handler: ErrorHandler,
                          reported_error: ReportedError):
    # test that core_error creates FeedbackDialog
    error_handler.core_error(reported_error)
    mocked_feedback_dialog.assert_called_once()
