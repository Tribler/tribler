import os
import time

import yappi


class YappiProfiler:

    def __init__(self, logs_dir):
        self.logs_dir = logs_dir

        self._start_time = None
        self._is_running = False

    def is_running(self):
        return self._is_running

    def start(self):
        """
        Start the Yappi profiler if it is not already running.
        """
        if self._is_running:
            raise RuntimeError("Profiler is already running")

        yappi.start(builtins=True)
        self._start_time = int(time.time())
        self._is_running = True

    def stop(self):
        """
        Stop Yappi and write the stats to the output directory.
        Return the path of the statistics file.
        """
        if not self._is_running:
            raise RuntimeError("Profiler is not running")

        yappi.stop()

        yappi_stats = yappi.get_func_stats()
        yappi_stats.sort('tsub', sort_order="desc")

        log_dir = self.logs_dir
        file_path = log_dir / f"yappi_{self._start_time}.stats"
        # Make the log directory if it does not exist
        if not log_dir.exists():
            os.makedirs(log_dir)

        yappi_stats.save(file_path, type='callgrind')
        yappi.clear_stats()
        self._is_running = False
        return file_path
