import logging
import os
import sys
import tempfile
import time
import traceback

import psutil

from tribler.core.utilities.utilities import show_system_popup

logger = logging.getLogger(__name__)


def error_and_exit(title, main_text):
    """
    Show a pop-up window and sys.exit() out of Python.

    :param title: the short error description
    :param main_text: the long error description
    """
    show_system_popup(title, main_text)

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
    logger.info('Check environment')
    check_read_write()


def check_free_space():
    logger.info('Check free space')
    try:
        free_space = psutil.disk_usage(".").free / (1024 * 1024.0)
        if free_space < 100:
            error_and_exit("Insufficient disk space",
                           "You have less than 100MB of usable disk space. " +
                           "Please free up some space and run Tribler again.")
    except ImportError as ie:
        logger.error(ie)
        error_and_exit("Import Error", f"Import error: {ie}")


def set_process_priority(pid=None, priority_order=1):
    """
    Sets process priority based on order provided. Note order range is 0-5 and higher value indicates higher priority.
    :param pid: Process ID or None. If None, uses current process.
    :param priority_order: Priority order (0-5). Higher value means higher priority.
    """
    if priority_order < 0 or priority_order > 5:
        return
    if sys.platform not in {'win32', 'darwin', 'linux'}:
        return

    if sys.platform == 'win32':
        priority_classes = [
            psutil.IDLE_PRIORITY_CLASS,
            psutil.BELOW_NORMAL_PRIORITY_CLASS,
            psutil.NORMAL_PRIORITY_CLASS,
            psutil.ABOVE_NORMAL_PRIORITY_CLASS,
            psutil.HIGH_PRIORITY_CLASS,
            psutil.REALTIME_PRIORITY_CLASS
        ]
    else:
        # On Unix, priority can be -20 to 20, but usually not allowed to set below 0, we set our classes somewhat in
        # that range.
        priority_classes = [5, 4, 3, 2, 1, 0]

    try:
        process = psutil.Process(pid if pid else os.getpid())
        process.nice(priority_classes[priority_order])
    except psutil.Error as e:
        logger.exception(e)


def enable_fault_handler(log_dir):
    """
    Enables fault handler if the module is available.
    """
    logger.info(f'Enable fault handler: "{log_dir}"')
    try:
        import faulthandler

        if not log_dir.exists():
            log_dir.mkdir(parents=True, exist_ok=True)
        crash_file = log_dir / "crash-report.log"
        faulthandler.enable(file=open(str(crash_file), "w"), all_threads=True)
    except ImportError:
        logger.error("Fault Handler module not found.")


def check_and_enable_code_tracing(process_name, log_dir):
    """
    Checks and enable trace logging if --trace-exception or --trace-debug system flag is present.
    :param process_name: used as prefix for log file
    :return: Log file handler
    """
    logger.info(f'Check and enable code tracing. Process name: "{process_name}". '
                f'Log dir: "{log_dir}"')

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
            trace_line = f"[{time.time()}] {func_filename}:{func_name}, " \
                         f"line {func_line_no} called from {caller_filename}, line {caller_line_no}\n"
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
        trace_line = f"[{time.time()}] Exception: {func_filename}, line {func_line_no} " \
                     f"\n{exc_type.__name__} {exc_value} " \
                     f"\n{''.join(traceback.format_tb(exc_traceback))}"
        file_handler.write(trace_line)
        file_handler.flush()
