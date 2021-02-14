import asyncio
import os
from binascii import unhexlify
from pathlib import Path

from ipv8.messaging.anonymization.tunnel import EXIT_NODE, ORIGINATOR
from ipv8.taskmanager import task

from experiment.tunnel_community.speed_test_exit import EXPERIMENT_NUM_CIRCUITS, EXPERIMENT_NUM_HOPS, \
                                                        EXPERIMENT_NUM_MB, Service as SpeedTestExitService

EXPERIMENT_NUM_MB = int(os.environ.get('EXPERIMENT_NUM_MB', 10))


class Service(SpeedTestExitService):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_file = 'speed_test_e2e.txt'
        self.index = 0

    async def on_tribler_started(self):
        info_hash = unhexlify('e24d8e65a329a59b41a532ebd4eb4a3db7cb291b')
        self.session.tunnel_community.join_swarm(info_hash, EXPERIMENT_NUM_HOPS,
                                                 seeding=False, callback=self.on_circuit_ready)

    @task
    async def on_circuit_ready(self, address):
        index = self.index
        self.index += 1
        circuit = self.session.tunnel_community.circuits[self.session.tunnel_community.ip_to_circuit_id(address[0])]
        self.results += await self.run_speed_test(ORIGINATOR, circuit, index, EXPERIMENT_NUM_MB)
        self.results += await self.run_speed_test(EXIT_NODE, circuit, index, EXPERIMENT_NUM_MB)
        self.session.tunnel_community.remove_circuit(circuit.circuit_id)

        if self.index >= EXPERIMENT_NUM_CIRCUITS:
            self._graceful_shutdown()


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
