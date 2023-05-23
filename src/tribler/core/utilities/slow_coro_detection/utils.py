import io
from asyncio import Handle, Task


# pylint: disable=protected-access


from tribler.core.utilities.slow_coro_detection.main_thread_stack_tracking import get_main_thread_stack, \
    main_stack_tracking_is_activated


def format_info(handle: Handle, include_stack: bool = False) -> str:
    """
    Returns the representation of a task executed by asyncio, with or without the stack.
    """
    func = handle._callback
    task: Task = getattr(func, '__self__', None)
    if not isinstance(task, Task):
        return repr(func)

    if not include_stack:
        return repr(task)

    if not main_stack_tracking_is_activated():
        stream = io.StringIO()
        task.print_stack(limit=3, file=stream)
        stack = stream.getvalue()
    else:
        stack = get_main_thread_stack()
    return f"{task}\n{stack}"
