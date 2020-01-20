import logging.config
import os
import signal
import sys
from asyncio import ensure_future, get_event_loop

import tribler_core
from tribler_core.dependencies import check_for_missing_dependencies

import tribler_gui

# https://github.com/Tribler/tribler/issues/3702
# We need to make sure that anyone running cp65001 can print to the stdout before we print anything.
# Annoyingly cp65001 is not shipped by default, so we add support for it through mapping it to mbcs.
if getattr(sys.stdout, 'encoding', None) == 'cp65001':
    import codecs

    def remapped_mbcs(_):
        mbcs_codec = codecs.lookup('mbcs')
        return codecs.CodecInfo(
            name='cp65001',
            encode=mbcs_codec.encode,
            decode=mbcs_codec.decode,
            incrementalencoder=mbcs_codec.incrementalencoder,
            incrementaldecoder=mbcs_codec.incrementaldecoder,
            streamreader=mbcs_codec.streamreader,
            streamwriter=mbcs_codec.streamwriter,
        )

    codecs.register(remapped_mbcs)


def start_tribler_core(base_path, api_port, api_key):
    """
    This method will start a new Tribler session.
    Note that there is no direct communication between the GUI process and the core: all communication is performed
    through the HTTP API.
    """
    from tribler_core.check_os import check_and_enable_code_tracing, set_process_priority
    tribler_core.load_logger_config()

    from tribler_core.config.tribler_config import TriblerConfig
    from tribler_core.modules.process_checker import ProcessChecker
    from tribler_core.session import Session

    trace_logger = None

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
        config = TriblerConfig()
        global trace_logger

        # Enable tracer if --trace-debug or --trace-exceptions flag is present in sys.argv
        trace_logger = check_and_enable_code_tracing('core')

        priority_order = config.get_cpu_priority_order()
        set_process_priority(pid=os.getpid(), priority_order=priority_order)

        config.set_http_api_port(int(api_port))
        # If the API key is set to an empty string, it will remain disabled
        if config.get_http_api_key() not in ('', api_key):
            config.set_http_api_key(api_key)
            config.write()  # Immediately write the API key so other applications can use it
        config.set_http_api_enabled(True)

        # Check if we are already running a Tribler instance
        process_checker = ProcessChecker(config.get_state_dir())
        if process_checker.already_running:
            return
        process_checker.create_lock_file()

        session = Session(config)

        signal.signal(signal.SIGTERM, lambda signum, stack: shutdown(session, signum, stack))
        await session.start()

    logging.getLogger('asyncio').setLevel(logging.WARNING)
    get_event_loop().create_task(start_tribler())
    get_event_loop().run_forever()


if __name__ == "__main__":
    # Check whether we need to start the core or the user interface
    if 'CORE_PROCESS' in os.environ:
        # Check for missing Core dependencies
        check_for_missing_dependencies(scope='core')

        base_path = os.environ['CORE_BASE_PATH']
        api_port = os.environ['CORE_API_PORT']
        api_key = os.environ['CORE_API_KEY']
        start_tribler_core(base_path, api_port, api_key)
    else:
        # Set up logging
        tribler_gui.load_logger_config()

        # Check for missing both(GUI, Core) dependencies
        check_for_missing_dependencies(scope='both')

        # Do imports only after dependencies check
        from tribler_core.check_os import check_and_enable_code_tracing, check_environment, check_free_space, enable_fault_handler, \
            error_and_exit, should_kill_other_tribler_instances
        from tribler_core.exceptions import TriblerException

        try:
            # Enable tracer using commandline args: --trace-debug or --trace-exceptions
            trace_logger = check_and_enable_code_tracing('gui')

            enable_fault_handler()

            # Exit if we cant read/write files, etc.
            check_environment()

            should_kill_other_tribler_instances()

            check_free_space()

            from tribler_gui.tribler_app import TriblerApplication
            from tribler_gui.tribler_window import TriblerWindow

            app_name = os.environ.get('TRIBLER_APP_NAME', 'triblerapp')
            app = TriblerApplication(app_name, sys.argv)
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
