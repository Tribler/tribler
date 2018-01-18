import logging
import os
import sys
import tempfile

from Tribler.Core.Config.tribler_config import TriblerConfig


def error_and_exit(title, main_text):
    """
    Show a pop-up window and sys.exit() out of Python.

    :param title: the short error description
    :param main_text: the long error description
    """
    # NOTE: We don't want to load all of these imports normally.
    #       Otherwise we will have these unused GUI modules loaded in the main process.
    from Tkinter import Tk, Canvas, DISABLED, INSERT, Label, Text, WORD

    root = Tk()
    root.wm_title("Tribler: Critical Error!")
    root.wm_minsize(500, 300)
    root.wm_maxsize(500, 300)
    root.configure(background='#535252')

    # Place the window at the center
    root.update_idletasks()
    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()
    size = tuple(int(_) for _ in root.geometry().split('+')[0].split('x'))
    x = w / 2 - 250
    y = h / 2 - 150
    root.geometry("%dx%d+%d+%d" % (size + (x, y)))

    Canvas(root, width=500, height=50, bd=0, highlightthickness=0, relief='ridge', background='#535252').pack()
    pane = Canvas(root, width=400, height=200, bd=0, highlightthickness=0, relief='ridge', background='#333333')
    Canvas(pane, width=400, height=20, bd=0, highlightthickness=0, relief='ridge', background='#333333').pack()
    Label(pane, text=title, width=40, background='#333333', foreground='#fcffff', font=("Helvetica", 11)).pack()
    Canvas(pane, width=400, height=20, bd=0, highlightthickness=0, relief='ridge', background='#333333').pack()

    main_text_label = Text(pane, width=45, height=6, bd=0, highlightthickness=0, relief='ridge', background='#333333',
                           foreground='#b5b5b5', font=("Helvetica", 11), wrap=WORD)
    main_text_label.tag_configure("center", justify='center')
    main_text_label.insert(INSERT, main_text)
    main_text_label.tag_add("center", "1.0", "end")
    main_text_label.config(state=DISABLED)
    main_text_label.pack()

    pane.pack()

    root.mainloop()

    # Exit the program
    sys.exit(1)


def check_read_write():
    """
    Check if we have access to file IO, or exit with an error.
    """
    try:
        tempfile.gettempdir()
    except IOError:
        error_and_exit("No write access!",
                       "Tribler does not seem to be able to have access to your filesystem. " +
                       "Please grant Tribler the proper permissions and try again.")


def check_environment():
    """
    Perform all of the pre-Tribler checks to see if we can run on this platform.
    """
    check_read_write()


def check_free_space():
    try:
        import psutil
        free_space = psutil.disk_usage(".").free/(1024 * 1024.0)
        if free_space < 100:
            error_and_exit("Insufficient disk space",
                           "You have less than 100MB of usable disk space. " +
                           "Please free up some space and run Tribler again.")
    except ImportError as ie:
        error_and_exit("Import Error", "Import error: {0}".format(ie))


def setup_gui_logging():
    setup_logging(gui=True)


def setup_core_logging():
    setup_logging(gui=False)


def setup_logging(gui=False):
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

    log_directory = TriblerConfig().get_log_dir()

    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    info_filename = 'tribler-gui-info.log' if gui else 'tribler-core-info.log'
    error_filename = 'tribler-gui-error.log' if gui else 'tribler-core-error.log'

    logging.info_log_file = os.path.join(log_directory, info_filename)
    logging.error_log_file = os.path.join(log_directory, error_filename)
    logging.config.fileConfig(log_config, disable_existing_loggers=False)
