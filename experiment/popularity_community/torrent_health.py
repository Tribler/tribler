"""This script observes the popularity community messages and verifies the health data (seeders/leechers)
of received torrents based on a given probability.

### Usage

```
cd tribler  # Run from the project root directory

export PYTHONPATH=${PYTHONPATH}:.:`echo src/{pyipv8,tribler-common,tribler-core} | tr " " :`

python3 experiment/popularity_community/torrent_health.py [-t <timeout_in_sec>] [-f <result.csv>]
```

Where:
* `timeout_in_sec` means the time that the experiment will last
* `result.csv` means the path to `csv` db file.
    If the file exists, it will be overwritten.

### Example

```
python3 experiment/popularity_community/torrent_health.py -t 600
python3 experiment/popularity_community/torrent_health.py -t 600 -f result.csv
```

"""

import argparse
import asyncio
import csv
import logging
import os
import random
import time
from binascii import hexlify
from pathlib import Path

from cuckoopy import CuckooFilter
from cuckoopy.exceptions import CuckooFilterFullException

from ipv8.lazy_community import lazy_wrapper_wd
from ipv8.peer import Peer
from ipv8.peerdiscovery.discovery import RandomWalk

from experiment.tool.tiny_tribler_service import TinyTriblerService

from tribler_core.modules.popularity.payload import TorrentsHealthPayload
from tribler_core.modules.popularity.popularity_community import PopularityCommunity


_logger = logging.getLogger(__name__)

TARGET_PEERS_COUNT = int(os.environ.get('HEALTH_CHECK_PERCENTAGE', '20'))
HEALTH_CHECK_PERCENTAGE = float(os.environ.get('HEALTH_CHECK_PERCENTAGE', '0.5'))
FRESHNESS_THRESHOLD = int(os.environ.get('FRESHNESS_THRESHOLD', '10'))


class ObservablePopularityCommunity(PopularityCommunity):

    # pylint: disable=too-many-instance-attributes
    def __init__(self, interval_in_sec, output_file_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = logging.getLogger(self.__class__.__name__)

        self._start_time = time.time()
        self.peers_filter = CuckooFilter(capacity=10000, bucket_size=4, fingerprint_size=1)
        self.infohash_filter = CuckooFilter(capacity=10000, bucket_size=4, fingerprint_size=1)

        self.peers_count_unique = 0

        self.torrents_count_total = 0
        self.torrents_count_unique = 0
        self.torrents_count_duplicate = 0
        self.torrents_count_dead = 0

        self.num_messages_received = 0
        self.bandwidth_received_bytes = 0

        self.max_seeders = 0
        self.max_leechers = 0
        self.sum_seeders = 0
        self.sum_leechers = 0
        self.avg_seeders = 0
        self.avg_leechers = 0

        self.dht_checks_sent = 0
        self.dht_checks_failed = 0
        self.dht_checks_success = 0  # Recording success checks because some checks might still be pending

        self.dht_confirmed_dead_torrents = 0
        self.dht_confirmed_alive_torrents = 0
        self.dht_confirmed_fresh_torrents = 0

        # Sum of difference in reported seeders and DHT seeders of measured torrents
        self.sum_of_dht_health_diff = 0

        self._interval_in_sec = interval_in_sec
        self._output_file_path = output_file_path

        self._csv_file, self._csv_writer = self.init_csv_writer()

        self.register_task("check", self.check, interval=self._interval_in_sec)

    def __del__(self):
        if self._csv_file:
            self._csv_file.close()

    def init_csv_writer(self):
        csv_file = open(self._output_file_path, 'w')
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['time_in_sec',
                             'peers_count_total', 'peers_count_unique',
                             'num_messages_received', 'bandwidth_received_bytes',
                             'torrents_count_total', 'torrents_count_unique',
                             'torrents_count_duplicate', 'torrents_count_dead',
                             'max_seeders', 'sum_seeders', 'avg_seeders',
                             'max_leechers', 'sum_leechers', 'avg_leechers',
                             'dht_checks_sent', 'dht_checks_failed', 'dht_checks_success',
                             'dht_confirmed_alive_torrents', 'dht_confirmed_dead_torrents',
                             'dht_confirmed_fresh_torrents',
                             'sum_of_dht_health_diff'])
        return csv_file, csv_writer

    def check(self):
        for peer in self.get_peers():
            if not self.peers_filter.contains(str(peer.mid)):
                self.peers_count_unique += 1
                self.peers_filter.insert(str(peer.mid))

        self.write_measurements()

    # pylint: disable=W0221(arguments-differ)
    # Pylint W0221(arguments-differ) issue: use of @lazy_wrapper_wd instead of @lazy_wrapper is intentional.
    @lazy_wrapper_wd(TorrentsHealthPayload)
    async def on_torrents_health(self, _, payload, data):
        self.num_messages_received += 1
        self.bandwidth_received_bytes += len(data)

        received_torrents = payload.random_torrents + payload.torrents_checked
        num_new_torrents = len(received_torrents)
        self.torrents_count_total += num_new_torrents
        self._logger.info("Received a response with %d torrents", num_new_torrents)

        for infohash, seeders, leechers, _ in received_torrents:
            infohash_str = str(infohash)

            if not self.infohash_filter.contains(infohash_str):
                self.torrents_count_unique += 1
                self.torrents_count_dead += 1 if seeders == 0 else 0
            else:
                self.torrents_count_duplicate += 1

            try:
                self.infohash_filter.insert(infohash_str)
                self.max_seeders = seeders if seeders > self.max_seeders else self.max_seeders
                self.max_leechers = leechers if leechers > self.max_leechers else self.max_leechers

                self.sum_seeders += seeders
                self.sum_leechers += leechers

                self.avg_seeders = self.sum_seeders / self.torrents_count_unique
                self.avg_leechers = self.sum_leechers / self.torrents_count_unique
            except CuckooFilterFullException:
                self._logger.error("Infohash filter is full")

            # Do health check based on probability?
            if random.random() < HEALTH_CHECK_PERCENTAGE:
                await self.verify_health_with_dht(infohash, seeders)

    async def verify_health_with_dht(self, infohash, reported_seeders):
        self._logger.info("Sending DHT health request: %s", hexlify(infohash))
        self.dht_checks_sent += 1

        health_data = await self.torrent_checker.check_torrent_health(infohash, scrape_now=True)
        self._logger.info("Received DHT health response: %s", health_data)

        if not health_data or ('DHT' in health_data and 'error' in health_data['DHT']):
            self.dht_checks_failed += 1
            return

        self.dht_checks_success += 1

        dht_seeders = health_data['DHT']['seeders']
        dht_leechers = health_data['DHT']['leechers']

        # If no seeders or leechers found, then count as dead torrent
        if dht_seeders == 0 and dht_leechers == 0:
            self.dht_confirmed_dead_torrents += 1
            return

        self.dht_confirmed_alive_torrents += 1

        diff = abs(reported_seeders - dht_seeders)
        self.sum_of_dht_health_diff += diff
        if diff < FRESHNESS_THRESHOLD:
            self.dht_confirmed_fresh_torrents += 1

    def write_measurements(self):
        time_since_start = time.time() - self._start_time
        print(f"time:{time_since_start}, dht [sent:{self.dht_checks_sent}, success: {self.dht_checks_success}, "
              f"alive: {self.dht_confirmed_alive_torrents}, diff: {self.sum_of_dht_health_diff}]")
        self._csv_writer.writerow([time_since_start,
                                   len(self.get_peers()), self.peers_count_unique,
                                   self.num_messages_received, self.bandwidth_received_bytes,
                                   self.torrents_count_total, self.torrents_count_unique,
                                   self.torrents_count_duplicate, self.torrents_count_dead,
                                   self.max_seeders, self.sum_seeders, self.avg_seeders,
                                   self.max_leechers, self.sum_leechers, self.avg_leechers,
                                   self.dht_checks_sent, self.dht_checks_failed, self.dht_checks_success,
                                   self.dht_confirmed_alive_torrents, self.dht_confirmed_dead_torrents,
                                   self.dht_confirmed_fresh_torrents,
                                   self.sum_of_dht_health_diff])
        self._csv_file.flush()


