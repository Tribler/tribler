from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING

from tribler.core.components.reporter.reported_error import ReportedError
from tribler.core.sentry_reporter.sentry_reporter import SentryStrategy
from tribler.core.sentry_reporter.sentry_scrubber import SentryScrubber
from tribler.gui import gui_sentry_reporter
from tribler.gui.app_manager import AppManager
from tribler.gui.dialogs.feedbackdialog import FeedbackDialog
from tribler.gui.exceptions import CoreError

if TYPE_CHECKING:
    from tribler.gui.tribler_window import TriblerWindow


# fmt: off


class ErrorHandler:
    def __init__(self, tribler_window: TriblerWindow):
        logger_name = self.__class__.__name__
        self._logger = logging.getLogger(logger_name)
        gui_sentry_reporter.ignore_logger(logger_name)

        self.tribler_window = tribler_window
        self.app_manager: AppManager = tribler_window.app_manager

        self._handled_exceptions = set()
        self._tribler_stopped = False

    def gui_error(self, exc_type, exc, tb):
        self._logger.info(f'Processing GUI error: {exc_type}')
        process_manager = self.tribler_window.process_manager
        process_manager.current_process.set_error(exc)

        text = "".join(traceback.format_exception(exc_type, exc, tb))
        self._logger.error(text)

        if self._tribler_stopped:
            self._logger.info('Tribler has been stopped')
            return

        if gui_sentry_reporter.global_strategy == SentryStrategy.SEND_SUPPRESSED:
            self._logger.info(f'GUI error was suppressed and not sent to Sentry: {exc_type.__name__}: {exc}')
            return

        if exc_type in self._handled_exceptions:
            self._logger.info('This exception has been handled already')
            return

        self._handled_exceptions.add(exc_type)

        reported_error = ReportedError(
            type=type(exc_type).__name__,
            text=text,
            event=gui_sentry_reporter.event_from_exception(exc),
        )

        is_core_exception = issubclass(exc_type, CoreError)
        if is_core_exception:
            self._logger.info('It is a subclass of CoreError exception')

            reported_error.last_core_output = self.tribler_window.core_manager.get_last_core_output(quoted=False)
            quoted_output = self.tribler_window.core_manager.get_last_core_output()
            self._logger.info(f'Last Core output:\n{quoted_output}')

            self._stop_tribler(reported_error.text)

        if self.app_manager.quitting_app:
            return

        additional_tags = {
            'source': 'gui',
            'tribler_stopped': self._tribler_stopped
        }

        FeedbackDialog(
            parent=self.tribler_window,
            sentry_reporter=gui_sentry_reporter,
            reported_error=reported_error,
            tribler_version=self.tribler_window.tribler_version,
            start_time=self.tribler_window.start_time,
            stop_application_on_close=self._tribler_stopped,
            additional_tags=additional_tags,
        ).show()

    def core_error(self, reported_error: ReportedError):
        if self._tribler_stopped or reported_error.type in self._handled_exceptions:
            return

        self._handled_exceptions.add(reported_error.type)
        self._logger.info(f'Processing Core error: {reported_error}')
        process_manager = self.tribler_window.process_manager
        process_manager.current_process.set_error(f"Core {reported_error.type}: {reported_error.text}")

        error_text = f'{reported_error.text}\n{reported_error.long_text}'
        self._logger.error(error_text)

        if reported_error.should_stop:
            self._stop_tribler(error_text)

        SentryScrubber.remove_breadcrumbs(reported_error.event)
        gui_sentry_reporter.additional_information.update(reported_error.additional_information)

        additional_tags = {
            'source': 'core',
            'tribler_stopped': self._tribler_stopped
        }

        FeedbackDialog(
            parent=self.tribler_window,
            sentry_reporter=gui_sentry_reporter,
            reported_error=reported_error,
            tribler_version=self.tribler_window.tribler_version,
            start_time=self.tribler_window.start_time,
            stop_application_on_close=self._tribler_stopped,
            additional_tags=additional_tags,
        ).show()

    def _stop_tribler(self, text):
        if self._tribler_stopped:
            return

        self._tribler_stopped = True

        self.tribler_window.tribler_crashed.emit(text)
        self.tribler_window.delete_tray_icon()

        # Stop the download loop
        self.tribler_window.downloads_page.stop_refreshing_downloads()

        # Add info about whether we are stopping Tribler or not
        self.tribler_window.core_manager.stop(quit_app_on_core_finished=False)

        self.tribler_window.setHidden(True)

        if self.tribler_window.debug_window:
            self.tribler_window.debug_window.setHidden(True)
