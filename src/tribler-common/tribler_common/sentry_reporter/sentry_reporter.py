import logging
from contextvars import ContextVar
from hashlib import md5

from faker import Faker

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.threading import ThreadingIntegration

from tribler_common.sentry_reporter.sentry_tools import (
    delete_item,
    get_first_item,
    get_value,
    parse_os_environ,
    parse_stacktrace,
)

PLATFORM_DETAILS = 'platform.details'
STACKTRACE = '_stacktrace'
SYSINFO = 'sysinfo'
OS_ENVIRON = 'os.environ'
SYS_ARGV = 'sys.argv'
TAGS = 'tags'
CONTEXTS = 'contexts'
EXTRA = 'extra'
BREADCRUMBS = 'breadcrumbs'
LOGENTRY = 'logentry'
REPORTER = 'reporter'


class SentryReporter:
    """SentryReporter designed for sending reports to the Sentry server from
    a Tribler Client.

    # Main concept

    It aims to work in a Tribler Client with the following specifics:

    1. An exception can be raised in two separate processes: GUI and Core.
    2. A report will be sent after a user presses the "send report" button.

    The main concept behind this class is the following: let's add controls that
    can allow or disallow sending Sentry reports by-default.

    If we have these controls, then it is easy to use Sentry with a Tribler
    Client.

    Algorithm:
    1. Initialise Sentry.
    2. Disallow sending messages (but storing the last event).
    3. Waiting for user action: the "sent report" button is pressed.
    4. Allow Sentry sending messages
    5. Send the last event.

    SentryReporter is thread-safe.
   """

    last_event = None

    _allow_sending_global = False
    _allow_sending_in_thread = ContextVar('Sentry')

    _scrubber = None
    _logger = logging.getLogger('SentryReporter')

    @staticmethod
    def init(sentry_url='', scrubber=None):
        """ Initialization.

        This method should be called in each process that uses SentryReporter.

        Args:
            sentry_url: URL for Sentry server. If it is empty then Sentry's
                sending mechanism will not be initialized.

            scrubber: a class that will be used for scrubbing sending events.
                Only a single method should be implemented in the class:
                ```
                    def scrub_event(self, event):
                        pass
                ```
        Returns:
            Sentry Guard.
        """
        SentryReporter._logger.info(f"Init: {sentry_url}")

        SentryReporter._scrubber = scrubber
        return sentry_sdk.init(
            sentry_url,
            release=None,
            # https://docs.sentry.io/platforms/python/configuration/integrations/
            integrations=[
                LoggingIntegration(
                    level=logging.INFO,  # Capture info and above as breadcrumbs
                    event_level=logging.ERROR,  # Send errors as events
                ),
                ThreadingIntegration(propagate_hub=True),
            ],
            before_send=SentryReporter._before_send,
        )

    @staticmethod
    def send(event, post_data, sys_info):
        """Send the event to the Sentry server

        This method
            1. Enable Sentry's sending mechanism.
            2. Extend sending event by the information from post_data.
            3. Send the event.
            4. Disables Sentry's sending mechanism.

        Scrubbing the information will be performed in the `_before_send` method.

        During the execution of this method, all unhandled exceptions that
        will be raised, will be sent to Sentry automatically.

        Args:
            event: event to send. It should be taken from SentryReporter at
            post_data: dictionary made by the feedbackdialog.py
                previous stages of executing.
            sys_info: dictionary made by the feedbackdialog.py

        Returns:
            Event that was sent to Sentry server
        """
        SentryReporter._logger.info(f"Send: {post_data}, {event}")

        if event is None:
            return event

        with AllowSentryReports(value=True, description='SentryReporter.send()'):
            # prepare event
            if CONTEXTS not in event:
                event[CONTEXTS] = {}

            if TAGS not in event:
                event[TAGS] = {}

            event[CONTEXTS][REPORTER] = {}

            # tags
            tags = event[TAGS]
            tags['version'] = get_value(post_data, 'version')
            tags['machine'] = get_value(post_data, 'machine')
            tags['os'] = get_value(post_data, 'os')
            tags['platform'] = get_first_item(get_value(sys_info, 'platform'))
            tags[('%s' % PLATFORM_DETAILS)] = get_first_item(get_value(sys_info, PLATFORM_DETAILS))

            # context
            context = event[CONTEXTS]
            reporter = context[REPORTER]
            version = get_value(post_data, 'version')

            context['browser'] = {'version': version, 'name': 'Tribler'}

            reporter[STACKTRACE] = parse_stacktrace(get_value(post_data, 'stack'))
            reporter['comments'] = get_value(post_data, 'comments')

            reporter[OS_ENVIRON] = parse_os_environ(get_value(sys_info, OS_ENVIRON))
            delete_item(sys_info, OS_ENVIRON)
            reporter[SYSINFO] = sys_info

            sentry_sdk.capture_event(event)

            return event

    @staticmethod
    def set_user(user_id):
        """ Set the user to identify the event on a Sentry server

        The algorithm is the following:
        1. Calculate hash from `user_id`.
        2. Generate fake user, based on the hash.

        No real `user_id` will be used in Sentry.

        Args:
            user_id: Real user id.

        Returns:
            Generated user (dictionary: {id, username}).
        """
        # calculate hash to keep real `user_id` in secret
        user_id_hash = md5(user_id).hexdigest()

        SentryReporter._logger.info(f"Set user: {user_id_hash}")

        Faker.seed(user_id_hash)
        user_name = Faker().name()
        user = {'id': user_id_hash, 'username': user_name}

        sentry_sdk.set_user(user)
        return user

    @staticmethod
    def get_allow_sending():
        """ Indicate whether Sentry allowed or disallowed to sent events.

        Returns:
            Bool
        """
        allow_sending_in_thread = SentryReporter._allow_sending_in_thread.get(None)
        if allow_sending_in_thread is not None:
            return allow_sending_in_thread

        return SentryReporter._allow_sending_global

    @staticmethod
    def allow_sending_globally(value, info=None):
        """ Setter for `_allow_sending_global` variable.

        It globally allows or disallows Sentry to send events.
        If `_allow_sending_in_thread` is not set, then `_allow_sending_global`
        will be used.

        Args:
            value: Bool
            info: String that will be used as an indicator of allowing or
            disallowing reason (or the place from which this method has been
            invoked).

        Returns:
            None
        """
        SentryReporter._logger.info(f"Allow sending globally: {value}. Info: {info}")
        SentryReporter._allow_sending_global = value

    @staticmethod
    def allow_sending_in_thread(value, info=None):
        """ Setter for `_allow_sending` variable.

        It allows or disallows Sentry to send events in the current thread.
        If `_allow_sending_in_thread` is not set, then `_allow_sending_global`
        will be used.

        Args:
            value: Bool
            info: String that will be used as an indicator of allowing or
            disallowing reason (or the place from which this method has been
            invoked).

        Returns:
            None
        """
        SentryReporter._logger.info(f"Allow sending in thread: {value}. Info: {info}")
        SentryReporter._allow_sending_in_thread.set(value)

    @staticmethod
    def _before_send(event, _):
        """The method that is called before each send. Both allowed and
        disallowed.

        The algorithm:
        1. If sending is allowed, then scrub the event and send.
        2. If sending is disallowed, then store the event in
            `SentryReporter.last_event`

        Args:
            event: event that generated by Sentry
            hint: root exception (can be used in some cases)

        Returns:
            The event, prepared for sending, or `None`, if sending is suppressed.
        """
        if not event:
            return event

        SentryReporter._logger.info(f"Before send event: {event}")
        SentryReporter._logger.info(f"Is allow sending: {SentryReporter._allow_sending_global}")
        # to synchronise error reporter and sentry, we should suppress all events
        # until user clicked on "send crash report"
        if not SentryReporter.get_allow_sending():
            SentryReporter._logger.info("Suppress sending. Storing the event.")
            SentryReporter.last_event = event
            return None

        # clean up the event
        SentryReporter._logger.info(f"Clean up the event with scrubber: {SentryReporter._scrubber}")
        if SentryReporter._scrubber:
            event = SentryReporter._scrubber.scrub_event(event)

        return event


class AllowSentryReports:
    """ This class designed for simplifying allowing and disallowing
    Sentry's sending mechanism for particular blocks of code.

    It is thread-safe, and use `SentryReporter.allow_sending_in_thread` method
    for setting corresponding variable.

    Example of use:
    ```
        with AllowSentryReports(value=True):
            do_some_work()
    ```
    """

    def __init__(self, value=True, description='', reporter=None):
        """ Initialising a value and a reporter

        Args:
            value: Value that will be used for passing in
                `SentryReporter.allow_sending`.
            description: Will be used while logging.
            reporter: Instance of a reporter. This argument mostly use for
                testing purposes.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info(f'Value: {value}, description: {description}')

        self._value = value
        self._saved_state = None
        self._reporter = reporter or SentryReporter()

    def __enter__(self):
        """Set SentryReporter.allow_sending(value)
        """
        self._logger.info('Enter')
        self._saved_state = self._reporter.get_allow_sending()

        self._reporter.allow_sending_in_thread(self._value, 'AllowSentryReports.__enter__()')
        return self._reporter

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore SentryReporter.allow_sending(old_value)
        """
        self._logger.info('Exit')
        self._reporter.allow_sending_in_thread(self._saved_state, 'AllowSentryReports.__exit__()')
