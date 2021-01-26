import logging
import time
from collections import deque

import psutil


class ResourceMonitor:
    """
    This is a base resource monitor class that monitors the process's CPU and memory usage.
    This is done by check_resources() method.

    The periodic monitoring of the resources is left as the responsibility of the inheriting
    class since the implementation could differ between the processes.
    For eg. Tribler Core process could use TaskManager to scheduler the call while
    the GUI process could use QTimer.

    Similarly, the cleanup after the periodic check should also be implemented by
    the inheriting class.
    """

    def __init__(self, history_size=1000):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.history_size = history_size

        self.cpu_data = deque(maxlen=history_size)
        self.memory_data = deque(maxlen=history_size)

        self.process = psutil.Process()
        self.last_error = None

    def check_resources(self):
        """
        Check CPU and memory usage of the process.
        """
        self._logger.debug("Checking memory/CPU usage")
        current_time = time.time()

        self.record_cpu_usage(current_time)
        self.record_memory_usage(current_time)

    def record_memory_usage(self, recorded_at=None):
        recorded_at = recorded_at or time.time()

        # Get the memory usage of the process
        # psutil package 4.0.0 introduced memory_full_info() method which among other info also returns uss.
        # uss (Unique Set Size) is probably the most representative metric for determining how much memory is
        # actually being used by a process.
        # However, on psutil version < 4.0.0, we fallback to use rss (Resident Set Size) which is the non-swapped
        # physical memory a process has used
        success = False
        if hasattr(self.process, "memory_full_info") and callable(getattr(self.process, "memory_full_info")):
            try:
                self.memory_data.append((recorded_at, self.process.memory_full_info().uss))
                success = True
            except psutil.AccessDenied:
                pass  # Happens on Windows
            except Exception as e:  # pylint: disable=broad-except
                # Can be MemoryError or WindowsError, which isn't defined on Linux
                # Catching a WindowsError would therefore error out the error handler itself on Linux
                # We do not want to spam the log with errors in situation where e.g., memory info
                # access is denied. So, we remember the string representation of the last error
                # message and skip logging it if we have already seen it before
                last_error_str = str(e)
                if self.last_error != last_error_str:
                    self._logger.error("Failed to get memory full info: %s", last_error_str)
                    self.last_error = last_error_str

        # If getting uss failed, fallback to rss
        if not success and hasattr(self.process, "memory_info") and callable(getattr(self.process, "memory_info")):
            self.memory_data.append((recorded_at, self.process.memory_info().rss))

    def record_cpu_usage(self, recorded_at=None):
        recorded_at = recorded_at or time.time()
        self.cpu_data.append((recorded_at, self.process.cpu_percent(interval=None)))

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
