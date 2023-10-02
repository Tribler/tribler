import io
from asyncio import Handle, Task
from typing import Optional

# pylint: disable=protected-access


from tribler.core.utilities.slow_coro_detection.main_thread_stack_tracking import get_main_thread_stack, \
    main_stack_tracking_is_enabled


def format_info(handle: Handle, include_stack: bool = False, stack_cut_duration: Optional[float] = None,
                limit: Optional[int] = None, enable_profiling_tip: bool = True) -> str:
    """
    Returns the representation of a task executed by asyncio, with or without the stack.
    """
    func = handle._callback
    task: Task = getattr(func, '__self__', None)
    if not isinstance(task, Task):
        return repr(func)

    if not include_stack:
        return repr(task)

    if not main_stack_tracking_is_enabled():
        stream = io.StringIO()
        try:
            task.print_stack(limit=limit, file=stream)
        except Exception as e:  # pylint: disable=broad-except
            stack = f'Stack is unavailable: {e.__class__.__name__}: {e}'
        else:
            stack = stream.getvalue()
    else:
        stack = get_main_thread_stack(stack_cut_duration, limit, enable_profiling_tip)
    return f"{task}\n{stack}"
