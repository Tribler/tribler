# Metric 1: velocity of  torrents list filling
# https://github.com/Tribler/tribler/issues/5580
# This script calculate velocity of torrents list filling.
#
# Given: the real network.
#
# Action:
# * add a new node
# * every N seconds check how long torrent's list are
#
# Result will be stored in a csv file.
# ## Usage
#
# ```
# export PYTHONPATH=${PYTHONPATH}:`echo ../../../src/{pyipv8,tribler-common,tribler-core} | tr " " :`
#
# python3 initial_filling.py [-i <check_interval_in_sec>] [-t <timeout_in_sec>] [-f <output_file.csv>]
# ```
#
# Where:
# * `check_interval_in_sec` means how frequently we check the torrent list
# * `timeout_in_sec` means a time that the experiment will last
# * `output_file.csv` means a path and a result file name
#
# #### Example
#
# ```
# python3 initial_filling.py -i 60
# python3 initial_filling.py -i 60 -t 900
# python3 initial_filling.py -i 60 -t 900 -f result.csv
# ```

import asyncio
import csv
import getopt
import os
import signal
import sys
import time

from pony.orm import db_session, count

from ipv8.peer import Peer
from ipv8.peerdiscovery.discovery import RandomWalk
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.popularity.popularity_community import PopularityCommunity
from tribler_core.modules.process_checker import ProcessChecker
from tribler_core.session import Session


# defaults
class Configuration:
    check_interval_in_sec = 10
    timeout_in_sec = 10 * 60
    output_file_name = 'result.csv'

    tribler_target_peers_count = 20
    tribler_working_dir = os.path.join('/tmp', '.Tribler')
    tribler_config_path = os.path.join(tribler_working_dir, 'triblerd.conf')

    def __str__(self):
        return f"Check interval: {self.check_interval_in_sec}s, " \
               f"timeout: {self.timeout_in_sec}, " \
               f"output file: {self.output_file_name}"


class ObservablePopularityCommunity(PopularityCommunity):

    def __init__(self, *args, **kwargs):
        self._configuration = kwargs.pop('configuration')
        super(ObservablePopularityCommunity, self).__init__(*args, **kwargs)

        self._start_time = time.time()
        self._csv_file, self._csv_writer = self.init_csv_writer()

        self.register_task("check", self.check, interval=self._configuration.check_interval_in_sec)

    def __del__(self):
        if self._csv_file:
            self._csv_file.close()

    def init_csv_writer(self):
        csv_file = open(self._configuration.output_file_name, 'w')
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['time_in_sec', 'total', 'alive'])
        return csv_file, csv_writer

    @db_session
    def get_torrents_info_tuple(self):
        return count(ts for ts in self.metadata_store.TorrentState), \
               count(ts for ts in self.metadata_store.TorrentState if ts.seeders > 0)

    def check(self):
        time_since_start = time.time() - self._start_time
        torrents_total, torrents_with_seeders = self.get_torrents_info_tuple()

        print(f"Time: {time_since_start:.0f}s, total: {torrents_total}, live: {torrents_with_seeders}")

        self._csv_writer.writerow([f"{time_since_start:.0f}", torrents_total, torrents_with_seeders])
        self._csv_file.flush()


class TriblerService:

    def __init__(self, configuration):
        self._configuration = configuration
        self.session = None
        self.process_checker = None

    async def start_tribler(self):
        print(f"Working dir:{self._configuration.tribler_working_dir}")
        # Check if we are already running a Tribler instance
        self.process_checker = ProcessChecker()
        if self.process_checker.already_running:
            print(f"Another Tribler instance is already using directory: {self._configuration.tribler_working_dir}")
            asyncio.get_event_loop().stop()
            return

        config = self.init_config()

        print("Starting Tribler session...")

        self.session = Session(config)
        await self.session.start()

        self.on_tribler_started()

    def on_tribler_started(self):
        print("Tribler started")
        asyncio.get_event_loop().create_task(self.terminate_by_timeout())

        self.enable_graceful_shutdown()
        self.init_popularity_community()

    def enable_graceful_shutdown(self):
        def signal_handler(signum, frame):
            print(f"Received shut down signal {signum} in frame {frame}")
            self.graceful_shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def graceful_shutdown(self):
        if not self.session.shutdownstarttime:
            task = asyncio.get_event_loop().create_task(self.session.shutdown())
            task.add_done_callback(lambda result: asyncio.get_event_loop().stop())

    async def terminate_by_timeout(self):
        await asyncio.sleep(self._configuration.timeout_in_sec)
        print("Terminated by timeout")
        self.graceful_shutdown()

    def init_popularity_community(self):
        session = self.session
        peer = Peer(session.trustchain_keypair)

        session.popularity_community = ObservablePopularityCommunity(peer, session.ipv8.endpoint,
                                                                     session.ipv8.network,
                                                                     metadata_store=session.mds,
                                                                     torrent_checker=session.torrent_checker,
                                                                     configuration=self._configuration)

        session.ipv8.overlays.append(session.popularity_community)
        session.ipv8.strategies.append((RandomWalk(session.popularity_community),
                                        self._configuration.tribler_target_peers_count))

    def init_config(self):
        config = TriblerConfig(self._configuration.tribler_working_dir,
                               config_file=self._configuration.tribler_config_path)

        config.set_tunnel_community_enabled(False)
        config.set_trustchain_enabled(False)
        config.set_market_community_enabled(False)
        config.set_popularity_community_enabled(False)
        config.set_bootstrap_enabled(False)

        config.set_torrent_checking_enabled(True)
        config.set_ipv8_enabled(True)
        config.set_libtorrent_enabled(True)
        config.set_dht_enabled(True)
        config.set_chant_enabled(True)

        return config


def _exception_handler(loop, context):
    # if any exception in loop
    #   then stop
    loop.default_exception_handler(context)
    print(context)
    loop.stop()


def _parse_argv(argv):
    configuration = Configuration()
    try:
        opts, _ = getopt.getopt(argv, "i:t:f:")
    except getopt.GetoptError:
        print('initial_filling.py -i <check_interval_in_sec> -t <timeout_in_sec> -f <output_file.csv>')
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-i':
            configuration.check_interval_in_sec = int(arg)
        elif opt == "-t":
            configuration.timeout_in_sec = int(arg)
        elif opt == "-f":
            configuration.output_file_name = arg

    print(configuration)
    return configuration


def main(argv):
    configuration = _parse_argv(argv)

    service = TriblerService(configuration)

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_exception_handler)
    loop.create_task(service.start_tribler())
    loop.run_forever()


if __name__ == "__main__":
    main(sys.argv[1:])
