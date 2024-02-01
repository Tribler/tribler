from unittest.mock import Mock, patch

import pytest

from tribler.core.utilities.slow_coro_detection.patch import _report_long_duration, patched_handle_run
from tribler.core.utilities.slow_coro_detection.watching_thread import SlowCoroWatchingThread, _report_freeze


@patch('tribler.core.utilities.slow_coro_detection.watching_thread._report_freeze')
@patch('tribler.core.utilities.slow_coro_detection.watching_thread.current')
@patch('time.sleep')
def test_slow_coro_watching_thread_run_1(_, current: Mock, _report_freeze: Mock):
    thread = SlowCoroWatchingThread()
    thread.stop_event = Mock()
    thread.stop_event.is_set.side_effect = [False, True]
    current.handle = Mock()
    current.start_time = start_time = 1000.0
    with patch('time.time', side_effect=[start_time + 0.01]):
        thread.run()

    _report_freeze.assert_not_called()


@patch('tribler.core.utilities.slow_coro_detection.watching_thread._report_freeze')
@patch('tribler.core.utilities.slow_coro_detection.watching_thread.current')
@patch('time.sleep')
def test_slow_coro_watching_thread_run_2(_, current: Mock, _report_freeze: Mock):
    thread = SlowCoroWatchingThread()
    thread.stop_event = Mock()
    thread.stop_event.is_set.side_effect = [False, False, False, True]
    current.handle = Mock()
    current.start_time = start_time = 1000.0
    with patch('time.time', side_effect=[start_time + 0.01, start_time + 1.5, start_time + 2.5]):
        thread.run()

    assert _report_freeze.call_count == 2
    assert _report_freeze.call_args_list[0].kwargs['first_report']
    assert not _report_freeze.call_args_list[1].kwargs['first_report']


def test_slow_coro_watching_thread_stop():
    thread = SlowCoroWatchingThread()
    thread.stop_event = Mock()
    thread.stop()
    thread.stop_event.set.assert_called()


@patch('tribler.core.utilities.slow_coro_detection.patch._report_long_duration')
@patch('tribler.core.utilities.slow_coro_detection.patch.current')
@patch('time.sleep')
def test_patched_handle_run(_, current: Mock, report_long_duration: Mock):
    handle = Mock()
    start_time = 1000

    def patched_original_handle_run(self):
        assert self is handle
        assert current.handle is handle
        assert current.start_time is start_time

    with patch('time.time', side_effect=[start_time, start_time + 1.5]):
        with patch('tribler.core.utilities.slow_coro_detection.patch._original_handle_run',
                   new=patched_original_handle_run):
            patched_handle_run(handle)

    assert current.handle is None
    assert current.start_time is None
    report_long_duration.assert_called()


@patch('tribler.core.utilities.slow_coro_detection.patch.format_info', return_value='<formatted handle>')
@patch('tribler.core.utilities.slow_coro_detection.patch.logger')
def test_report_long_duration(logger, format_info: Mock):
    handle = Mock()
    duration = 10
    _report_long_duration(handle, duration)
    format_info.assert_called_with(handle)
    logger.warning.assert_called_with('Slow coroutine step execution (duration=10.000 seconds): <formatted handle>')


@patch('tribler.core.utilities.slow_coro_detection.watching_thread.format_info', return_value='<formatted handle>')
@patch('tribler.core.utilities.slow_coro_detection.watching_thread.logger')
def test__report_freeze_first_report(logger, format_info):
    handle = Mock()
    duration = 10

    _report_freeze(handle, duration, first_report=True)
    format_info.assert_called_with(handle, include_stack=True, stack_cut_duration=pytest.approx(8.0))
    logger.warning.assert_called_with(
        'Slow coroutine is occupying the loop for 10.000 seconds already: <formatted handle>')


@patch('tribler.core.utilities.slow_coro_detection.watching_thread.format_info', return_value='<formatted handle>')
@patch('tribler.core.utilities.slow_coro_detection.watching_thread.logger')
def test__report_freeze_not_first_report(logger, format_info):
    handle = Mock()
    duration = 10

    _report_freeze(handle, duration, first_report=False)
    format_info.assert_called_with(handle, include_stack=True, stack_cut_duration=pytest.approx(8.0),
                                   limit=2, enable_profiling_tip=False)
    logger.warning.assert_called_with('Still executing <formatted handle>')
