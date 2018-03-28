import logging
import time

import psutil
from twisted.internet.task import LoopingCall

from Tribler.Core.simpledefs import SIGNAL_LOW_SPACE, SIGNAL_RESOURCE_CHECK
from Tribler.pyipv8.ipv8.taskmanager import TaskManager


class ResourceMonitor(TaskManager):
    """
    This class contains code to monitor resources (memory usage and CPU). Can be toggled using the config file.
    """

    def __init__(self, session):
        super(ResourceMonitor, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session
        self.check_interval = 5
        self.cpu_data = []
        self.memory_data = []
        self.disk_usage_data = []
        self.process = psutil.Process()
        self.history_size = session.config.get_resource_monitor_history_size()

    def start(self):
        """
        Start the resource monitor by scheduling a LoopingCall.
        """
        self.register_task("check_resources", LoopingCall(self.check_resources)).start(
            self.session.config.get_resource_monitor_poll_interval(), now=False)

    def stop(self):
        self.shutdown_task_manager()

    def get_free_disk_space(self):
        return psutil.disk_usage(self.session.config.get_state_dir())

    def check_resources(self):
        """
        Check CPU and memory usage.
        """
        self._logger.debug("Checking memory/CPU usage")
        if len(self.cpu_data) == self.history_size:
            self.cpu_data.pop(0)
        if len(self.memory_data) == self.history_size:
            self.memory_data.pop(0)
        if len(self.disk_usage_data) == self.history_size:
            self.disk_usage_data.pop(0)

        time_seconds = time.time()
        self.cpu_data.append((time_seconds, self.process.cpu_percent(interval=None)))

        # Get the memory usage of the process
        # psutil package 4.0.0 introduced memory_full_info() method which among other info also returns uss.
        # uss (Unique Set Size) is probably the most representative metric for determining how much memory is
        # actually being used by a process.
        # However, on psutil version < 4.0.0, we fallback to use rss (Resident Set Size) which is the non-swapped
        # physical memory a process has used
        if hasattr(self.process, "memory_full_info") and callable(getattr(self.process, "memory_full_info")):
            try:
                self.memory_data.append((time_seconds, self.process.memory_full_info().uss))
            except Exception as e:
                # Can be MemoryError or WindowsError, which isn't defined on Linux
                # Catching a WindowsError would therefore error out the error handler itself on Linux
                self._logger.error("Failed to get memory full info: %s", str(e))
        elif hasattr(self.process, "memory_info") and callable(getattr(self.process, "memory_info")):
            self.memory_data.append((time_seconds, self.process.memory_info().rss))

        # Check for available disk space
        disk_usage = self.get_free_disk_space()
        self.disk_usage_data.append({"time": time_seconds,
                                     "total": disk_usage.total,
                                     "used": disk_usage.used,
                                     "free": disk_usage.free,
                                     "percent": disk_usage.percent})

        # Notify session if less than 100MB of disk space is available
        if disk_usage.free < 100 * (1024 * 1024):
            self._logger.warn("Warning! Less than 100MB of disk space available")
            self.session.notifier.notify(SIGNAL_RESOURCE_CHECK, SIGNAL_LOW_SPACE, None, self.disk_usage_data[-1])

    def get_cpu_history_dict(self):
        """
        Return a dictionary containing the history of CPU usage, together with timestamps.
        """
        return [{"time": cpu_data[0], "cpu": cpu_data[1]} for cpu_data in self.cpu_data]

    def get_memory_history_dict(self):
        """
        Return a dictionary containing the history of memory usage, together with timestamps.
        """
        return [{"time": memory_data[0], "mem": memory_data[1]} for memory_data in self.memory_data]

    def get_disk_usage(self):
        """
        Return a list containing the history of free disk space
        """
        return self.disk_usage_data
