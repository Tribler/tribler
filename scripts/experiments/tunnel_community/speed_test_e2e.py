import argparse
import os
from binascii import unhexlify
from pathlib import Path

from ipv8.messaging.anonymization.tunnel import EXIT_NODE, ORIGINATOR
from ipv8.taskmanager import task

from scripts.experiments.tunnel_community.speed_test_exit import EXPERIMENT_NUM_CIRCUITS, EXPERIMENT_NUM_HOPS, \
    Service as SpeedTestExitService
from tribler.core.components.tunnel.tunnel_component import TunnelsComponent

EXPERIMENT_NUM_MB = int(os.environ.get('EXPERIMENT_NUM_MB', 10))


class Service(SpeedTestExitService):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_file = 'speed_test_e2e.txt'
        self.index = 0
        self.tunnel_community = None

    async def on_tribler_started(self):
        info_hash = unhexlify('e24d8e65a329a59b41a532ebd4eb4a3db7cb291b')

        tunnels_component = self.session.get_instance(TunnelsComponent)
        self.tunnel_community = tunnels_component.community
        self.tunnel_community.join_swarm(info_hash, EXPERIMENT_NUM_HOPS, seeding=False, callback=self.on_circuit_ready)

    @task
    async def on_circuit_ready(self, address):
        index = self.index
        self.index += 1
        self.logger.info(f"on_circuit_ready: {self.index}/{EXPERIMENT_NUM_CIRCUITS}")
        circuit = self.tunnel_community.circuits[self.tunnel_community.ip_to_circuit_id(address[0])]
        self.results += await self.run_speed_test(ORIGINATOR, circuit, index, EXPERIMENT_NUM_MB)
        self.results += await self.run_speed_test(EXIT_NODE, circuit, index, EXPERIMENT_NUM_MB)
        self.tunnel_community.remove_circuit(circuit.circuit_id)
        if self.index >= EXPERIMENT_NUM_CIRCUITS:
            self._graceful_shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run speed e2e experiment')
    parser.add_argument('--fragile', '-f', help='Fail at the first error', action='store_true')
    arguments = parser.parse_args()

    service = Service(state_dir=Path('.Tribler'))
    service.run(fragile=arguments.fragile)
