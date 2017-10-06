import logging
import time

import psutil
from twisted.internet.task import LoopingCall

from Tribler.dispersy.taskmanager import TaskManager


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
        self.process = psutil.Process()
        self.history_size = session.config.get_resource_monitor_history_size()

    def start(self):
        """
        Start the resource monitor by scheduling a LoopingCall.
        """
        self.register_task("check_resources", LoopingCall(self.check_resources)).start(
            self.session.config.get_resource_monitor_poll_interval(), now=False)

    def stop(self):
        self.cancel_all_pending_tasks()

    def check_resources(self):
        """
        Check CPU and memory usage.
        """
        self._logger.debug("Checking memory/CPU usage")
        if len(self.cpu_data) == self.history_size:
            self.cpu_data.pop(0)
        if len(self.memory_data) == self.history_size:
            self.memory_data.pop(0)

        time_seconds = time.time()
        self.cpu_data.append((time_seconds, self.process.cpu_percent(interval=None)))

        # Get the memory usage of the process
        # psutil package 4.0.0 introduced memory_full_info() method which among other info also returns uss.
        # uss (Unique Set Size) is probably the most representative metric for determining how much memory is
        # actually being used by a process.
        # However, on psutil version < 4.0.0, we fallback to use rss (Resident Set Size) which is the non-swapped
        # physical memory a process has used
        if hasattr(self.process, "memory_full_info") and callable(getattr(self.process, "memory_full_info")):
            self.memory_data.append((time_seconds, self.process.memory_full_info().uss))
        elif hasattr(self.process, "memory_info") and callable(getattr(self.process, "memory_info")):
            self.memory_data.append((time_seconds, self.process.memory_info().rss))

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
