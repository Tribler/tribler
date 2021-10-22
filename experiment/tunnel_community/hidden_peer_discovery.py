import asyncio
import os
import time
from binascii import hexlify, unhexlify
from pathlib import Path

from ipv8.taskmanager import TaskManager

from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.restapi.restapi_component import RESTComponent
from tribler_core.components.tunnel.tunnel_component import TunnelsComponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.utilities.tiny_tribler_service import TinyTriblerService

EXPERIMENT_RUN_TIME = int(os.environ.get('EXPERIMENT_RUN_TIME', 3600 * 3))


class Service(TinyTriblerService, TaskManager):
    def __init__(self, working_dir, config_path):
        super().__init__(Service.create_config(working_dir, config_path), working_dir=working_dir,
                         components=[Ipv8Component(), KeyComponent(), RESTComponent(), TunnelsComponent()])
        TaskManager.__init__(self)
        self.swarm = None
        self.start = time.time()
        self.results = []
        self.register_task('monitor_swarm', self.monitor_swarm, interval=5)
        self.register_task('_graceful_shutdown', self._graceful_shutdown, delay=EXPERIMENT_RUN_TIME)

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
        with open('hidden_peer_discovery.txt', 'w') as f:
            f.write("Time Seeders Introduction-points Connections Partial-connections Last-lookup Last-DHT-lookup\n")
            for result in self.results:
                f.write(' '.join(map(str, result)) + '\n')

    async def on_tribler_started(self):
        info_hash = unhexlify('e24d8e65a329a59b41a532ebd4eb4a3db7cb291b')
        community = TunnelsComponent.instance().community
        community.join_swarm(info_hash, 1, seeding=False)
        self.swarm = community.swarms[info_hash]
        print(f'Joining hidden swarm {hexlify(info_hash)}')  # noqa: T001

    def monitor_swarm(self):
        self.results.append((int(time.time() - self.start),
                             self.swarm.get_num_seeders(),
                             len(self.swarm.intro_points),
                             self.swarm.get_num_connections(),
                             self.swarm.get_num_connections_incomplete(),
                             int(self.swarm.last_lookup - self.start) if self.swarm.last_lookup else 0,
                             int(self.swarm.last_dht_response - self.start) if self.swarm.last_dht_response else 0))


def run_experiment():
    service = Service(working_dir=Path('/tmp/tribler').absolute(), config_path=Path('./tribler.conf'))
    loop = asyncio.get_event_loop()
    loop.create_task(service.start_tribler())
    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    run_experiment()
