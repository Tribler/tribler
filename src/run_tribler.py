import argparse
import logging.config
import os
import sys

# A fix for "LookupError: unknown encoding: idna" error.
# Adding encodings.idna to hiddenimports is not enough.
# https://github.com/pyinstaller/pyinstaller/issues/1113
# noinspection PyUnresolvedReferences
import encodings.idna  # pylint: disable=unused-import

from tribler.core.sentry_reporter.sentry_reporter import SentryReporter, SentryStrategy
from tribler.core.sentry_reporter.sentry_scrubber import SentryScrubber
from tribler.core.utilities.slow_coro_detection.main_thread_stack_tracking import start_main_thread_stack_tracing
from tribler.core.utilities.osutils import get_root_state_directory
from tribler.core.utilities.utilities import is_frozen
from tribler.core.version import version_id

logger = logging.getLogger(__name__)


# pylint: disable=import-outside-toplevel, ungrouped-imports


class RunTriblerArgsParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs['description'] = 'Run Tribler BitTorrent client'
        super().__init__(*args, **kwargs)
        self.add_argument('torrent', help='torrent file to download', default='', nargs='?')
        self.add_argument('--core', action="store_true", help="run core process")
        self.add_argument('--gui-test-mode', action="store_true", help="use fake data to test GUI application")

        self.add_argument('--allow-code-injection', action="store_true",
                          help="accept remote code to test GUI application")

        self.add_argument('--trace-exception', action="store_true", help="trace exceptions for debugging")
        self.add_argument('--trace-debug', action="store_true", help="trace function calls for debugging")

        self.add_argument('--testnet', action="store_true", help="run Tribler in a separate test network")

        self.add_argument('--chant-testnet', action="store_true", help="use a separate test database for channels")
        self.add_argument('--tunnel-testnet', action="store_true", help="use a separate tunnel community")


def init_sentry_reporter(reporter: SentryReporter):
    """ Initialise sentry reporter

    We use `sentry_url` as a URL for normal tribler mode and TRIBLER_TEST_SENTRY_URL
    as a URL for sending sentry's reports while a Tribler client running in
    test mode
    """
    sentry_url = reporter.get_sentry_url()
    test_sentry_url = reporter.get_test_sentry_url()
    if not test_sentry_url:
        reporter.init(
            sentry_url=sentry_url,
            release_version=version_id,
            scrubber=SentryScrubber(),
            strategy=SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION
        )
        logger.info('Sentry has been initialised in normal mode')
    else:
        reporter.init(
            sentry_url=test_sentry_url,
            release_version=version_id,
            scrubber=None,
            strategy=SentryStrategy.SEND_ALLOWED
        )
        logger.info('Sentry has been initialised in debug mode')


def init_boot_logger():
    # this logger config will be used before Core and GUI
    #  set theirs configs explicitly
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def main():
    init_boot_logger()

    parsed_args = RunTriblerArgsParser().parse_args()
    logger.info(f'Run Tribler: {parsed_args}')

    root_state_dir = get_root_state_directory(create=True)
    logger.info(f'Root state dir: {root_state_dir}')

    api_port = os.environ.get('CORE_API_PORT')
    api_port = int(api_port) if api_port else None

    api_key = os.environ.get('CORE_API_KEY')

    # Check whether we need to start the core or the user interface
    if parsed_args.core:
        from tribler.core.utilities.pony_utils import track_slow_db_sessions
        track_slow_db_sessions()

        from tribler.core.start_core import run_core
        from tribler.core.components.reporter.exception_handler import default_core_exception_handler

        init_sentry_reporter(default_core_exception_handler.sentry_reporter)

        slow_coro_stack_tracking = os.environ.get('SLOW_CORO_STACK_TRACING', '0' if is_frozen() else '1')
        # By default, the stack tracking of slow coroutines is enabled when running the Tribler from sources
        # and disabled in the compiled version, as it makes the Python code of Core work slower.
        if slow_coro_stack_tracking == '1':
            start_main_thread_stack_tracing()

        run_core(api_port, api_key, root_state_dir, parsed_args)
    else:  # GUI
        from tribler.gui.start_gui import run_gui
        from tribler.gui import gui_sentry_reporter

        init_sentry_reporter(gui_sentry_reporter)
        run_gui(api_port, api_key, root_state_dir, parsed_args)


if __name__ == "__main__":
    main()
