import logging
import os
import time

from ipv8.taskmanager import TaskManager

import psutil

from tribler_common.simpledefs import NTFY

from tribler_core.utilities import path_util

# Attempt to import yappi
try:
    import yappi
    HAS_YAPPI = True
except ImportError:
    HAS_YAPPI = False

DEFAULT_RESOURCE_FILENAME = "resources.log"


class ResourceMonitor(TaskManager):
    """
    This class contains code to monitor resources (memory usage and CPU). Can be toggled using the config file.
    """

    def __init__(self, session):
        super(ResourceMonitor, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session
        self.cpu_data = []
        self.memory_data = []
        self.disk_usage_data = []
        self.process = psutil.Process()
        self.history_size = session.config.get_resource_monitor_history_size()
        self.resource_log_file = session.config.get_log_dir() / DEFAULT_RESOURCE_FILENAME
        self.resource_log_enabled = session.config.get_resource_monitor_enabled()
        self.reset_resource_logs()

        self.profiler_start_time = None
        self.profiler_running = False

        self.last_error = None

    def start(self):
        """
        Start the resource monitor by scheduling a LoopingCall.
        """
        self.register_task("check_resources", self.check_resources,
                           interval=self.session.config.get_resource_monitor_poll_interval())

    async def stop(self):
        if HAS_YAPPI and self.profiler_running:
            self.stop_profiler()

        await self.shutdown_task_manager()

    def start_profiler(self):
        """
        Start the Yappi profiler if the library is available and if it's not already running.
        """
        if self.profiler_running:
            raise RuntimeError("Profiler is already running")

        if not HAS_YAPPI:
            raise RuntimeError("Yappi cannot be found. Plase install the yappi library using your preferred package "
                               "manager and restart Tribler afterwards.")

        yappi.start(builtins=True)
        self.profiler_start_time = int(time.time())
        self.profiler_running = True

    def stop_profiler(self):
        """
        Stop yappi and write the stats to the output directory.
        Return the path of the yappi statistics file.
        """
        if not self.profiler_running:
            raise RuntimeError("Profiler is not running")

        if not HAS_YAPPI:
            raise RuntimeError("Yappi cannot be found. Plase install the yappi library using your preferred package "
                               "manager and restart Tribler afterwards.")

        yappi.stop()

        yappi_stats = yappi.get_func_stats()
        yappi_stats.sort("tsub")

        log_dir = self.session.config.get_state_dir() / 'logs'
        file_path = log_dir / (f"yappi_{self.profiler_start_time}.stats")
        # Make the log directory if it does not exist
        if not log_dir.exists():
            os.makedirs(log_dir)

        yappi_stats.save(file_path, type='callgrind')
        yappi.clear_stats()
        self.profiler_running = False
        return file_path

    def get_free_disk_space(self):
        return psutil.disk_usage(str(self.session.config.get_state_dir()))

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
        success = False
        if hasattr(self.process, "memory_full_info") and callable(getattr(self.process, "memory_full_info")):
            try:
                self.memory_data.append((time_seconds, self.process.memory_full_info().uss))
                success = True
            except psutil.AccessDenied:
                pass  # Happens on Windows
            except Exception as e:
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
            self._logger.warning("Warning! Less than 100MB of disk space available")
            self.session.notifier.notify(NTFY.LOW_SPACE, self.disk_usage_data[-1])

        # Write resource logs
        if self.resource_log_enabled:
            self.write_resource_logs(time_seconds)

    def set_resource_log_enabled(self, enabled):
        self.resource_log_enabled = enabled

    def is_resource_log_enabled(self):
        return self.resource_log_enabled

    def write_resource_logs(self, time_seconds):
        if not self.memory_data or not self.cpu_data:
            return
        with self.resource_log_file.open(mode="a+") as output_file:
            output_file.write(f"{time_seconds}, {self.memory_data[len(self.memory_data)-1][1]}, "
                                f"{self.cpu_data[len(self.cpu_data)-1][1]}\n")

    def reset_resource_logs(self):
        resource_dir = self.resource_log_file.parent
        if not resource_dir.exists() and resource_dir:
            path_util.makedirs(resource_dir)
        if self.resource_log_file.exists():
            self.resource_log_file.unlink()

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