class Service(TinyTriblerService):
    def __init__(self, interval_in_sec, output_file_path, timeout_in_sec, working_dir, config_path):
        super().__init__(Service.create_config(working_dir, config_path), timeout_in_sec,
                         working_dir, config_path)

        self._interval_in_sec = interval_in_sec
        self._output_file_path = output_file_path

    @staticmethod
    def create_config(working_dir, config_path):
        config = TinyTriblerService.create_default_config(working_dir, config_path)

        config.set_libtorrent_enabled(True)
        config.set_ipv8_enabled(True)
        config.set_chant_enabled(True)

        # For BEP33 to work, the node making the DHT request should have support for it.
        # So, setting hops=0 to avoid passing the request via exit nodes.
        config.set_default_number_hops(0)

        return config

    async def on_tribler_started(self):
        await super().on_tribler_started()

        session = self.session
        peer = Peer(session.trustchain_keypair)

        session.popularity_community = ObservablePopularityCommunity(self._interval_in_sec,
                                                                     self._output_file_path,
                                                                     peer, session.ipv8.endpoint,
                                                                     session.ipv8.network,
                                                                     metadata_store=session.mds,
                                                                     torrent_checker=session.torrent_checker)

        session.ipv8.overlays.append(session.popularity_community)
        session.ipv8.strategies.append((RandomWalk(session.popularity_community),
                                        TARGET_PEERS_COUNT))


def _parse_argv():
    parser = argparse.ArgumentParser(description='Runs popularity community with metrics measurement enabled.')

    parser.add_argument('-i', '--interval', type=int, help='how frequently (in sec) the torrent list has been checked',
                        default=10)
    parser.add_argument('-t', '--timeout', type=int, help='a time in sec that the experiment will last',
                        default=1 * 60)
    parser.add_argument('-f', '--file', type=str, help='result file path (csv)', default='result.csv')
    parser.add_argument('-v', '--verbosity', help='increase output verbosity', action='store_true')

    return parser.parse_args()


def _run_tribler(arguments):
    working_dir = Path(os.getcwd(), '.Tribler')

    service = Service(arguments.interval,
                      arguments.file,
                      arguments.timeout,
                      working_dir=working_dir,
                      config_path=Path(working_dir, 'tribler.conf'))

    loop = asyncio.get_event_loop()
    loop.create_task(service.start_tribler())
    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    _arguments = _parse_argv()
    print(f"Arguments: {_arguments}")

    logging_level = logging.DEBUG if _arguments.verbosity else logging.INFO
    logging.basicConfig(level=logging_level)

    _run_tribler(_arguments)
