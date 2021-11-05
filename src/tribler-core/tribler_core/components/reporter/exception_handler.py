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
from tribler_core.utilities.utilities import froze_it

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


@froze_it
class CoreExceptionHandler:
    """
    This singleton handles Python errors arising in the Core by catching them, adding necessary context,
    and sending them to the GUI through the events endpoint. It must be connected to the Asyncio loop.
    """

    _logger = logging.getLogger("CoreExceptionHandler")
    report_callback: Optional[Callable[[ReportedError], None]] = None
    requires_user_consent: bool = True

    @staticmethod
    def _get_long_text_from(exception: Exception):
        with StringIO() as buffer:
            print_exception(type(exception), exception, exception.__traceback__, file=buffer)
            return buffer.getvalue()

    @classmethod
    def _create_exception_from(cls, message: str):
        text = f'Received error without exception: {message}'
        cls._logger.warning(text)
        return Exception(text)

    @classmethod
    def _is_ignored(cls, exception: Exception):
        exception_class = exception.__class__
        error_number = exception.errno if hasattr(exception, 'errno') else None

        if (exception_class, error_number) in IGNORED_ERRORS_BY_CODE:
            return True

        if exception_class not in IGNORED_ERRORS_BY_REGEX:
            return False

        pattern = IGNORED_ERRORS_BY_REGEX[exception_class]
        return re.search(pattern, str(exception)) is not None

    @classmethod
    def unhandled_error_observer(cls, loop, context):  # pylint: disable=unused-argument
        """
        This method is called when an unhandled error in Tribler is observed.
        It broadcasts the tribler_exception event.
        """
        try:
            SentryReporter.ignore_logger(cls._logger.name)

            should_stop = True
            context = context.copy()
            message = context.pop('message', 'no message')
            exception = context.pop('exception', None) or cls._create_exception_from(message)
            # Exception
            text = str(exception)
            if isinstance(exception, ComponentStartupException):
                should_stop = exception.component.tribler_should_stop_on_component_error
                exception = exception.__cause__

            if cls._is_ignored(exception):
                cls._logger.warning(exception)
                return

            long_text = cls._get_long_text_from(exception)
            cls._logger.error(f"Unhandled exception occurred! {exception}\n{long_text}")

            reported_error = ReportedError(
                type=exception.__class__.__name__,
                text=text,
                long_text=long_text,
                context=str(context),
                event=SentryReporter.event_from_exception(exception) or {},
                requires_user_consent=cls.requires_user_consent,
                should_stop=should_stop
            )
            if cls.report_callback:
                cls.report_callback(reported_error)  # pylint: disable=not-callable

        except Exception as ex:
            SentryReporter.capture_exception(ex)
            raise ex
