import os
import sys
import multiprocessing
import logging.config

from check_os import check_environment, check_free_space, error_and_exit, setup_gui_logging, \
    should_kill_other_tribler_instances


if __name__ == "__main__":
    # Exit if we cant read/write files, etc.
    check_environment()

    multiprocessing.freeze_support()

    should_kill_other_tribler_instances()

    check_free_space()

    # Set up logging
    setup_gui_logging()

    try:
        from TriblerGUI.tribler_app import TriblerApplication
        from TriblerGUI.tribler_window import TriblerWindow

        app = TriblerApplication("triblerapp", sys.argv)

        if app.is_running():
            for arg in sys.argv[1:]:
                if os.path.exists(arg):
                    app.send_message("file:%s" % arg)
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
        error_and_exit("Import Error", "Import error: {0}".format(ie))

    except SystemExit as se:
        logging.info("Shutting down Tribler")
        # Flush all the logs to make sure it is written to file before it exits
        for handler in logging.getLogger().handlers:
            handler.flush()
        raise
