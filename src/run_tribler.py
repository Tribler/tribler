import asyncio
import logging.config
import os
import signal
import sys
from asyncio import ensure_future, get_event_loop

import tribler_core
from tribler_core.config.tribler_config import CONFIG_FILENAME
from tribler_core.dependencies import check_for_missing_dependencies
from tribler_core.upgrade.version_manager import fork_state_directory_if_necessary, get_versioned_state_directory
from tribler_core.utilities.osutils import get_root_state_directory
from tribler_core.version import version_id

import tribler_gui


def start_tribler_core(base_path, api_port, api_key, root_state_dir, core_test_mode=False):
    """
    This method will start a new Tribler session.
    Note that there is no direct communication between the GUI process and the core: all communication is performed
    through the HTTP API.
    """
    from tribler_core.check_os import check_and_enable_code_tracing, set_process_priority
    tribler_core.load_logger_config(root_state_dir)

    from tribler_core.config.tribler_config import TriblerConfig
    from tribler_core.modules.process_checker import ProcessChecker
    from tribler_core.session import Session

    trace_logger = None

    # TODO for the moment being, we use the SelectorEventLoop on Windows, since with the ProactorEventLoop, ipv8
    # peer discovery becomes unstable. Also see issue #5485.
    if sys.platform.startswith('win'):
        asyncio.set_event_loop(asyncio.SelectorEventLoop())

    def on_tribler_shutdown(future):
        future.result()
        get_event_loop().stop()
        if trace_logger:
            trace_logger.close()

    def shutdown(session, *_):
        logging.info("Stopping Tribler core")
        ensure_future(session.shutdown()).add_done_callback(on_tribler_shutdown)

    sys.path.insert(0, base_path)

    async def start_tribler():
        # Check if we are already running a Tribler instance
        process_checker = ProcessChecker(root_state_dir)
        if process_checker.already_running:
            return
        process_checker.create_lock_file()

        # Before any upgrade, prepare a separate state directory for the update version so it does not
        # affect the older version state directory. This allows for safe rollback.
        fork_state_directory_if_necessary(root_state_dir, version_id)

        state_dir = get_versioned_state_directory(root_state_dir)

        config = TriblerConfig(state_dir, config_file=state_dir / CONFIG_FILENAME)
        config.set_api_http_port(int(api_port))
        # If the API key is set to an empty string, it will remain disabled
        if config.get_api_key() not in ('', api_key):
            config.set_api_key(api_key)
            config.write()  # Immediately write the API key so other applications can use it
        config.set_api_http_enabled(True)

        priority_order = config.get_cpu_priority_order()
        set_process_priority(pid=os.getpid(), priority_order=priority_order)

        global trace_logger
        # Enable tracer if --trace-debug or --trace-exceptions flag is present in sys.argv
        trace_logger = check_and_enable_code_tracing('core', config.get_log_dir())

        session = Session(config, core_test_mode=core_test_mode)

        signal.signal(signal.SIGTERM, lambda signum, stack: shutdown(session, signum, stack))
        await session.start()

    logging.getLogger('asyncio').setLevel(logging.WARNING)
    get_event_loop().create_task(start_tribler())
    get_event_loop().run_forever()


if __name__ == "__main__":
    # Get root state directory (e.g. from environment variable or from system default)
    root_state_dir = get_root_state_directory()

    # Check whether we need to start the core or the user interface
    if 'CORE_PROCESS' in os.environ:
        # Check for missing Core dependencies
        check_for_missing_dependencies(scope='core')

        base_path = os.environ['CORE_BASE_PATH']
        api_port = os.environ['CORE_API_PORT']
        api_key = os.environ['CORE_API_KEY']
        core_test_mode = bool(os.environ.get("TRIBLER_CORE_TEST_MODE", False))

        start_tribler_core(base_path, api_port, api_key, root_state_dir, core_test_mode=core_test_mode)
    else:
        # Set up logging
        tribler_gui.load_logger_config(root_state_dir)

        # Check for missing both(GUI, Core) dependencies
        check_for_missing_dependencies(scope='both')

        # Do imports only after dependencies check
        from tribler_core.check_os import check_and_enable_code_tracing, check_environment, check_free_space, \
            enable_fault_handler, error_and_exit, should_kill_other_tribler_instances
        from tribler_core.exceptions import TriblerException

        try:
            # Enable tracer using commandline args: --trace-debug or --trace-exceptions
            trace_logger = check_and_enable_code_tracing('gui', root_state_dir)

            enable_fault_handler(root_state_dir)

            # Exit if we cant read/write files, etc.
            check_environment()

            should_kill_other_tribler_instances()

            check_free_space()

            from tribler_gui.tribler_app import TriblerApplication
            from tribler_gui.tribler_window import TriblerWindow

            app_name = os.environ.get('TRIBLER_APP_NAME', 'triblerapp')
            app = TriblerApplication(app_name, sys.argv)
            app.installTranslator(app.translator)

            if app.is_running():
                for arg in sys.argv[1:]:
                    if os.path.exists(arg) and arg.endswith(".torrent"):
                        app.send_message(f"file:{arg}")
                    elif arg.startswith('magnet'):
                        app.send_message(arg)
                sys.exit(1)

            window = TriblerWindow()
            window.setWindowTitle("Tribler")
            app.set_activation_window(window)
            app.parse_sys_args(sys.argv)
            sys.exit(app.exec_())

        except ImportError as ie:
            logging.exception(ie)
            error_and_exit("Import Error", f"Import error: {ie}")

        except TriblerException as te:
            logging.exception(te)
            error_and_exit("Tribler Exception", f"{te}")

        except SystemExit:
            logging.info("Shutting down Tribler")
            if trace_logger:
                trace_logger.close()
            # Flush all the logs to make sure it is written to file before it exits
            for handler in logging.getLogger().handlers:
                handler.flush()
            raise
