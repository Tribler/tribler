import re
import sys
import time
from unittest.mock import Mock, patch

import pytest

from tribler.core.utilities.slow_coro_detection.main_thread_stack_tracking import (
    StackFrameInfo, _get_main_thread_stack_info, get_main_thread_stack, main_stack_tracking_is_enabled,
    main_thread_profile,
    start_main_thread_stack_tracing,
    stop_main_thread_stack_tracing
)


def test_main_thread_profile():
    frame = Mock()
    arg = Mock()
    stack = []

    with patch('tribler.core.utilities.slow_coro_detection.main_thread_stack_tracking._main_thread_stack', stack):
        assert not stack

        result = main_thread_profile(frame, 'call', arg, now=lambda: 123)
        assert result is main_thread_profile
        assert stack == [(frame, 123)]

        result = main_thread_profile(frame, 'return', arg)
        assert result is main_thread_profile
        assert not stack


def test_main_stack_tracking_is_activated():
    assert not main_stack_tracking_is_enabled()
    activated_profiler = start_main_thread_stack_tracing()
    assert main_stack_tracking_is_enabled()
    deactivated_profiler = stop_main_thread_stack_tracing()
    assert not main_stack_tracking_is_enabled()
    assert activated_profiler is deactivated_profiler


def test_get_main_thread_stack_info():
    frame1 = Mock(f_lineno=111, f_code=Mock(co_name='CO_NAME1', co_filename='CO_FILENAME1'))
    frame2 = Mock(f_lineno=222, f_code=Mock(co_name='CO_NAME2', co_filename='CO_FILENAME2'))
    start_time_1 = time.time() - 2
    start_time_2 = time.time() - 1

    stack = [(frame1, start_time_1), (frame2, start_time_2)]

    prev_switch_interval = sys.getswitchinterval()
    test_switch_interval = 10.0
    assert prev_switch_interval != pytest.approx(test_switch_interval, abs=0.01)
    sys.setswitchinterval(test_switch_interval)

    with patch('tribler.core.utilities.slow_coro_detection.main_thread_stack_tracking._main_thread_stack', stack):
        stack_info = _get_main_thread_stack_info()

    assert stack_info == [StackFrameInfo(func_name='CO_NAME1', file_name='CO_FILENAME1', line_number=111,
                                         start_time=start_time_1, is_under_profiling=False),
                          StackFrameInfo(func_name='CO_NAME2', file_name='CO_FILENAME2', line_number=222,
                                         start_time=start_time_2, is_under_profiling=False)]
    assert sys.getswitchinterval() == pytest.approx(test_switch_interval, abs=0.01)
    sys.setswitchinterval(prev_switch_interval)


def test_get_main_thread_stack():
    t = time.time()
    stack_info = [
        # This line is cut from the output because of limit=2
        StackFrameInfo(func_name='CO_NAME1', file_name='CO_FILENAME1', line_number=111, start_time=t-4),

        StackFrameInfo(func_name='CO_NAME2', file_name='CO_FILENAME2', line_number=222, start_time=t-3),
        StackFrameInfo(func_name='CO_NAME3', file_name='CO_FILENAME3', line_number=333, start_time=t-2),

        # This line is cut from the traceback because we want to see the line where the last slow function is called,
        # not the line inside the last slow function
        StackFrameInfo(func_name='CO_NAME4', file_name='CO_FILENAME4', line_number=444, start_time=t-1),

        # This function is fast and not added to the stack
        StackFrameInfo(func_name='CO_NAME5', file_name='CO_FILENAME5', line_number=555, start_time=t-0.02),

        # This function is fast and not added to the stack
        StackFrameInfo(func_name='CO_NAME6', file_name='CO_FILENAME6', line_number=666, start_time=t-0.01)
    ]
    with patch('tribler.core.utilities.slow_coro_detection.main_thread_stack_tracking._get_main_thread_stack_info',
               return_value=stack_info):
        with patch('linecache.getline', side_effect=['line1', 'line2', 'line3', 'line4', 'line5']):
            stack_str = get_main_thread_stack(stack_cut_duration=0.5, limit=2)

    traceback_re = re.compile(r'Traceback \(most recent call last\):\n'
                              r'  File "CO_FILENAME2", line 222, in CO_NAME2 \(function started [0-9.]* seconds ago\)\n'
                              r'    line2\n'
                              r'  File "CO_FILENAME3", line 333, in CO_NAME3 \(function started [0-9.]* seconds ago\)\n'
                              r'    line3\n')
    assert traceback_re.match(stack_str)
