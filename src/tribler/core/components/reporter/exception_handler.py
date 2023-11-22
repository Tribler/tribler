import dataclasses
import errno
import json
import logging
import os
import re
import sys
from io import StringIO
from json import JSONDecodeError
from socket import gaierror
from traceback import print_exception
from typing import Callable, Dict, Optional, Set, Tuple, Type

from tribler.core.components.exceptions import ComponentStartupException
from tribler.core.components.reporter.reported_error import ReportedError
from tribler.core.sentry_reporter.sentry_reporter import SentryReporter
from tribler.core.utilities.db_corruption_handling.base import DatabaseIsCorrupted
from tribler.core.utilities.exit_codes.tribler_exit_codes import EXITCODE_DATABASE_IS_CORRUPTED
from tribler.core.utilities.process_manager import get_global_process_manager

# There are some errors that we are ignoring.

IGNORED_ERRORS_BY_CLASS: Tuple[Type[Exception], ...] = (
    ConnectionResetError,  # Connection forcibly closed by the remote host.
    gaierror,  # all gaierror is ignored
)

IGNORED_ERRORS_BY_CODE: Set[Tuple[Type[Exception], int]] = {
    (OSError, 113),  # No route to host is non-critical since Tribler can still function when a request fails.
    # Socket block: this sometimes occurs on Windows and is non-critical.
    (BlockingIOError, 10035 if sys.platform == 'win32' else errno.EWOULDBLOCK),
    (OSError, 51),  # Could not send data: network is unreachable.
    (ConnectionAbortedError, 10053),  # An established connection was aborted by the software in your host machine.
    (OSError, 10022),  # Failed to get address info.
    (OSError, 16),  # Socket error: Device or resource busy.
    (OSError, 0)
}

IGNORED_ERRORS_BY_REGEX: Dict[Type[Exception], str] = {
    RuntimeError: r'.*invalid info-hash.*'
}


class NoCrashException(Exception):
    """Raising exceptions of this type doesn't lead to forced Tribler stop"""


class CoreExceptionHandler:
    """
    This class handles Python errors arising in the Core by catching them, adding necessary context,
    and sending them to the GUI through the events endpoint. It must be connected to the Asyncio loop.
    """

    def __init__(self):
        self.logger = logging.getLogger("CoreExceptionHandler")
        self.report_callback: Optional[Callable[[ReportedError], None]] = None
        self.unreported_error: Optional[ReportedError] = None
        self.sentry_reporter = SentryReporter()
        self.crash_dir = None

    @staticmethod
    def _get_long_text_from(exception: Exception):
        with StringIO() as buffer:
            print_exception(type(exception), exception, exception.__traceback__, file=buffer)
            return buffer.getvalue()

    @staticmethod
    def _is_ignored(exception: Exception):
        exception_class = exception.__class__
        error_number = exception.errno if hasattr(exception, 'errno') else None

        if isinstance(exception, IGNORED_ERRORS_BY_CLASS):
            return True

        if (exception_class, error_number) in IGNORED_ERRORS_BY_CODE:
            return True

        if exception_class not in IGNORED_ERRORS_BY_REGEX:
            return False

        pattern = IGNORED_ERRORS_BY_REGEX[exception_class]
        return re.search(pattern, str(exception)) is not None

    def _create_exception_from(self, message: str):
        text = f'Received error without exception: {message}'
        self.logger.warning(text)
        return Exception(text)

    def unhandled_error_observer(self, _, context):
        """
        This method is called when an unhandled error in Tribler is observed.
        It broadcasts the tribler_exception event.
        """
        self.logger.info('Processing unhandled error...')
        process_manager = get_global_process_manager()
        try:
            self.sentry_reporter.ignore_logger(self.logger.name)

            context = context.copy()
            should_stop = context.pop('should_stop', True)
            message = context.pop('message', 'no message')
            exception = context.pop('exception', None) or self._create_exception_from(message)

            self.logger.exception(f'{exception.__class__.__name__}: {exception}', exc_info=exception)

            if isinstance(exception, DatabaseIsCorrupted):
                process_manager.sys_exit(EXITCODE_DATABASE_IS_CORRUPTED, exception)
                return  # Added for clarity; actually, the code raised SystemExit on the previous line

            if isinstance(exception, ComponentStartupException):
                self.logger.info('The exception is ComponentStartupException')
                should_stop = exception.component.tribler_should_stop_on_component_error
                exception = exception.__cause__

            if isinstance(exception, NoCrashException):
                self.logger.info('The exception is NoCrashException')
                should_stop = False
                exception = exception.__cause__

            if self._is_ignored(exception):
                self.logger.info('The exception will be ignored')
                self.logger.warning(exception)
                return

            long_text = self._get_long_text_from(exception)

            reported_error = ReportedError(
                type=exception.__class__.__name__,
                text=str(exception),
                long_text=long_text,
                context=str(context),
                event=self.sentry_reporter.event_from_exception(exception) or {},
                should_stop=should_stop,
                # `additional_information` should be converted to dict
                # see: https://github.com/python/cpython/pull/32056
                additional_information=dict(self.sentry_reporter.additional_information)
            )
            self.logger.error(f"Unhandled exception occurred! {reported_error}\n{reported_error.long_text}")
            if process_manager:
                process_manager.current_process.set_error(exception)

            if should_stop:
                self.save_to_file(reported_error)

            if self.report_callback:
                self.logger.error('Call report callback')
                self.report_callback(reported_error)  # pylint: disable=not-callable
            else:
                self.logger.error('Save the error to later report')
                if not self.unreported_error:
                    # We only remember the first unreported error,
                    # as that was probably the root cause for # the crash
                    self.unreported_error = reported_error

        except Exception as ex:
            if process_manager:
                process_manager.current_process.set_error(ex)

            self.sentry_reporter.capture_exception(ex)
            self.logger.exception(f'Error occurred during the error handling: {ex}')
            raise ex

    def get_or_create_log_dir(self):
        if self.crash_dir and not self.crash_dir.exists():
            self.crash_dir.mkdir(exist_ok=True)
        return self.crash_dir

    def get_file_path(self, reported_error: ReportedError):
        if not self.crash_dir:
            return None

        if not self.crash_dir.exists():
            self.crash_dir.mkdir(exist_ok=True)

        filepath = self.crash_dir / f"{reported_error.type}-{reported_error.created_at}.json"
        return filepath

    def save_to_file(self, reported_error: ReportedError):
        filepath = self.get_file_path(reported_error)
        if not filepath:
            return

        # While saving to file, set should_stop=False.
        # This is because this file will be read on restart of the core, and
        # we don't want to crash the core for the error from the last run.
        self_copy = dataclasses.replace(reported_error)
        self_copy.should_stop = False
        serialized_error = json.dumps(dataclasses.asdict(self_copy), indent=True)

        with open(filepath, 'w', encoding='utf-8') as exc_file:
            exc_file.write(serialized_error)

    def delete_saved_file(self, reported_error: ReportedError):
        if file_path := self.get_file_path(reported_error):
            file_path.unlink(missing_ok=True)

    def get_saved_errors(self):
        if self.crash_dir and not self.crash_dir.exists():
            return []

        saved_errors = []
        for error_filename in os.listdir(self.crash_dir):
            if not error_filename.endswith('.json'):
                continue

            error_file_path = self.crash_dir / error_filename
            with open(error_file_path, 'r', encoding='utf-8') as file_handle:
                try:
                    saved_errors.append(ReportedError(**json.loads(file_handle.read())))
                except JSONDecodeError:
                    error_file_path.unlink()
        return saved_errors


default_core_exception_handler = CoreExceptionHandler()
