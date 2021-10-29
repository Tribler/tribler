import errno
import logging
import sys
from io import StringIO
from socket import gaierror
from traceback import print_exception
from typing import Callable, Optional

from tribler_common.sentry_reporter.sentry_reporter import SentryReporter

from tribler_core.components.base import ComponentStartupException
from tribler_core.utilities.utilities import froze_it

if sys.platform == 'win32':
    SOCKET_BLOCK_ERRORCODE = 10035  # WSAEWOULDBLOCK
else:
    SOCKET_BLOCK_ERRORCODE = errno.EWOULDBLOCK
# There are some errors that we are ignoring.
IGNORED_ERRORS = {
    # No route to host: this issue is non-critical since Tribler can still function when a request fails.
    (OSError, 113): "Observed no route to host error (but ignoring)."
                    "This might indicate a problem with your firewall.",
    # Socket block: this sometimes occurs on Windows and is non-critical.
    (BlockingIOError, SOCKET_BLOCK_ERRORCODE): f"Unable to send data due to builtins.OSError {SOCKET_BLOCK_ERRORCODE}",
    (OSError, 51): "Could not send data: network is unreachable.",
    (ConnectionAbortedError, 10053): "An established connection was aborted by the software in your host machine.",
    (ConnectionResetError, 10054): "Connection forcibly closed by the remote host.",
    (OSError, 10022): "Failed to get address info. Error code: 10022",
    (OSError, 16): "Socket error: Device or resource busy. Error code: 16",
    (OSError, 0): "",
    gaierror: "Unable to perform DNS lookup."
}


@froze_it
class CoreExceptionHandler:
    """
    This singleton handles Python errors arising in the Core by catching them, adding necessary context,
    and sending them to the GUI through the events endpoint. It must be connected to the Asyncio loop.
    """

    _logger = logging.getLogger("CoreExceptionHandler")
    report_callback: Optional[Callable] = None

    @classmethod
    def unhandled_error_observer(cls, loop, context):  # pylint: disable=unused-argument
        """
        This method is called when an unhandled error in Tribler is observed.
        It broadcasts the tribler_exception event.
        """
        try:
            SentryReporter.ignore_logger(cls._logger.name)

            should_stop = True
            exception = context.get('exception')
            if isinstance(exception, ComponentStartupException):
                should_stop = exception.component.tribler_should_stop_on_component_error
                exception = exception.__cause__

            ignored_message = None
            try:
                ignored_message = IGNORED_ERRORS.get(
                    (exception.__class__, exception.errno),
                    IGNORED_ERRORS.get(exception.__class__))
            except (ValueError, AttributeError):
                pass
            if ignored_message is not None:
                cls._logger.error(ignored_message if ignored_message != "" else context.get('message'))
                return

            text = str(exception or context.get('message'))
            # We already have a check for invalid infohash when adding a torrent, but if somehow we get this
            # error then we simply log and ignore it.
            if isinstance(exception, RuntimeError) and 'invalid info-hash' in text:
                cls._logger.error("Invalid info-hash found")
                return

            exc_type_name = exc_long_text = text
            if isinstance(exception, Exception):
                exc_type_name = type(exception).__name__
                with StringIO() as buffer:
                    print_exception(type(exception), exception, exception.__traceback__, file=buffer)
                    exc_long_text = exc_long_text + "\n--LONG TEXT--\n" + buffer.getvalue()
            exc_long_text = exc_long_text + "\n--CONTEXT--\n" + str(context)
            cls._logger.error("Unhandled exception occurred! %s", exc_long_text, exc_info=None)

            sentry_event = SentryReporter.event_from_exception(exception)

            if cls.report_callback is not None:
                cls.report_callback(exc_type_name, exc_long_text, sentry_event, should_stop=should_stop)  # pylint: disable=not-callable

        except Exception as ex:
            SentryReporter.capture_exception(ex)
            raise ex
