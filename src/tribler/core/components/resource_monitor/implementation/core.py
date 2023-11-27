import time
from collections import deque
from typing import NamedTuple, Optional

import psutil
from ipv8.taskmanager import TaskManager

from tribler.core import notifications
from tribler.core.components.resource_monitor.implementation.base import ResourceMonitor
from tribler.core.components.resource_monitor.implementation.profiler import YappiProfiler
from tribler.core.components.resource_monitor.settings import ResourceMonitorSettings
from tribler.core.utilities.notifier import Notifier

FREE_DISK_THRESHOLD = 100 * (1024 * 1024)  # 100MB
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
        self.resource_log_enabled = config.enabled

        # Setup yappi profiler
        self.profiler = YappiProfiler(log_dir)

    def start(self):
        """
        Start the resource monitoring by scheduling a task in TaskManager.
        """
        self._logger.info('Starting...')
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

    def record_disk_usage(self, recorded_at=None):
        recorded_at = recorded_at or time.time()

        # Check for available disk space
        if disk_usage := self.get_disk_usage():
            self.disk_usage_data.append(
                {
                    "time": recorded_at,
                    "total": disk_usage.total,
                    "used": disk_usage.used,
                    "free": disk_usage.free,
                    "percent": disk_usage.percent
                }
            )

        # Notify session if less than 100MB of disk space is available
        if disk_usage.free < FREE_DISK_THRESHOLD:
            self._logger.warning("Warning! Less than 100MB of disk space available")
            if self.notifier:
                self.notifier[notifications.low_space](self.disk_usage_data[-1])

    def get_disk_usage(self) -> Optional[NamedTuple]:
        try:
            return psutil.disk_usage(str(self.state_dir))
        except OSError:
            return None
