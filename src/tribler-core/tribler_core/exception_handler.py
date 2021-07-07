import errno
import sys
from _socket import gaierror
from io import StringIO
from traceback import print_exception

from tribler_common.sentry_reporter.sentry_reporter import SentryReporter
from tribler_core.settings import ErrorHandlingSettings
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
    This class handles Python errors arising in the Core by catching them, adding necessary context,
    and sending them to the GUI through the events endpoint. It must be connected to the Asyncio loop.
    """
    def __init__(self, logger, config: ErrorHandlingSettings, events_endpoint=None, state_endpoint=None):
        self._logger = logger
        self.config = config
        self.events_endpoint = events_endpoint
        self.state_endpoint = state_endpoint

    def unhandled_error_observer(self, loop, context):
        """
        This method is called when an unhandled error in Tribler is observed.
        It broadcasts the tribler_exception event.
        """
        try:
            SentryReporter.ignore_logger(self._logger.name)

            exception = context.get('exception')
            ignored_message = None
            try:
                ignored_message = IGNORED_ERRORS.get(
                    (exception.__class__, exception.errno),
                    IGNORED_ERRORS.get(exception.__class__))
            except (ValueError, AttributeError):
                pass
            if ignored_message is not None:
                self._logger.error(ignored_message if ignored_message != "" else context.get('message'))
                return
            text = str(exception or context.get('message'))
            # We already have a check for invalid infohash when adding a torrent, but if somehow we get this
            # error then we simply log and ignore it.
            if isinstance(exception, RuntimeError) and 'invalid info-hash' in text:
                self._logger.error("Invalid info-hash found")
                return
            text_long = text
            exc = context.get('exception')
            if exc:
                with StringIO() as buffer:
                    print_exception(type(exc), exc, exc.__traceback__, file=buffer)
                    text_long = text_long + "\n--LONG TEXT--\n" + buffer.getvalue()
            text_long = text_long + "\n--CONTEXT--\n" + str(context)
            self._logger.error("Unhandled exception occurred! %s", text_long, exc_info=None)

            sentry_event = SentryReporter.event_from_exception(exception)

            if self.events_endpoint:
                self.events_endpoint.on_tribler_exception(
                    text_long, sentry_event, self.config.core_error_reporting_requires_user_consent)

            if self.events_endpoint:
                self.state_endpoint.on_tribler_exception(text_long, sentry_event)

        except Exception as ex:
            SentryReporter.capture_exception(ex)
            raise ex
