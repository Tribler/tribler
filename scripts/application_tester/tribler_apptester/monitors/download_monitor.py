import logging
import os
import time
from asyncio import ensure_future

from tribler_apptester.utils.asyncio import looping_call


class DownloadMonitor(object):
    """
    This class is responsible for monitoring downloads and circuits in Tribler.
    Specifically, it fetches information from the Tribler core and writes it to a file.
    """

    def __init__(self, request_manager, interval):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.interval = interval
        self.request_manager = request_manager
        self.monitor_lc = None
        self.start_time = time.time()

        # Create the output directory if it does not exist yet
        output_dir = os.path.join(os.getcwd(), "output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        self.download_stats_file_path = os.path.join(output_dir, 'download_stats.csv')
        with open(self.download_stats_file_path, "w") as output_file:
            output_file.write("time,infohash,status,speed_up,speed_down,progress\n")

        self.circuits_file_path = os.path.join(output_dir, 'circuits.csv')
        with open(self.circuits_file_path, "w") as output_file:
            output_file.write("time,id,type,state,goal_hops,actual_hops,bytes_up,bytes_down\n")

        self.circuits_states_file_path = os.path.join(output_dir, 'circuit_states.csv')
        with open(self.circuits_states_file_path, "w") as output_file:
            output_file.write("time,ready,extending,closing\n")

        self.circuits_types_file_path = os.path.join(output_dir, 'circuit_types.csv')
        with open(self.circuits_types_file_path, "w") as output_file:
            output_file.write("time,data,ip,rp,rendezvous\n")

    def start(self):
        """
        Start the monitoring loop for the downloads.
        """
        self._logger.info("Starting download monitor (interval: %d seconds)" % self.interval)
        self.monitor_lc = ensure_future(looping_call(0, self.interval, self.monitor_downloads))

    def stop(self):
        """
        Stop the monitoring loop for the downloads.
        """
        if self.monitor_lc:
            self.monitor_lc.cancel()
            self.monitor_lc = None

    async def monitor_downloads(self):
        """
        Monitor the downloads in Tribler.
        """
        downloads = await self.request_manager.get_downloads()
        for download in downloads["downloads"]:
            time_diff = time.time() - self.start_time
            with open(self.download_stats_file_path, "a") as output_file:
                output_file.write("%s,%s,%s,%s,%s,%f\n" % (time_diff,
                                                           download["infohash"],
                                                           download["status"],
                                                           download["speed_up"],
                                                           download["speed_down"],
                                                           download["progress"]))

        # Now we get the number of circuits
        circuits_info = await self.request_manager.get_circuits_info()
        time_diff = time.time() - self.start_time
        circuits_ready = circuits_extending = circuits_closing = 0
        circuits_data = circuits_ip = circuits_rp = circuits_rendezvous = 0

        for circuit in circuits_info["circuits"]:
            if circuit["state"] == "READY":
                circuits_ready += 1
            elif circuit["state"] == "EXTENDING":
                circuits_extending += 1
            elif circuit["state"] == "CLOSING":
                circuits_closing += 1

            if circuit["type"] == "DATA":
                circuits_data += 1
            elif circuit["type"] == "IP":
                circuits_ip += 1
            elif circuit["type"] == "RP":
                circuits_rp += 1
            elif circuit["type"] == "RENDEZVOUS":
                circuits_rendezvous += 1

            with open(self.circuits_file_path, "a") as output_file:
                output_file.write("%s,%s,%s,%s,%d,%d,%d,%d\n" % (time_diff,
                                                                 circuit["circuit_id"],
                                                                 circuit["type"],
                                                                 circuit["state"],
                                                                 circuit["goal_hops"],
                                                                 circuit["actual_hops"],
                                                                 circuit["bytes_up"],
                                                                 circuit["bytes_down"]))

        with open(self.circuits_states_file_path, "a") as output_file:
            output_file.write("%s,%d,%d,%d\n" % (time_diff,
                                                 circuits_ready,
                                                 circuits_extending,
                                                 circuits_closing))

        with open(self.circuits_types_file_path, "a") as output_file:
            output_file.write("%s,%d,%d,%d,%d\n" % (time_diff,
                                                    circuits_data,
                                                    circuits_ip,
                                                    circuits_rp,
                                                    circuits_rendezvous))
