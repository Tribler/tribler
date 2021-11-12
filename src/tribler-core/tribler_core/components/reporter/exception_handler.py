import errno
import logging
import re
import sys
from io import StringIO
from socket import gaierror
from traceback import print_exception
from typing import Callable, Optional

from tribler_common.reported_error import ReportedError
from tribler_common.sentry_reporter.sentry_reporter import SentryReporter

from tribler_core.components.base import ComponentStartupException

# There are some errors that we are ignoring.
IGNORED_ERRORS_BY_CODE = {
    (OSError, 113),  # No route to host is non-critical since Tribler can still function when a request fails.
    # Socket block: this sometimes occurs on Windows and is non-critical.
    (BlockingIOError, 10035 if sys.platform == 'win32' else errno.EWOULDBLOCK),
    (OSError, 51),  # Could not send data: network is unreachable.
    (ConnectionAbortedError, 10053),  # An established connection was aborted by the software in your host machine.
    (ConnectionResetError, 10054),  # Connection forcibly closed by the remote host.
    (OSError, 10022),  # Failed to get address info.
    (OSError, 16),  # Socket error: Device or resource busy.
    (OSError, 0)
}

IGNORED_ERRORS_BY_REGEX = {
    gaierror: r'',  # all gaierror is ignored
    RuntimeError: r'.*invalid info-hash.*'
}


class CoreExceptionHandler:
    """
    This class handles Python errors arising in the Core by catching them, adding necessary context,
    and sending them to the GUI through the events endpoint. It must be connected to the Asyncio loop.
    """

    def __init__(self):
        self.logger = logging.getLogger("CoreExceptionHandler")
        self.report_callback: Optional[Callable[[ReportedError], None]] = None

    @staticmethod
    def _get_long_text_from(exception: Exception):
        with StringIO() as buffer:
            print_exception(type(exception), exception, exception.__traceback__, file=buffer)
            return buffer.getvalue()

    @staticmethod
    def _is_ignored(exception: Exception):
        exception_class = exception.__class__
        error_number = exception.errno if hasattr(exception, 'errno') else None

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
        try:
            SentryReporter.ignore_logger(self.logger.name)

            should_stop = True
            context = context.copy()
            message = context.pop('message', 'no message')
            exception = context.pop('exception', None) or self._create_exception_from(message)
            # Exception
            text = str(exception)
            if isinstance(exception, ComponentStartupException):
                should_stop = exception.component.tribler_should_stop_on_component_error
                exception = exception.__cause__

            if self._is_ignored(exception):
                self.logger.warning(exception)
                return

            long_text = self._get_long_text_from(exception)
            self.logger.error(f"Unhandled exception occurred! {exception}\n{long_text}")

            reported_error = ReportedError(
                type=exception.__class__.__name__,
                text=text,
                long_text=long_text,
                context=str(context),
                event=SentryReporter.event_from_exception(exception) or {},
                should_stop=should_stop
            )
            if self.report_callback:
                self.report_callback(reported_error)  # pylint: disable=not-callable

        except Exception as ex:
            SentryReporter.capture_exception(ex)
            raise ex


default_core_exception_handler = CoreExceptionHandler()
