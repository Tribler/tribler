import os
import sys
import time
from collections import namedtuple
from unittest.mock import Mock

import pytest

from tribler_common.simpledefs import NTFY

from tribler_core.modules.resource_monitor import HAS_YAPPI, ResourceMonitor


@pytest.fixture
async def resource_monitor(session):
    session.notifier = Mock()
    resource_monitor = ResourceMonitor(session)
    yield resource_monitor
    await resource_monitor.stop()


def test_check_resources(resource_monitor):
    """
    Test the resource monitor check
    """
    resource_monitor.write_resource_logs = lambda _: None
    resource_monitor.check_resources()
    assert len(resource_monitor.cpu_data) == 1
    # Getting memory info produces an AccessDenied error using Python 3
    if sys.version_info.major < 3:
        assert len(resource_monitor.memory_data) == 1
    assert len(resource_monitor.disk_usage_data) == 1

    # Check that we remove old history
    resource_monitor.history_size = 1
    resource_monitor.check_resources()
    assert len(resource_monitor.cpu_data) == 1
    if sys.version_info.major < 3:
        assert len(resource_monitor.memory_data) == 1
    assert len(resource_monitor.disk_usage_data) == 1


def test_get_history_dicts(resource_monitor):
    """
    Test the CPU/memory/disk usage history dictionary of a resource monitor
    """
    resource_monitor.check_resources()
    cpu_dict = resource_monitor.get_cpu_history_dict()
    assert isinstance(cpu_dict, list)

    memory_dict = resource_monitor.get_memory_history_dict()
    assert isinstance(memory_dict, list)

    disk_usage_history = resource_monitor.get_disk_usage()
    assert isinstance(disk_usage_history, list)


def test_memory_full_error(resource_monitor):
    """
    Test if check resources completes when memory_full_info fails
    """
    resource_monitor.process.cpu_percent = lambda interval: None

    def fail_with_error():
        raise MemoryError()

    resource_monitor.process.memory_full_info = fail_with_error

    resource_monitor.check_resources()

    assert len(resource_monitor.memory_data) == 1


def test_low_disk_notification(resource_monitor):
    """
    Test low disk space notification
    """
    def fake_get_free_disk_space():
        disk = {"total": 318271800, "used": 312005050, "free": 6266750, "percent": 98.0}
        return namedtuple('sdiskusage', disk.keys())(*disk.values())

    def on_notify(subject, *args):
        assert subject in [NTFY.LOW_SPACE, NTFY.TRIBLER_SHUTDOWN_STATE]

    resource_monitor.get_free_disk_space = fake_get_free_disk_space
    resource_monitor.session.notifier.notify = on_notify
    resource_monitor.check_resources()


@pytest.mark.skipif(not HAS_YAPPI, reason="Yappi not installed")
def test_profiler(resource_monitor):
    """
    Test the profiler functionality
    """
    resource_monitor.start_profiler()
    assert resource_monitor.profiler_running
    with pytest.raises(RuntimeError):
        resource_monitor.start_profiler()

    resource_monitor.stop_profiler()
    assert not resource_monitor.profiler_running
    with pytest.raises(RuntimeError):
        resource_monitor.stop_profiler()


def test_resource_log(resource_monitor):
    """
    Test resource log file is created when enabled.
    """
    resource_monitor.set_resource_log_enabled(True)
    resource_monitor.check_resources()
    assert resource_monitor.resource_log_file.exists()


def test_write_resource_log(resource_monitor):
    """
    Test no data is written to file and no exception raised when resource data (cpu & memory) is empty which
    happens at startup.
    """
    # Empty resource log to check later if something was written to the log or not.
    with open(resource_monitor.resource_log_file, 'w'): pass

    resource_monitor.memory_data = []
    resource_monitor.cpu_data = []

    # Try writing the log
    resource_monitor.write_resource_logs(time.time())

    # Nothing should be written since memory and cpu data was not available
    assert os.stat(resource_monitor.resource_log_file).st_size == 0


def test_enable_resource_log(resource_monitor):
    resource_monitor.set_resource_log_enabled(True)
    assert resource_monitor.is_resource_log_enabled()


def test_reset_resource_log(resource_monitor):
    resource_monitor.reset_resource_logs()
    assert not resource_monitor.resource_log_file.exists()
