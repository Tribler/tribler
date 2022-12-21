import logging
import os
import sys

from PyQt5.QtCore import QSettings

from tribler.core.check_os import (
    check_and_enable_code_tracing,
    check_environment,
    check_free_space,
    enable_fault_handler
)
from tribler.core.exceptions import TriblerException
from tribler.core.logger.logger import load_logger_config
from tribler.core.sentry_reporter.sentry_reporter import SentryStrategy
from tribler.core.utilities.process_manager import ProcessKind, ProcessManager, set_global_process_manager
from tribler.core.utilities.rest_utils import path_to_url
from tribler.core.utilities.utilities import show_system_popup
from tribler.gui import gui_sentry_reporter
from tribler.gui.app_manager import AppManager
from tribler.gui.tribler_app import TriblerApplication
from tribler.gui.tribler_window import TriblerWindow
from tribler.gui.utilities import get_translator

logger = logging.getLogger(__name__)


def run_gui(api_port, api_key, root_state_dir, parsed_args):
    logger.info('Running GUI' + ' in gui_test_mode' if parsed_args.gui_test_mode else '')

    # Workaround for macOS Big Sur, see https://github.com/Tribler/tribler/issues/5728
    if sys.platform == "darwin":
        logger.info('Enabling a workaround for macOS Big Sur')
        os.environ["QT_MAC_WANTS_LAYER"] = "1"
    # Workaround for Ubuntu 21.04+, see https://github.com/Tribler/tribler/issues/6701
    elif sys.platform == "linux":
        logger.info('Enabling a workaround for Ubuntu 21.04+ wayland environment')
        os.environ["GDK_BACKEND"] = "x11"

    # Set up logging
    load_logger_config('tribler-gui', root_state_dir)

    # Enable tracer using commandline args: --trace-debug or --trace-exceptions
    trace_logger = check_and_enable_code_tracing('gui', root_state_dir)

    enable_fault_handler(root_state_dir)
    # Exit if we cant read/write files, etc.
    check_environment()
    check_free_space()

    process_manager = ProcessManager(root_state_dir, ProcessKind.GUI)
    another_process_is_primary = not process_manager.current_process.primary
    set_global_process_manager(process_manager)   # to be able to add information about exception to the process info
    try:
        app_name = os.environ.get('TRIBLER_APP_NAME', 'triblerapp')
        app = TriblerApplication(app_name, sys.argv, another_process_is_primary)
        app_manager = AppManager(app)

        # Note (@ichorid): translator MUST BE created and assigned to a separate variable
        # before calling installTranslator on app. Otherwise, it won't work for some reason
        settings = QSettings('nl.tudelft.tribler')
        translator = get_translator(settings.value('translation', None))
        app.installTranslator(translator)

        if app.is_running():
            # if an application is already running, then send the command line
            # argument to it and close the current instance
            logger.info('GUI Application is already running. Passing a torrent file path to it.')
            for arg in sys.argv[1:]:
                if os.path.exists(arg) and arg.endswith(".torrent"):
                    app.send_message(path_to_url(arg))
                elif arg.startswith('magnet'):
                    app.send_message(arg)
            logger.info('Close the current application.')
            process_manager.sys_exit(1, 'Tribler GUI application is already running')

        logger.info('Start Tribler Window')
        window = TriblerWindow(app_manager, settings, root_state_dir, api_port=api_port, api_key=api_key)
        window.setWindowTitle("Tribler")
        app.tribler_window = window
        app.parse_sys_args(sys.argv)
        exit_code = app.exec_()
        process_manager.sys_exit(exit_code or None)

    except ImportError as ie:
        logger.exception(ie)
        show_system_popup("Import Error", f"Import error: {ie}")
        process_manager.sys_exit(1, exc=ie)

    except TriblerException as te:
        logger.exception(te)
        show_system_popup("Tribler Exception", f"{te.__class__.__name__}: {te}")
        process_manager.sys_exit(1, exc=te)

    except SystemExit:
        logger.info("Shutting down Tribler")
        if trace_logger:
            trace_logger.close()

        # Flush all the logs to make sure it is written to file before it exits
        for handler in logging.getLogger().handlers:
            handler.flush()

        gui_sentry_reporter.global_strategy = SentryStrategy.SEND_SUPPRESSED
        raise
