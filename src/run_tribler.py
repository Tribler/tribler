import argparse
# A fix for "LookupError: unknown encoding: idna" error.
# Adding encodings.idna to hiddenimports is not enough.
# https://github.com/pyinstaller/pyinstaller/issues/1113
# noinspection PyUnresolvedReferences
import encodings.idna  # pylint: disable=unused-import
import logging.config
import os
import sys

from tribler_core.components.reporter.exception_handler import default_core_exception_handler
from tribler_core.sentry_reporter.sentry_reporter import SentryStrategy
from tribler_core.sentry_reporter.sentry_scrubber import SentryScrubber

logger = logging.getLogger(__name__)


# pylint: disable=import-outside-toplevel, ungrouped-imports


class RunTriblerArgsParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs['description'] = 'Run Tribler BitTorrent client'
        super().__init__(*args, **kwargs)
        self.add_argument('torrent', help='torrent file to download', default='', nargs='?')
        self.add_argument('--core', action="store_true")
        self.add_argument('--gui-test-mode', action="store_true")


def init_sentry_reporter():
    """ Initialise sentry reporter

    We use `sentry_url` as a URL for normal tribler mode and TRIBLER_TEST_SENTRY_URL
    as a URL for sending sentry's reports while a Tribler client running in
    test mode
    """
    sentry_reporter = default_core_exception_handler.sentry_reporter
    from tribler_core.version import sentry_url, version_id
    test_sentry_url = sentry_reporter.get_test_sentry_url()

    if not test_sentry_url:
        sentry_reporter.init(sentry_url=sentry_url,
                             release_version=version_id,
                             scrubber=SentryScrubber(),
                             strategy=SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION)
        logger.info('Sentry has been initialised in normal mode')
    else:
        sentry_reporter.init(sentry_url=test_sentry_url,
                             release_version=version_id,
                             scrubber=None,
                             strategy=SentryStrategy.SEND_ALLOWED)
        logger.info('Sentry has been initialised in debug mode')


def init_boot_logger():
    # this logger config will be used before Core and GUI
    #  set theirs configs explicitly
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)


if __name__ == "__main__":
    init_boot_logger()
    init_sentry_reporter()

    parsed_args = RunTriblerArgsParser().parse_args()
    logger.info(f'Run Tribler: {parsed_args}')

    # Get root state directory (e.g. from environment variable or from system default)
    from tribler_core.utilities.osutils import get_root_state_directory

    root_state_dir = get_root_state_directory()
    logger.info(f'Root state dir: {root_state_dir}')

    api_port = os.environ.get('CORE_API_PORT')
    api_key = os.environ.get('CORE_API_KEY')

    # Check whether we need to start the core or the user interface
    if parsed_args.core:
        from tribler_core.start_core import run_core

        run_core(api_port, api_key, root_state_dir, parsed_args)
    else:  # GUI
        from tribler_gui.start_gui import run_gui

        run_gui(api_port, api_key, root_state_dir, parsed_args)
