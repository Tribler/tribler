import asyncio
import os
from pathlib import Path

from ipv8.messaging.anonymization.tunnel import EXIT_NODE, ORIGINATOR
from ipv8.messaging.anonymization.utils import run_speed_test
from ipv8.taskmanager import TaskManager

from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.restapi.restapi_component import RESTComponent
from tribler_core.components.tunnel.tunnel_component import TunnelsComponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.utilities.tiny_tribler_service import TinyTriblerService

EXPERIMENT_NUM_MB = int(os.environ.get('EXPERIMENT_NUM_MB', 25))
EXPERIMENT_NUM_CIRCUITS = int(os.environ.get('EXPERIMENT_NUM_CIRCUITS', 10))
EXPERIMENT_NUM_HOPS = int(os.environ.get('EXPERIMENT_NUM_HOPS', 1))


class Service(TinyTriblerService, TaskManager):
    def __init__(self, working_dir, config_path):
        super().__init__(Service.create_config(working_dir, config_path), working_dir=working_dir,
                         components=[Ipv8Component(), KeyComponent(), RESTComponent(), TunnelsComponent()])
        TaskManager.__init__(self)
        self.results = []
        self.output_file = 'speed_test_exit.txt'

    @staticmethod
    def create_config(working_dir, config_path):
        config = TriblerConfig(state_dir=working_dir, file=config_path)
        config.dht.enabled = True
        return config

    def _graceful_shutdown(self):
        task = asyncio.create_task(self.on_tribler_shutdown())
        task.add_done_callback(lambda result: TinyTriblerService._graceful_shutdown(self))

    async def on_tribler_shutdown(self):
        await self.shutdown_task_manager()

        # Fill in the gaps with 0's
        max_time = max(result[0] for result in self.results)
        index = 0
        while index < len(self.results):
            curr = self.results[index]
            _next = self.results[index + 1] if index + 1 < len(self.results) else None
            if not _next or curr[2] != _next[2]:
                self.results[index + 1:index + 1] = [(t + curr[0] + 1, curr[1], curr[2], 0)
                                                     for t in range(max_time - curr[0])]
                index += max_time - curr[0]
            index += 1

        with open(self.output_file, 'w') as f:
            f.write("Time Circuit Type Speed\n")
            for result in self.results:
                f.write(' '.join(map(str, result)) + '\n')

    async def on_tribler_started(self):
        index = 0
        while index < EXPERIMENT_NUM_CIRCUITS:
            community = TunnelsComponent.instance().community
            circuit = community.create_circuit(EXPERIMENT_NUM_HOPS)
            if circuit and (await circuit.ready):
                index += 1
                self.results += await self.run_speed_test(ORIGINATOR, circuit, index, EXPERIMENT_NUM_MB)
                self.results += await self.run_speed_test(EXIT_NODE, circuit, index, EXPERIMENT_NUM_MB)
                community.remove_circuit(circuit.circuit_id)
            else:
                await asyncio.sleep(1)
        self._graceful_shutdown()

    async def run_speed_test(self, direction, circuit, index, size):
        request_size = 0 if direction == ORIGINATOR else 1024
        response_size = 1024 if direction == ORIGINATOR else 0
        num_requests = size * 1024
        task = asyncio.create_task(run_speed_test(TunnelsComponent.instance().community, circuit, request_size,
                                                  response_size, num_requests, window=50))
        results = []
        prev_transferred = ts = 0
        while not task.done():
            cur_transferred = circuit.bytes_down if direction == ORIGINATOR else circuit.bytes_up
            results.append((ts, index, direction, (cur_transferred - prev_transferred) / 1024))
            prev_transferred = cur_transferred
            ts += 1
            await asyncio.sleep(1)
        return results


def run_experiment():
    service = Service(working_dir=Path('.Tribler').absolute(), config_path=Path('./tribler.conf'))
    loop = asyncio.get_event_loop()
    loop.create_task(service.start_tribler())
    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    run_experiment()
