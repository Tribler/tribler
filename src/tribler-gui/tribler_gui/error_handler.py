import logging
import os
import traceback

from tribler_common.reported_error import ReportedError
from tribler_common.sentry_reporter.sentry_reporter import SentryReporter

from tribler_gui.dialogs.feedbackdialog import FeedbackDialog
from tribler_gui.event_request_manager import CoreConnectTimeoutError

# fmt: off

class ErrorHandler:
    def __init__(self, tribler_window):
        logger_name = self.__class__.__name__
        self._logger = logging.getLogger(logger_name)
        SentryReporter.ignore_logger(logger_name)

        self.tribler_window = tribler_window

        self._handled_exceptions = set()
        self._tribler_stopped = False

    def gui_error(self, *exc_info):
        if self._tribler_stopped:
            return

        info_type, info_error, tb = exc_info
        if info_type in self._handled_exceptions:
            return
        self._handled_exceptions.add(info_type)

        text = "".join(traceback.format_exception(info_type, info_error, tb))

        is_core_timeout_exception = info_type is CoreConnectTimeoutError
        if is_core_timeout_exception:
            text = text + self.tribler_window.core_manager.core_traceback
            self._stop_tribler(text)

        self._logger.error(text)
        reported_error = ReportedError(
            type=type(info_type).__name__,
            text=text,
            event=SentryReporter.event_from_exception(info_error),
            requires_user_consent=True
        )

        FeedbackDialog(
            parent=self.tribler_window,
            reported_error=reported_error,
            tribler_version=self.tribler_window.tribler_version,
            start_time=self.tribler_window.start_time,
            stop_application_on_close=self._tribler_stopped,
            additional_tags={'source': 'gui'},
            retrieve_error_message_from_stacktrace=is_core_timeout_exception
        ).show()

    def core_error(self, reported_error: ReportedError):
        if self._tribler_stopped or reported_error.type in self._handled_exceptions:
            return

        error_text = f'{reported_error.text}\n{reported_error.long_text}'
        self._logger.error(error_text)

        if reported_error.should_stop:
            self._stop_tribler(error_text)

        FeedbackDialog(
            parent=self.tribler_window,
            reported_error=reported_error,
            tribler_version=self.tribler_window.tribler_version,
            start_time=self.tribler_window.start_time,
            stop_application_on_close=self._tribler_stopped,
            additional_tags={'source': 'core'}
        ).show()

    def _stop_tribler(self, text):
        if self._tribler_stopped:
            return

        self._tribler_stopped = True

        self.tribler_window.tribler_crashed.emit(text)
        self.tribler_window.delete_tray_icon()

        # Stop the download loop
        self.tribler_window.downloads_page.stop_loading_downloads()

        # Add info about whether we are stopping Tribler or not
        os.environ['TRIBLER_SHUTTING_DOWN'] = str(self.tribler_window.core_manager.shutting_down).upper()
        if not self.tribler_window.core_manager.shutting_down:
            self.tribler_window.core_manager.stop(stop_app_on_shutdown=False)

        self.tribler_window.setHidden(True)

        if self.tribler_window.debug_window:
            self.tribler_window.debug_window.setHidden(True)
