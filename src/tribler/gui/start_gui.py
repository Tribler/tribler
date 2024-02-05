import logging
import os
import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QSettings

from tribler.core.check_os import (
    check_and_enable_code_tracing,
    check_environment,
    check_free_space,
    enable_fault_handler
)
from tribler.core.logger.logger import load_logger_config
from tribler.core.sentry_reporter.sentry_reporter import SentryStrategy
from tribler.core.utilities.exit_codes.tribler_exit_codes import EXITCODE_ANOTHER_GUI_PROCESS_IS_RUNNING
from tribler.core.utilities.process_locking import GUI_LOCK_FILENAME, try_acquire_file_lock
from tribler.core.utilities.process_manager import ProcessKind
from tribler.core.utilities.process_manager.manager import setup_process_manager
from tribler.core.utilities.utilities import show_system_popup
from tribler.gui import gui_sentry_reporter
from tribler.gui.app_manager import AppManager
from tribler.gui.tribler_app import TriblerApplication
from tribler.gui.tribler_window import TriblerWindow
from tribler.gui.utilities import get_translator

logger = logging.getLogger(__name__)


def run_gui(api_port: Optional[int], api_key: Optional[str], root_state_dir: Path, parsed_args):
    logger.info(f"Running GUI in {'gui_test_mode' if parsed_args.gui_test_mode else 'normal mode'}")

    # Workaround for macOS Big Sur, see https://github.com/Tribler/tribler/issues/5728
    if sys.platform == "darwin":
        logger.info('Enabling a workaround for macOS Big Sur')
        os.environ["QT_MAC_WANTS_LAYER"] = "1"
    # Workaround for Ubuntu 21.04+, see https://github.com/Tribler/tribler/issues/6701
    elif sys.platform == "linux":
        logger.info('Enabling a workaround for Ubuntu 21.04+ wayland environment')
        os.environ["GDK_BACKEND"] = "x11"

    process_lock = try_acquire_file_lock(root_state_dir / GUI_LOCK_FILENAME)
    current_process_owns_lock = bool(process_lock)

    process_manager = setup_process_manager(root_state_dir, ProcessKind.GUI, current_process_owns_lock)

    load_logger_config('tribler-gui', root_state_dir, current_process_owns_lock)

    # Enable tracer using commandline args: --trace-debug or --trace-exceptions
    trace_logger = check_and_enable_code_tracing('gui', root_state_dir)

    enable_fault_handler(root_state_dir)
    # Exit if we cant read/write files, etc.
    check_environment()
    check_free_space(root_state_dir)

    try:
        app_name = os.environ.get('TRIBLER_APP_NAME', 'triblerapp')
        app = TriblerApplication(app_name, sys.argv, start_local_server=current_process_owns_lock)
        app_manager = AppManager(app)

        # Note (@ichorid): translator MUST BE created and assigned to a separate variable
        # before calling installTranslator on app. Otherwise, it won't work for some reason
        settings = QSettings('nl.tudelft.tribler')
        translator = get_translator(settings.value('translation', None))
        app.installTranslator(translator)

        if not current_process_owns_lock:
            msg = 'Tribler GUI application is already running'
            logger.info(msg)
            app.send_torrent_file_path_to_primary_process()
            logger.info('Close the current GUI application.')
            process_manager.sys_exit(EXITCODE_ANOTHER_GUI_PROCESS_IS_RUNNING, msg)

        logger.info('Start Tribler Window')
        window = TriblerWindow(process_manager, app_manager, settings, root_state_dir,
                               api_port=api_port, api_key=api_key)
        window.setWindowTitle("Tribler")
        app.tribler_window = window
        app.parse_sys_args(sys.argv)
        exit_code = app.exec_()
        process_manager.sys_exit(exit_code or None)

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(exc)
        show_system_popup("Tribler Exception", f"{exc.__class__.__name__}: {exc}")
        process_manager.sys_exit(1, exc)

    except SystemExit:
        logger.info("Shutting down Tribler")
        if trace_logger:
            trace_logger.close()

        # Flush all the logs to make sure it is written to file before it exits
        for handler in logging.getLogger().handlers:
            handler.flush()

        gui_sentry_reporter.global_strategy = SentryStrategy.SEND_SUPPRESSED
        raise
