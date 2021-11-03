import logging.config
import os
import sys

from PyQt5.QtCore import QSettings

logger = logging.getLogger(__name__)
CONFIG_FILE_NAME = 'triblerd.conf'


# pylint: disable=import-outside-toplevel, ungrouped-imports

def init_sentry_reporter():
    from tribler_common.sentry_reporter.sentry_reporter import SentryReporter, SentryStrategy
    from tribler_common.sentry_reporter.sentry_scrubber import SentryScrubber

    """ Initialise sentry reporter

    We use `sentry_url` as a URL for normal tribler mode and TEST_SENTRY_URL
    as a URL for sending sentry's reports while a Tribler client running in
    test mode
    """
    from tribler_core.version import sentry_url, version_id
    test_sentry_url = os.environ.get('TEST_SENTRY_URL', None)

    if not test_sentry_url:
        SentryReporter.init(sentry_url=sentry_url,
                            release_version=version_id,
                            scrubber=SentryScrubber(),
                            strategy=SentryStrategy.SEND_ALLOWED_WITH_CONFIRMATION)
        logger.info('Sentry has been initialised in normal mode')
    else:
        SentryReporter.init(sentry_url=test_sentry_url,
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

    # Get root state directory (e.g. from environment variable or from system default)
    from tribler_common.osutils import get_root_state_directory

    root_state_dir = get_root_state_directory()
    logger.info(f'Root state dir: {root_state_dir}')

    # Check whether we need to start the core or the user interface
    if 'CORE_PROCESS' in os.environ:
        logger.info('Running in "core" mode')

        base_path = os.environ['CORE_BASE_PATH']
        api_port = os.environ['CORE_API_PORT']
        api_key = os.environ.get('CORE_API_KEY')
        gui_test_mode = bool(os.environ.get("TRIBLER_GUI_TEST_MODE", False))

        from tribler_core.start_core import start_tribler_core
        start_tribler_core(base_path, api_port, api_key, root_state_dir, gui_test_mode=gui_test_mode)
    else:
        import tribler_gui
        from tribler_gui.utilities import get_translator

        logger.info('Running in "normal" mode')

        # Workaround for macOS Big Sur, see https://github.com/Tribler/tribler/issues/5728
        if sys.platform == "darwin":
            logger.info('Enabling a workaround for macOS Big Sur')
            os.environ["QT_MAC_WANTS_LAYER"] = "1"

        # Set up logging
        tribler_gui.load_logger_config(root_state_dir)

        from tribler_core.check_os import check_and_enable_code_tracing, check_environment, check_free_space, \
            enable_fault_handler, error_and_exit, should_kill_other_tribler_instances
        from tribler_core.exceptions import TriblerException

        try:
            # Enable tracer using commandline args: --trace-debug or --trace-exceptions
            trace_logger = check_and_enable_code_tracing('gui', root_state_dir)

            enable_fault_handler(root_state_dir)

            # Exit if we cant read/write files, etc.
            check_environment()

            should_kill_other_tribler_instances(root_state_dir)

            check_free_space()

            from tribler_gui.tribler_app import TriblerApplication
            from tribler_gui.tribler_window import TriblerWindow

            app_name = os.environ.get('TRIBLER_APP_NAME', 'triblerapp')
            app = TriblerApplication(app_name, sys.argv)
            # ACHTUNG! translator MUST BE created and assigned to a separate variable
            # BEFORE calling installTranslator on app. Otherwise, it won't work for some reason

            settings = QSettings('nl.tudelft.tribler')
            translator = get_translator(settings.value('translation', None))
            app.installTranslator(translator)

            if app.is_running():
                logger.info('Application is running')
                for arg in sys.argv[1:]:
                    if os.path.exists(arg) and arg.endswith(".torrent"):
                        app.send_message(f"file:{arg}")
                    elif arg.startswith('magnet'):
                        app.send_message(arg)

                sys.exit(1)

            logger.info('Start Tribler Window')
            window = TriblerWindow(settings)
            window.setWindowTitle("Tribler")
            app.set_activation_window(window)
            app.parse_sys_args(sys.argv)
            sys.exit(app.exec_())

        except ImportError as ie:
            logger.exception(ie)
            error_and_exit("Import Error", f"Import error: {ie}")

        except TriblerException as te:
            logger.exception(te)
            error_and_exit("Tribler Exception", f"{te}")

        except SystemExit:
            logger.info("Shutting down Tribler")
            if trace_logger:
                trace_logger.close()
            # Flush all the logs to make sure it is written to file before it exits
            for handler in logging.getLogger().handlers:
                handler.flush()
            raise
