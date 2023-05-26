import time

from _pytest.logging import LogCaptureFixture

from tribler.core.utilities.slow_coro_detection.profiler import profile


def profiled_function():
    function1()
    function2()
    function3()


def function1():
    pass


def function2():
    time.sleep(0.02)


def function3():
    time.sleep(0.01)


def test_profile(caplog: LogCaptureFixture):
    f = profile(threshold_duration=0.0)(profiled_function)
    f()

    log_text = caplog.text
    assert 'Profiled results for `profiled_function`:' in log_text
    assert '{built-in method time.sleep}' in log_text
    assert '(profiled_function)' in log_text
    assert '(function1)' not in log_text
    assert '(function2)' in log_text
    assert '(function3)' in log_text
    assert log_text.index('{built-in method time.sleep}') < log_text.index('(profiled_function)')
    assert log_text.index('{built-in method time.sleep}') < log_text.index('(function2)')
    assert log_text.index('{built-in method time.sleep}') < log_text.index('(function3)')


def test_fast_profile_no_stats(caplog: LogCaptureFixture):
    f = profile(threshold_duration=1.0)(profiled_function)
    f()

    log_text = caplog.text
    assert 'Profiled function `profiled_function` executed in' in log_text
    assert 'Profiled results for `profiled_function`:' not in log_text
