import os
from collections import deque, namedtuple
from unittest.mock import MagicMock

import pytest

from tribler.core import notifications
from tribler.core.components.resource_monitor.implementation.core import CoreResourceMonitor
from tribler.core.components.resource_monitor.settings import ResourceMonitorSettings
from tribler.core.utilities.notifier import Notifier


@pytest.fixture(name="resource_monitor")
async def fixture_resource_monitor(tmp_path):
    config = ResourceMonitorSettings()
    notifier = Notifier()
    resource_monitor = CoreResourceMonitor(state_dir=tmp_path, log_dir=tmp_path, config=config, notifier=notifier,
                                           history_size=10)
    yield resource_monitor
    await resource_monitor.stop()


def test_check_resources(resource_monitor):
    """
    Test the resource monitor check
    """
    resource_monitor.write_resource_logs = lambda: None

    # Checking resources for the first time
    resource_monitor.check_resources()
    assert len(resource_monitor.cpu_data) == 1
    assert len(resource_monitor.memory_data) == 1
    assert len(resource_monitor.disk_usage_data) == 1

    # Check resources multiple times, it should keep the history size constant
    for _ in range(resource_monitor.history_size * 2):
        resource_monitor.check_resources()

    assert len(resource_monitor.cpu_data) == resource_monitor.history_size
    assert len(resource_monitor.memory_data) == resource_monitor.history_size
    assert len(resource_monitor.disk_usage_data) == resource_monitor.history_size


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
    assert isinstance(disk_usage_history, deque)


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

    resource_monitor.notifier = MagicMock()

    resource_monitor.get_free_disk_space = fake_get_free_disk_space
    resource_monitor.check_resources()
    resource_monitor.notifier[notifications.low_space].assert_called()
    resource_monitor.notifier[notifications.tribler_shutdown_state].assert_called()


def test_enable_resource_log(resource_monitor):
    resource_monitor.set_resource_log_enabled(True)
    assert resource_monitor.is_resource_log_enabled()


def test_profiler(resource_monitor):
    """
    Test the profiler start(), stop() methods.
    """
    profiler = resource_monitor.profiler
    assert not profiler.is_running()

    profiler.start()
    assert profiler.is_running()

    with pytest.raises(RuntimeError):
        profiler.start()

    stats_file = profiler.stop()
    assert os.path.exists(stats_file)
    assert not profiler.is_running()

    with pytest.raises(RuntimeError):
        profiler.stop()
