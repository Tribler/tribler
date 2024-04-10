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
    if not isinstance(task, Task) and func.__class__.__name__ not in {"TaskWakeupMethWrapper", "task_wakeup"}:
        return repr(func)

    task_repr = repr(task) if task is not None else repr(func)

    if not include_stack:
        return task_repr

    if main_stack_tracking_is_enabled():
        stack = get_main_thread_stack(stack_cut_duration, limit, enable_profiling_tip)
    else:
        stack = 'Set SLOW_CORO_STACK_TRACING=1 to see the coroutine stack'

    return f"{task_repr}\n{stack}"
