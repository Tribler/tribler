import os
import time
from collections import deque

import psutil

from ipv8.taskmanager import TaskManager
from tribler_common.simpledefs import NTFY
from tribler_core.components.resource_monitor.implementation.base import ResourceMonitor
from tribler_core.components.resource_monitor.implementation.profiler import YappiProfiler
from tribler_core.components.resource_monitor.settings import ResourceMonitorSettings
from tribler_core.notifier import Notifier

FREE_DISK_THRESHOLD = 100 * (1024 * 1024)  # 100MB
DEFAULT_RESOURCE_FILENAME = "resources.log"
CORE_RESOURCE_HISTORY_SIZE = 1000


class CoreResourceMonitor(ResourceMonitor, TaskManager):
    """
    Implementation class of ResourceMonitor by the core process. The core process uses
    TaskManager to implement start() and stop() methods.
    """

    def __init__(self, state_dir, log_dir, config: ResourceMonitorSettings,
                 notifier: Notifier, history_size=CORE_RESOURCE_HISTORY_SIZE):
        TaskManager.__init__(self)
        ResourceMonitor.__init__(self, history_size=history_size)

        self.config = config
        self.notifier = notifier
        self.disk_usage_data = deque(maxlen=history_size)

        self.state_dir = state_dir
        self.resource_log_file = log_dir / DEFAULT_RESOURCE_FILENAME
        self.resource_log_enabled = config.enabled

        # Setup yappi profiler
        self.profiler = YappiProfiler(log_dir)

    def start(self):
        """
        Start the resource monitoring by scheduling a task in TaskManager.
        """
        poll_interval = self.config.poll_interval
        self.register_task("check_resources", self.check_resources, interval=poll_interval)

    async def stop(self):
        """
        Called during shutdown, should clear all scheduled tasks.
        """
        await self.shutdown_task_manager()

    def check_resources(self):
        super().check_resources()
        # Additionally, record the disk and notify on low disk space available.
        self.record_disk_usage()
        try:
            if self.resource_log_file:
                self.write_resource_logs()
        except FileNotFoundError as e:
            self._logger.warning(e)

    def write_resource_logs(self):
        if not self.memory_data or not self.cpu_data:
            return

        if not self.resource_log_file.exists():
            resource_dir = self.resource_log_file.parent
            if resource_dir and not resource_dir.exists():
                os.makedirs(resource_dir)

        with self.resource_log_file.open(mode="a+") as output_file:
            latest_memory_data = self.memory_data[len(self.memory_data) - 1]
            latest_cpu_data = self.cpu_data[len(self.cpu_data) - 1]
            time_in_seconds = latest_memory_data[0]
            output_file.write(f"{time_in_seconds}, {latest_memory_data[1]}, {latest_cpu_data[1]}\n")

    def reset_resource_logs(self):
        if self.resource_log_file and self.resource_log_file.exists():
            self.resource_log_file.unlink()

    def set_resource_log_enabled(self, enabled):
        self.resource_log_enabled = enabled

    def is_resource_log_enabled(self):
        return self.resource_log_enabled

    def record_disk_usage(self, recorded_at=None):
        recorded_at = recorded_at or time.time()

        # Check for available disk space
        disk_usage = self.get_free_disk_space()
        self.disk_usage_data.append({"time": recorded_at,
                                     "total": disk_usage.total,
                                     "used": disk_usage.used,
                                     "free": disk_usage.free,
                                     "percent": disk_usage.percent})

        # Notify session if less than 100MB of disk space is available
        if disk_usage.free < FREE_DISK_THRESHOLD:
            self._logger.warning("Warning! Less than 100MB of disk space available")
            if self.notifier:
                self.notifier.notify(NTFY.LOW_SPACE, self.disk_usage_data[-1])

    def get_free_disk_space(self):
        return psutil.disk_usage(str(self.state_dir))

    def get_disk_usage(self):
        """
        Return a list containing the history of free disk space
        """
        return self.disk_usage_data
