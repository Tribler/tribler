import logging.config
import os
import psutil
import subprocess
import sys
import tempfile

from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.Modules.process_checker import ProcessChecker

FORCE_RESTART_MESSAGE = "A Tribler instance is already running. Do you want to force restart? " \
                        "\n\nCaution: force restart could result in data corruption."

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


def get_existing_tribler_pids():
    """ Get PID of all existing instances excluding the current one """
    pids = []
    if sys.platform == 'linux2':
        for proc in subprocess.check_output(['ps', '-ef']).splitlines():
            if 'python' in proc and 'run_tribler.py' in proc:
                pids += [int(proc.split()[1])]
    elif sys.platform == 'win32':
        pids = [int(item.split()[1]) for item in os.popen('tasklist').read().splitlines()[4:] if
                'tribler.exe' in item.split()]
    elif sys.platform == 'darwin':
        tribler_executable_partial_path = "Tribler.app/Contents/MacOS/tribler".lower()
        for proc in subprocess.check_output(['ps', '-ef']).splitlines():
            if tribler_executable_partial_path in proc.lower() or ('python' in proc and 'run_tribler.py' in proc):
                pids += [int(proc.split()[1])]

    # Remove the current instance PID from this list
    current_pid = os.getpid()
    # In Mac, there are two processes spawned somehow with consecutive pids, if so remove it from the list
    current_pid_list = [current_pid, current_pid - 1, current_pid + 1]
    for new_pid in current_pid_list:
        if new_pid in pids:
            pids.remove(new_pid)

    # Get core process PID from the lock file (if any) and add it to the PID list
    process_checker = ProcessChecker()
    if process_checker.already_running:
        core_pid = process_checker.get_pid_from_lock_file()
        if core_pid not in pids:
            pids.append(int(core_pid))

    return pids


def should_kill_other_tribler_instances():
    """ Asks user whether to force restart Tribler if there is more than one instance running.
        This will help user to kill any zombie instances which might have been left behind from
        previous force kill command or some other unexpected exceptions and relaunch Tribler again.
        It ignores if Tribler is opened with some arguments, for eg. with a torrent.
     """
    # If there are cmd line args, let existing instance handle it
    if len(sys.argv) > 1:
        return

    # Get PIDs of existing tribler instance
    pids = get_existing_tribler_pids()

    # If the PID list is not empty, then there is another Tribler instance running
    # Ask user whether to force restart
    if pids:
        import Tkinter
        import tkMessageBox
        window = Tkinter.Tk()
        window.withdraw()
        result = tkMessageBox.askquestion("Warning", FORCE_RESTART_MESSAGE, icon='warning')
        if result == 'yes':
            for pid in pids:
                os.kill(pid, 9)
            window.update()
            window.quit()

            # Restart Tribler properly
            restart_tribler_properly()
        else:
            window.update()
            window.quit()
            sys.exit(0)


def restart_tribler_properly():
    """
    Restarting Tribler with proper cleanup of file objects and descriptors
    """
    try:
        process = psutil.Process(os.getpid())
        for handler in process.open_files() + process.connections():
            os.close(handler.fd)
    except Exception as e:
        # If exception occurs on cleaning up the resources, simply log it and continue with the restart
        logging.error(e)

    python = sys.executable
    os.execl(python, python, *sys.argv)


def set_process_priority(pid=None, priority_order=1):
    """
    Sets process priority based on order provided. Note order range is 0-5 and higher value indicates higher priority.
    :param pid: Process ID or None. If None, uses current process.
    :param priority_order: Priority order (0-5). Higher value means higher priority.
    """
    if priority_order < 0 or priority_order > 5:
        return

    process = psutil.Process(pid if pid else os.getpid())

    if sys.platform == 'win32':
        priority_classes = [psutil.IDLE_PRIORITY_CLASS,
                            psutil.BELOW_NORMAL_PRIORITY_CLASS,
                            psutil.NORMAL_PRIORITY_CLASS,
                            psutil.ABOVE_NORMAL_PRIORITY_CLASS,
                            psutil.HIGH_PRIORITY_CLASS,
                            psutil.REALTIME_PRIORITY_CLASS]
        process.nice(priority_classes[priority_order])
    elif sys.platform == 'darwin' or sys.platform == 'linux2':
        # On Unix, priority can be -20 to 20, but usually not allowed to set below 0, we set our classes somewhat in
        # that range.
        priority_classes = [15, 12, 10, 4, 1, 0]
        process.nice(priority_classes[priority_order])


def enable_fault_handler():
    """
    Enables fault handler if the module is available.
    """
    try:
        import faulthandler

        log_dir = TriblerConfig().get_log_dir()
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        crash_file = os.path.join(log_dir, "crash-report.log")
        faulthandler.enable(file=open(crash_file, "w"), all_threads=True)
    except ImportError:
        logging.error("Fault Handler module not found.")
