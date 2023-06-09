import cProfile
import logging
import pstats
import io
import sys
import time
from functools import wraps
from types import FunctionType
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def profile(func: Optional[FunctionType] = None, /, *,
            sort_order: pstats.SortKey = pstats.SortKey.TIME, threshold_duration: float = 0.1):
    """
    Enables profiling for the wrapped function.

    Example 1:
        >>> @profile:
        ... def my_function():
                ...

    Example 2:
        >>> @profile(threshold_duration=1.0):
        ... def my_function():
                ...

    Args:
        func: positional-only argument for a function, used when the decorator is specified without parentheses;
        sort_order: how to sort the output, by default it's the time inside the function itself without nested calls;
        threshold_duration: do not print statistics if the function executed faster than the threshold duration.
    """
    def profile_decorator(func: FunctionType):
        @wraps(func)
        def profile_wrapper(*args, **kwargs):
            profiler = cProfile.Profile()

            prev_profiler = sys.getprofile()
            sys.setprofile(None)
            try:
                t = time.time()

                profiler.enable()
                try:
                    result = func(*args, **kwargs)
                finally:
                    profiler.disable()

                duration = time.time() - t
            finally:
                # To be able to combine the @profile decorator with the main thread stack tracing
                sys.setprofile(prev_profiler)

            if duration < threshold_duration:
                logger.info(f'Profiled function `{func.__name__}` executed in {duration:.3f} seconds')
            else:
                stats = _get_statistics(profiler, sort_order)
                logger.info(f'Profiled results for `{func.__name__}`:\n{stats}')

            return result

        return profile_wrapper

    if func is not None:
        return profile_decorator(func)

    return profile_decorator


def _get_statistics(profiler: cProfile.Profile, sort_order: pstats.SortKey) -> str:
    stream = io.StringIO()
    ps = pstats.Stats(profiler, stream=stream).sort_stats(sort_order.value)
    _fix_fcn_list(ps)
    ps.print_stats()
    return stream.getvalue()


def _fix_fcn_list(stats: pstats.Stats):
    # The function fixes two problems with the default statistics output:
    # 1. The default list of the function is very long, and most functions have an execution time of 0.000.
    #    Let's remove fast functions to make statistics easier to read and make an accent on slow functions
    # 2. Some dynamically generated functions have a weird multi-line name that includes the function source code;
    #    these function names make the resulting table hard to read and understand. Let's simplify them a bit.
    prev_func_list: List[Tuple[str, int, str]] = getattr(stats, 'fcn_list', [])
    if not prev_func_list:
        return  # pragma: no cover  # should not happen, added for extra safety

    new_func_list: List[Tuple[str, int, str]] = []

    stats_dict: dict = getattr(stats, 'stats', {})
    for func_tuple in prev_func_list:
        stat = stats_dict.get(func_tuple)
        if stat is None:
            continue  # pragma: no cover  # Should not happen, added for extra safety

        cumulative_time = stat[3]
        if cumulative_time < 0.0005:
            continue  # The function is fast and its time will be displayed as 0.000, remove it to simplify statistics

        func_file_name = func_tuple[0]
        if '\n' in func_file_name:  # pragma: no cover  # tested manually
            # The function is dynamically generated and have a weird multi-line name that makes statistics looks weird.
            # Replace it with a shorter single-line name. Add a hash to the name to distinct theoretical duplicates.
            fixed_file_name = func_file_name.strip().partition('\n')[0][:20] + f'... (name hash {id(func_file_name)})'
            fixed_func_tuple = (fixed_file_name,) + func_tuple[1:]
            stats_dict[fixed_func_tuple] = stats_dict[func_tuple]  # copy statistics from the old name to the new name
            func_tuple = fixed_func_tuple

        new_func_list.append(func_tuple)
    stats.fcn_list = new_func_list
