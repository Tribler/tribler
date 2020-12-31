import logging
import os
import sys
import tempfile
import time
import traceback

import psutil

from tribler_core.dependencies import _show_system_popup
from tribler_core.modules.process_checker import ProcessChecker
from tribler_core.utilities import path_util

FORCE_RESTART_MESSAGE = "An existing Tribler core process (PID:%s) is already running. \n\n" \
                        "Do you want to stop the process and do a clean restart instead?"


def error_and_exit(title, main_text):
    """
    Show a pop-up window and sys.exit() out of Python.

    :param title: the short error description
    :param main_text: the long error description
    """
    _show_system_popup(title, main_text)

    # Exit the program
    sys.exit(1)


def check_read_write():
    """
    Check if we have access to file IO, or exit with an error.
    """
    try:
        tempfile.gettempdir()
    except OSError:
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
        free_space = psutil.disk_usage(".").free/(1024 * 1024.0)
        if free_space < 100:
            error_and_exit("Insufficient disk space",
                           "You have less than 100MB of usable disk space. " +
                           "Please free up some space and run Tribler again.")
    except ImportError as ie:
        error_and_exit("Import Error", f"Import error: {ie}")


def get_existing_tribler_pid():
    """ Get PID of existing instance if present from the lock file (if any)"""
    process_checker = ProcessChecker()
    if process_checker.already_running:
        return process_checker.get_pid_from_lock_file()
    return -1


def should_kill_other_tribler_instances():
    """ Asks user whether to force restart Tribler if there is more than one instance running.
        This will help user to kill any zombie instances which might have been left behind from
        previous force kill command or some other unexpected exceptions and relaunch Tribler again.
        It ignores if Tribler is opened with some arguments, for eg. with a torrent.
     """
    # If there are cmd line args, let existing instance handle it
    if len(sys.argv) > 1:
        return

    old_pid = get_existing_tribler_pid()
    current_pid = os.getpid()

    if current_pid != old_pid and old_pid > 0:
        # If the old process is a zombie, simply kill it and restart Tribler
        old_process = psutil.Process(old_pid)
        if old_process.status() == psutil.STATUS_ZOMBIE:
            kill_tribler_process(old_process)
            restart_tribler_properly()
            return

        from PyQt5.QtWidgets import QApplication, QMessageBox
        app = QApplication(sys.argv)  # pylint: disable=W0612
        message_box = QMessageBox()
        message_box.setWindowTitle("Warning")
        message_box.setText("Warning")
        message_box.setInformativeText(FORCE_RESTART_MESSAGE % old_pid)
        message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        message_box.setDefaultButton(QMessageBox.Save)
        result = message_box.exec_()

        if result == QMessageBox.Yes:
            kill_tribler_process(old_process)
            restart_tribler_properly()
        else:
            sys.exit(0)


def kill_tribler_process(process):
    """
    Kills the given process if it is a Tribler process.
    :param process: psutil.Process
    :return: None
    """
    def is_tribler_process(name):
        """
        Checks if the given name is of a Tribler processs. It checks a few potential keywords that
        could be present in a Tribler process name across different platforms.
        :param name: Process name
        :return: True if pid is a Tribler process else False
        """
        name = name.lower()
        process_keywords = ['usr/bin/python', 'run_tribler.py', 'tribler.exe', 'tribler.sh',
                            'Contents/MacOS/tribler', 'usr/bin/tribler']
        for keyword in process_keywords:
            if keyword.lower() in name:
                return True
        return False

    try:
        if not is_tribler_process(process.exe()):
            return

        parent_process = process.parent()
        if parent_process.pid > 1 and is_tribler_process(parent_process.exe()):
            os.kill(process.pid, 9)
            os.kill(parent_process.pid, 9)
        else:
            os.kill(process.pid, 9)

    except OSError:
        logging.exception("Failed to kill the existing Tribler process")


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
        priority_classes = [5, 4, 3, 2, 1, 0]
        process.nice(priority_classes[priority_order])


def enable_fault_handler(log_dir):
    """
    Enables fault handler if the module is available.
    """
    try:
        import faulthandler

        if not log_dir.exists():
            path_util.makedirs(log_dir)
        crash_file = log_dir / "crash-report.log"
        faulthandler.enable(file=open(str(crash_file), "w"), all_threads=True)
    except ImportError:
        logging.error("Fault Handler module not found.")


def check_and_enable_code_tracing(process_name, log_dir):
    """
    Checks and enable trace logging if --trace-exception or --trace-debug system flag is present.
    :param process_name: used as prefix for log file
    :return: Log file handler
    """
    trace_logger = None
    if '--trace-exception' in sys.argv[1:]:
        trace_logger = open(log_dir / (f'{process_name}-exceptions.log'), 'w')
        sys.settrace(lambda frame, event, args: trace_calls(trace_logger, frame, event, args,
                                                            filter_exceptions_only=True))
    elif '--trace-debug' in sys.argv[1:]:
        trace_logger = open(log_dir / (f'{process_name}-debug.log'), 'w')
        sys.settrace(lambda frame, event, args: trace_calls(trace_logger, frame, event, args))
    return trace_logger


def trace_calls(file_handler, frame, event, args, filter_exceptions_only=False):
    """
    Trace all Tribler calls as it runs. Useful for debugging.
    Checkout: https://pymotw.com/2/sys/tracing.html
    :param file_handler: File handler where logs will be written to.
    :param frame: Current frame
    :param event: Call event
    :param args: None
    :return: next trace handler
    """
    if event != 'call' or file_handler.closed:
        return

    if not filter_exceptions_only:
        co = frame.f_code
        func_name = co.co_name

        # Ignore write() calls from print statements
        if func_name == 'write':
            return

        func_line_no = frame.f_lineno
        func_filename = co.co_filename

        caller = frame.f_back
        caller_line_no = caller.f_lineno
        caller_filename = caller.f_code.co_filename

        # Only write if callee or caller is Tribler code
        if "tribler" in caller_filename.lower() or "tribler" in func_filename.lower():
            trace_line = "[{}] {}:{}, line {} called from {}, line {}\n".format(
                time.time(), func_filename, func_name, func_line_no,
                caller_filename, caller_line_no)
            file_handler.write(trace_line)
            file_handler.flush()

    return lambda _frame, _event, _args: trace_exceptions(file_handler, _frame, _event, _args)


def trace_exceptions(file_handler, frame, event, args):
    """
    Trace all Tribler exceptions as it runs. Useful for debugging.
    Checkout: https://pymotw.com/2/sys/tracing.html
    :param file_handler: File handler where logs will be written to.
    :param frame: Current frame
    :param event: Exception event
    :param args: exc_type, exc_value, exc_traceback
    :return: None
    """
    if event != 'exception' or file_handler.closed:
        return

    co = frame.f_code
    func_line_no = frame.f_lineno
    func_filename = co.co_filename

    # Only write if exception is originated from Tribler code
    if "tribler" in func_filename.lower():
        exc_type, exc_value, exc_traceback = args
        trace_line = "[{}] Exception: {}, line {} \n{} {} \n{}".format(
            time.time(), func_filename, func_line_no,
            exc_type.__name__, exc_value, "".join(traceback.format_tb(exc_traceback)))
        file_handler.write(trace_line)
        file_handler.flush()
