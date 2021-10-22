# flake8: noqa
import argparse
import asyncio
import csv
import logging
import os
import time
from pathlib import Path

import sentry_sdk
from pony.orm import count, db_session

from ipv8.peerdiscovery.discovery import RandomWalk
from ipv8_service import IPv8
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.popularity.popularity_component import PopularityComponent
from tribler_core.components.restapi.restapi_component import RESTComponent
from tribler_core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler_core.components.torrent_checker.torrent_checker_component import TorrentCheckerComponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.components.gigachannel.community.sync_strategy import RemovePeers
from tribler_core.components.popularity.community.popularity_community import PopularityCommunity
from tribler_core.utilities.tiny_tribler_service import TinyTriblerService

_logger = logging.getLogger(__name__)
interval_in_sec = None
output_file_path = None

TARGET_PEERS_COUNT = 20  # Tribler uses this number for walking strategy

sentry_sdk.init(
    os.environ.get('SENTRY_URL'),
    traces_sample_rate=1.0
)


class ObservablePopularityComponent(PopularityComponent):
    community: PopularityCommunity
    _ipv8: IPv8

    async def run(self):
        config = self.session.config
        ipv8_component = await self.require_component(Ipv8Component)
        self._ipv8 = ipv8_component.ipv8
        peer = ipv8_component.peer
        metadata_store_component = await self.require_component(MetadataStoreComponent)
        torrent_checker_component = await self.require_component(TorrentCheckerComponent)

        community = ObservablePopularityCommunity(peer, self._ipv8.endpoint, self._ipv8.network,
                                                  settings=config.popularity_community,
                                                  rqc_settings=config.remote_query_community,
                                                  metadata_store=metadata_store_component.mds,
                                                  torrent_checker=torrent_checker_component.torrent_checker)
        self.community = community

        self._ipv8.add_strategy(community, RandomWalk(community), 30)
        self._ipv8.add_strategy(community, RemovePeers(community), -1)

        community.bootstrappers.append(ipv8_component.make_bootstrapper())

    async def shutdown(self):
        await self._ipv8.unload_overlay(self.community)


class ObservablePopularityCommunity(PopularityCommunity):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = logging.getLogger(self.__class__.__name__)

        self._start_time = time.time()

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
        csv_writer.writerow(['time_in_sec', 'total', 'alive'])
        return csv_file, csv_writer

    @db_session
    def get_torrents_info_tuple(self):
        return count(ts for ts in self.mds.TorrentState), \
               count(ts for ts in self.mds.TorrentState if ts.seeders > 0)

    def check(self):
        time_since_start = time.time() - self._start_time
        torrents_total, torrents_with_seeders = self.get_torrents_info_tuple()

        print(f"Time: {time_since_start:.0f}s, total: {torrents_total}, live: {torrents_with_seeders}")
        self._csv_writer.writerow([f"{time_since_start:.0f}", torrents_total, torrents_with_seeders])
        self._csv_file.flush()


class Service(TinyTriblerService):
    def __init__(self, timeout_in_sec, working_dir):
        super().__init__(config=TriblerConfig(state_dir=working_dir), timeout_in_sec=timeout_in_sec,
                         working_dir=working_dir,
                         components=[SocksServersComponent(), LibtorrentComponent(), TorrentCheckerComponent(),
                                     MetadataStoreComponent(), KeyComponent(), RESTComponent(), Ipv8Component(),
                                     ObservablePopularityComponent()])


def _parse_argv():
    parser = argparse.ArgumentParser(description='Calculate velocity of initial torrents list filling')

    parser.add_argument('-i', '--interval', type=int, help='how frequently (in sec) the torrent list has been checked',
                        default=10)
    parser.add_argument('-t', '--timeout', type=int, help='a time in sec that the experiment will last',
                        default=10 * 60)
    parser.add_argument('-f', '--file', type=str, help='result file path (csv)', default='result.csv')
    parser.add_argument('-v', '--verbosity', help='increase output verbosity', action='store_true')

    return parser.parse_args()


def _run_tribler(arguments):
    global interval_in_sec, output_file_path  # pylint: disable=global-statement
    working_dir = Path('/tmp/tribler/experiment/popularity_community/initial_filling/.Tribler')
    interval_in_sec = arguments.interval
    output_file_path = arguments.file
    service = Service(
        arguments.timeout,
        working_dir=working_dir)

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

    logging_level = logging.DEBUG if _arguments.verbosity else logging.CRITICAL
    logging.basicConfig(level=logging_level)

    _run_tribler(_arguments)
