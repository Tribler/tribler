import sys
from unittest.mock import Mock, patch

import pytest

from tribler.core.utilities.slow_coro_detection.main_thread_stack_tracking import (
    _get_main_thread_stack_info, get_main_thread_stack, main_stack_tracking_is_activated, main_thread_profile,
    start_main_thread_stack_tracing,
    stop_main_thread_stack_tracing
)


def test_main_thread_profile():
    frame = Mock()
    arg = Mock()
    stack = []

    with patch('tribler.core.utilities.slow_coro_detection.main_thread_stack_tracking._main_thread_stack', stack):
        assert not stack

        result = main_thread_profile(frame, 'call', arg)
        assert result is main_thread_profile
        assert stack == [frame]

        result = main_thread_profile(frame, 'return', arg)
        assert result is main_thread_profile
        assert not stack


def test_main_stack_tracking_is_activated():
    assert not main_stack_tracking_is_activated()
    activated_profiler = start_main_thread_stack_tracing()
    assert main_stack_tracking_is_activated()
    deactivated_profiler = stop_main_thread_stack_tracing()
    assert not main_stack_tracking_is_activated()
    assert activated_profiler is deactivated_profiler


def test_get_main_thread_stack_info():
    frame1 = Mock(f_lineno=111)
    frame1.f_code.co_name = 'CO_NAME1'
    frame1.f_code.co_filename = 'CO_FILENAME1'
    frame2 = Mock(f_lineno=222)
    frame2.f_code.co_name = 'CO_NAME2'
    frame2.f_code.co_filename = 'CO_FILENAME2'
    stack = [frame1, frame2]

    prev_switch_interval = sys.getswitchinterval()
    test_switch_interval = 10.0
    assert prev_switch_interval != pytest.approx(test_switch_interval, abs=0.01)
    sys.setswitchinterval(test_switch_interval)

    with patch('tribler.core.utilities.slow_coro_detection.main_thread_stack_tracking._main_thread_stack', stack):
        stack_info = _get_main_thread_stack_info()

    assert stack_info == [('CO_NAME1', 'CO_FILENAME1', 111), ('CO_NAME2', 'CO_FILENAME2', 222)]
    assert sys.getswitchinterval() == pytest.approx(test_switch_interval, abs=0.01)
    sys.setswitchinterval(prev_switch_interval)


def test_get_main_thread_stack():
    stack_info = [('CO_NAME1', 'CO_FILENAME1', 111), ('CO_NAME2', 'CO_FILENAME2', 222)]
    with patch('tribler.core.utilities.slow_coro_detection.main_thread_stack_tracking._get_main_thread_stack_info',
               return_value=stack_info):
        with patch('linecache.getline', side_effect=['line1', 'line2']):
            stack = get_main_thread_stack()
    assert stack == 'Traceback (most recent call last):\n' \
                    '  File "CO_FILENAME1", line 111, in CO_NAME1\n' \
                    '    line1\n' \
                    '  File "CO_FILENAME2", line 222, in CO_NAME2\n' \
                    '    line2\n'
