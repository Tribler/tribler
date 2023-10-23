import logging
import os
import time

import aiohttp


class HTTPRequestManager(object):
    """
    This class manages requests to the Tribler core.
    """

    def __init__(self, api_key, api_port):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.headers = {'User-Agent': 'Tribler application tester', 'X-Api-Key': api_key}
        self.api_port = api_port
        self.tribler_start_time = None

        # Create the output directory if it does not exist yet
        output_dir = os.path.join(os.getcwd(), "output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        self.request_times_file_path = os.path.join(output_dir, 'request_times.csv')

        with open(self.request_times_file_path, "w") as output_file:
            output_file.write("request_type,start_time,duration\n")

        self._logger.info(f'Initialized. Key: {api_key}. Port: {api_port}')

    def write_request_time(self, request_type, start_time):
        current_time = int(round(time.time() * 1000))
        request_time = current_time - start_time
        time_since_start = current_time - self.tribler_start_time
        with open(self.request_times_file_path, "a") as output_file:
            output_file.write("%s,%d,%d\n" % (request_type, time_since_start, request_time))

    async def get_json_from_endpoint(self, endpoint):
        """
        Perform a JSON request and log the request type and duration.
        """
        async with aiohttp.ClientSession() as client:
            start_time = int(round(time.time() * 1000))
            response = await client.get(f"http://localhost:{self.api_port}/{endpoint}", headers=self.headers)
            json_response = await response.json()
            self.write_request_time(endpoint, start_time)
            return json_response

    async def get_downloads(self):
        """
        Perform a request to the core to get the downloads
        """
        return await self.get_json_from_endpoint("downloads")

    async def get_circuits_info(self):
        """
        Perform a request to the core to get circuits information
        """
        return await self.get_json_from_endpoint("ipv8/tunnel/circuits")

    async def get_overlay_statistics(self):
        """
        Perform a request to the core to get IPv8 overlay statistics
        """
        return await self.get_json_from_endpoint("ipv8/overlays")

    async def get_memory_history_core(self):
        """
        Perform a request to the core to get the memory usage history
        """
        return await self.get_json_from_endpoint("debug/memory/history")

    async def get_cpu_history_core(self):
        """
        Perform a request to the core to get the CPU usage history
        """
        return await self.get_json_from_endpoint("debug/cpu/history")
