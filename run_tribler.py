import os
import sys
import multiprocessing
import logging.config

from check_os import check_environment
from check_os import error_and_exit


def setup_logging():
    """
    Setup logging to write logs to files inside \
    .Tribler directory in each platforms
    """
    # First check if logger.conf is present or not
    base_path = getattr(sys, '_MEIPASS') if hasattr(sys, '_MEIPASS') else os.path.dirname(__file__)
    log_config = os.path.join(base_path, "logger.conf")

    if not os.path.exists(log_config):
        print "Log configuration file not found at location '%s'" % log_config
        return

    log_directory = os.path.abspath(os.environ.get('APPDATA', os.path.expanduser('~')))
    log_directory = os.path.join(log_directory, '.Tribler', 'logs')

    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    logging.info_log_file = '%s/tribler-info.log' % log_directory
    logging.error_log_file = '%s/tribler-error.log' % log_directory
    logging.config.fileConfig(log_config, disable_existing_loggers=False)


if __name__ == "__main__":
    # Exit if we cant read/write files, etc.
    check_environment()

    multiprocessing.freeze_support()

    # Set up logging
    setup_logging()

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
