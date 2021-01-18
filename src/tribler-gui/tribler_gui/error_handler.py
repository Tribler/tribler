import logging
import os
import traceback

from tribler_common.sentry_reporter.sentry_reporter import SentryReporter

from tribler_gui.dialogs.feedbackdialog import FeedbackDialog
from tribler_gui.event_request_manager import CoreConnectTimeoutError


class ErrorHandler:
    def __init__(self, tribler_windows):
        logger_name = self.__class__.__name__
        self._logger = logging.getLogger(logger_name)
        SentryReporter.ignore_logger(logger_name)

        self.tribler_windows = tribler_windows

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

        if info_type is CoreConnectTimeoutError:
            text = text + self.tribler_windows.core_manager.core_traceback
            self._stop_tribler(text)

        self._logger.error(text)

        FeedbackDialog(
            self.tribler_windows,
            text,
            self.tribler_windows.tribler_version,
            self.tribler_windows.start_time,
            SentryReporter.event_from_exception(info_error),
            True,
            self._tribler_stopped
        ).show()

    def core_error(self, text, core_event):
        if self._tribler_stopped:
            return

        self._logger.error(text)

        self._stop_tribler(text)

        FeedbackDialog(
            self.tribler_windows,
            text,
            self.tribler_windows.tribler_version,
            self.tribler_windows.start_time,
            core_event['sentry_event'],
            core_event['error_reporting_requires_user_consent'],
            self._tribler_stopped
        ).show()

    def _stop_tribler(self, text):
        if self._tribler_stopped:
            return

        self._tribler_stopped = True

        self.tribler_windows.tribler_crashed.emit(text)
        self.tribler_windows.delete_tray_icon()

        # Stop the download loop
        self.tribler_windows.downloads_page.stop_loading_downloads()

        # Add info about whether we are stopping Tribler or not
        os.environ['TRIBLER_SHUTTING_DOWN'] = str(self.tribler_windows.core_manager.shutting_down)
        if not self.tribler_windows.core_manager.shutting_down:
            self.tribler_windows.core_manager.stop(stop_app_on_shutdown=False)

        self.tribler_windows.setHidden(True)

        if self.tribler_windows.debug_window:
            self.tribler_windows.debug_window.setHidden(True)
