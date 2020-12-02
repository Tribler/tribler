import logging
import sys
from contextvars import ContextVar
from enum import Enum, auto
from hashlib import md5

from PyQt5.QtWidgets import QApplication, QMessageBox

from faker import Faker

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration, ignore_logger
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

    It can work with 3 strategies:
    1. Send reports are allowed
    2. Send reports are allowed with a confirmation dialog
    3. Send reports are suppressed (disallowed, but the last event will be stored)

    Example of how to change a strategy:
    ```
        SentryReporter.strategy.set(SentryReporter.Strategy.SEND_SUPPRESSED)
    ```
    SentryReporter is thread-safe.
   """

    class Strategy(Enum):
        SEND_ALLOWED = auto()
        SEND_ALLOWED_WITH_CONFIRMATION = auto()
        SEND_SUPPRESSED = auto()  # the last event will be stored in `SentryReporter.last_event`

    last_event = None

    ignored_exceptions = [KeyboardInterrupt, SystemExit]

    strategy = ContextVar('Sentry', default=Strategy.SEND_ALLOWED_WITH_CONFIRMATION)

    _scrubber = None
    _sentry_logger_name = 'SentryReporter'
    _logger = logging.getLogger(_sentry_logger_name)

    @staticmethod
    def init(sentry_url='', scrubber=None, strategy=Strategy.SEND_ALLOWED_WITH_CONFIRMATION):
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
        SentryReporter._logger.debug(f"Init: {sentry_url}")
        SentryReporter._scrubber = scrubber
        SentryReporter.strategy.set(strategy)

        rv = sentry_sdk.init(
            sentry_url,
            release=None,
            # https://docs.sentry.io/platforms/python/configuration/integrations/
            integrations=[
                LoggingIntegration(
                    level=logging.INFO,  # Capture info and above as breadcrumbs
                    event_level=None,  # Send no errors as events
                ),
                ThreadingIntegration(propagate_hub=True),
            ],
            before_send=SentryReporter._before_send,
        )

        ignore_logger(SentryReporter._sentry_logger_name)

        return rv

    @staticmethod
    def ignore_logger(logger_name):
        SentryReporter._logger.debug(f"Ignore logger: {logger_name}")
        ignore_logger(logger_name)

    @staticmethod
    def send_event(event, post_data=None, sys_info=None):
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

        saved_strategy = SentryReporter.strategy.get()
        try:
            SentryReporter.strategy.set(SentryReporter.Strategy.SEND_ALLOWED)
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
        finally:
            SentryReporter.strategy.set(saved_strategy)

    @staticmethod
    def get_confirmation(exception):
        """Get confirmation on sending exception to the Team.

        There are two message boxes, that will be triggered:
        1. Message box with the error_text
        2. Message box with confirmation about sending this report to the Tribler
            team.

        Args:
            exception: exception to be sent.
        """
        SentryReporter._logger.debug(f"Get confirmation: {exception}")

        _ = QApplication(sys.argv)
        messagebox = QMessageBox(icon=QMessageBox.Critical, text=f'{exception}.')
        messagebox.setWindowTitle("Error")
        messagebox.exec()

        messagebox = QMessageBox(
            icon=QMessageBox.Question,
            text='Do you want to send this crash report to the Tribler team? '
            'We anonymize all your data, who you are and what you downloaded.',
        )
        messagebox.setWindowTitle("Error")
        messagebox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

        return messagebox.exec() == QMessageBox.Yes

    @staticmethod
    def capture_exception(exception):
        SentryReporter._logger.info(f"Capture exception: {exception}")
        sentry_sdk.capture_exception(exception)

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

        SentryReporter._logger.debug(f"Set user: {user_id_hash}")

        Faker.seed(user_id_hash)
        user_name = Faker().name()
        user = {'id': user_id_hash, 'username': user_name}

        sentry_sdk.set_user(user)
        return user

    @staticmethod
    def _before_send(event, hint):
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

        strategy = SentryReporter.strategy.get()
        SentryReporter._logger.info(f"Before send event: {event}")
        SentryReporter._logger.info(f"Strategy: {strategy}")

        exc_info = get_value(hint, 'exc_info')
        error_type = get_first_item(exc_info)

        if error_type in SentryReporter.ignored_exceptions:
            SentryReporter._logger.debug(f"Exception is in ignored: {hint}. Skipped.")
            return None

        if strategy == SentryReporter.Strategy.SEND_SUPPRESSED:
            SentryReporter._logger.debug("Suppress sending. Storing the event.")
            SentryReporter.last_event = event
            return None

        if strategy == SentryReporter.Strategy.SEND_ALLOWED_WITH_CONFIRMATION:
            SentryReporter._logger.debug("Request confirmation.")
            if not SentryReporter.get_confirmation(hint):
                return None

        # clean up the event
        SentryReporter._logger.debug(f"Clean up the event with scrubber: {SentryReporter._scrubber}")
        if SentryReporter._scrubber:
            event = SentryReporter._scrubber.scrub_event(event)

        return event
