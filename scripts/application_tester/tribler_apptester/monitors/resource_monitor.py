import logging
import os
import time
from asyncio import ensure_future

from tribler_apptester.utils.asyncio import looping_call


class ResourceMonitor(object):
    """
    This class is responsible for monitoring resources in Tribler.
    Specifically, it fetches information from the Tribler core and writes it to a file.
    """

    def __init__(self, request_manager, interval):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.interval = interval
        self.request_manager = request_manager
        self.monitor_memory_lc = None
        self.monitor_cpu_lc = None
        self.start_time = time.time()
        self.latest_memory_time = 0
        self.latest_cpu_time = 0

        # Create the output directory if it does not exist yet
        output_dir = os.path.join(os.getcwd(), "output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        self.memory_stats_file_path = os.path.join(output_dir, 'memory_stats.csv')
        with open(self.memory_stats_file_path, "w") as output_file:
            output_file.write("time,memory_usage\n")

        self.cpu_stats_file_path = os.path.join(output_dir, 'cpu_stats.csv')
        with open(self.cpu_stats_file_path, "w") as output_file:
            output_file.write("time,cpu_usage\n")

    def start(self):
        """
        Start the monitoring loop for the resources.
        """
        self._logger.info("Starting resource monitor (interval: %d seconds)" % self.interval)
        self.monitor_memory_lc = ensure_future(looping_call(0, self.interval, self.monitor_memory))
        self.monitor_cpu_lc = ensure_future(looping_call(0, self.interval, self.monitor_cpu))

    def stop(self):
        """
        Stop the monitoring loop for the resources.
        """
        if self.monitor_memory_lc:
            self.monitor_memory_lc.cancel()
            self.monitor_memory_lc = None

        if self.monitor_cpu_lc:
            self.monitor_cpu_lc.cancel()
            self.monitor_cpu_lc = None

    async def monitor_memory(self):
        """
        Monitor the memory usage in Tribler.
        """
        history = await self.request_manager.get_memory_history_core()
        for history_item in history["memory_history"]:
            if history_item["time"] > self.latest_memory_time:
                self.latest_memory_time = history_item["time"]
                time_diff = history_item["time"] - self.start_time
                with open(self.memory_stats_file_path, "a") as output_file:
                    output_file.write("%s,%s\n" % (time_diff, history_item["mem"]))

    async def monitor_cpu(self):
        """
        Monitor the CPU usage in Tribler.
        """
        history = await self.request_manager.get_cpu_history_core()
        for history_item in history["cpu_history"]:
            if history_item["time"] > self.latest_cpu_time:
                self.latest_cpu_time = history_item["time"]
                time_diff = history_item["time"] - self.start_time
                with open(self.cpu_stats_file_path, "a") as output_file:
                    output_file.write("%s,%s\n" % (time_diff, history_item["cpu"]))
