import linecache
import sys
import time
from types import FrameType
from typing import Callable, List, Optional, Tuple

from tribler.core.utilities.slow_coro_detection import logger

# The default interval Python uses to switch threads is 0.005 seconds. When obtaining the main stack,
# the _get_main_thread_stack_info() function temporarily switches it to a much bigger value of 0.1 seconds
# to prevent a thread switch at that moment, so the debug thread can copy the main_thread_stack list content
# without interruption.
SWITCH_INTERVAL = 0.1


_main_thread_stack_tracking_is_enabled: bool = False


# If the main thread stack tracing is enabled, the list contains frames for stack of the main thread.
# The second element of a tuple is a frame's start time. We use tuple and not dataclass here for performance reasons.
_main_thread_stack: List[Tuple[FrameType, float]] = []


def main_stack_tracking_is_enabled() -> bool:
    return _main_thread_stack_tracking_is_enabled


def main_thread_profile(frame: FrameType, event: str, _, now=time.time):
    """
    A hook that calls before and after a function call in the main thread if the stack tracking is activated
    """
    if event == 'call':
        _main_thread_stack.append((frame, now()))
    elif event == 'return' and _main_thread_stack:
        # Usually, 'call' and 'return' are always paired, so 'return' removes the frame added by the previous 'call'.
        # But at the very beginning, when the `start_main_thread_stack_tracing` function is called, we are already
        # inside the function, so we get unpaired `return` when we exit from the function. At that moment, the stack
        # is empty. By checking that the stack can be empty, we handle this situation by ignoring the unpaired 'return'.
        _main_thread_stack.pop()
    return main_thread_profile


def start_main_thread_stack_tracing() -> Callable:
    """
    Activates the profiler hook in the main thread. Note that it makes Python functions about two times slower.
    The compiled code is run as fast, so libtorrent calls and database queries should be as efficient as before.

    Returns the profiler function (for testing purpose)
    """
    logger.info('Start tracing of coroutine stack to show stack for slow coroutines (makes code execution slower)')
    global _main_thread_stack_tracking_is_enabled  # pylint: disable=global-statement
    _main_thread_stack_tracking_is_enabled = True
    sys.setprofile(main_thread_profile)
    return main_thread_profile


def stop_main_thread_stack_tracing() -> Callable:
    """
    Deactivates the profiler hook in the main thread.
    Returns the previous profiler function (for testing purpose)
    """
    previous_profiler = sys.getprofile()
    sys.setprofile(None)
    global _main_thread_stack_tracking_is_enabled  # pylint: disable=global-statement
    _main_thread_stack_tracking_is_enabled = False
    return previous_profiler


def _get_main_thread_stack_info() -> List[Tuple[str, str, Optional[int], float]]:
    """
    Quickly copies necessary information from the main thread stack, so it is possible later to format a usual
    traceback in a separate thread.

    The function temporarily changes the interpreter’s thread switch interval to prevent thread switch during
    the stack copying. It is a lighter analogue of holding the GIL (Global Interpreter Lock).
    """
    previous_switch_interval = sys.getswitchinterval()
    sys.setswitchinterval(SWITCH_INTERVAL)
    try:
        stack_info = [(frame.f_code.co_name, frame.f_code.co_filename, frame.f_lineno, start_time)
                      for frame, start_time in _main_thread_stack]
    finally:
        sys.setswitchinterval(previous_switch_interval)
    return stack_info


def get_main_thread_stack(stack_cut_duration: Optional[float] = None, limit: Optional[int] = None) -> str:
    """
    Obtains the main thread stack and format it in a usual way.
    """
    traceback_items = []
    stack_info = _get_main_thread_stack_info()
    now = time.time()
    for func_name, file_name, line_number, start_time in stack_info:
        duration = now - start_time
        source_line = (linecache.getline(file_name, line_number).strip() if line_number else '') or '?'
        traceback_item = f'  File "{file_name}", line {line_number or "?"}' \
                         f', in {func_name} (function started {duration:.3f} seconds ago)\n' \
                         f'    {source_line}'

        if stack_cut_duration is not None and duration < stack_cut_duration:
            # On this stack level, the function's call duration is insignificant, indicating that it isn't related
            # to the current freeze. Thus, this stack level and the nested ones are omitted from the traceback
            # to prevent any misinterpretation.

            # The execution time of the previous frame is significantly long. However, the exact code line
            # being executed within the function isn't as relevant and may misdirect the reader. Hence,
            # the last stack frame is removed. The final line in the traceback will then display the code line
            # that initiated the current function rather than the specific line within it. As a result,
            # in the last code line, a reader sees the name of the function that should be optimized.
            if traceback_items:
                traceback_items.pop()

            break

        traceback_items.append(traceback_item)

    if limit:
        traceback_items = traceback_items[-limit:]

    traceback_str = '\n'.join(traceback_items) + '\n'
    return f"Traceback (most recent call last):\n{traceback_str}"
