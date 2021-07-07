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

from ipv8.peer import Peer
from ipv8.peerdiscovery.discovery import RandomWalk
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity
from tribler_core.modules.dht.community import DHTDiscoveryStrategies
from tribler_core.modules.discovery.community import TriblerDiscoveryStrategies
from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity
from tribler_core.modules.popularity.community import PopularityCommunity
from tribler_core.modules.tunnel.community.community import TriblerTunnelCommunity
from tribler_core.session import CommunityFactory
from tribler_core.utilities.tiny_tribler_service import TinyTriblerService

_logger = logging.getLogger(__name__)

TARGET_PEERS_COUNT = 20  # Tribler uses this number for walking strategy

sentry_sdk.init(
    os.environ.get('SENTRY_URL'),
    traces_sample_rate=1.0
)


class ObservablePopularityCommunity(PopularityCommunity):

    def __init__(self, *args, interval_in_sec=0, output_file_path=None, **kwargs):
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
    def __init__(self, interval_in_sec, output_file_path, timeout_in_sec, working_dir, config_path):
        config = TriblerConfig(state_dir=working_dir, file=config_path)
        config.libtorrent.enabled = True
        config.ipv8.enabled = True
        config.chant.enabled = True
        config.upgrader_enabled = False
        config.chant.enabled = False

        self._interval_in_sec = interval_in_sec
        self._output_file_path = output_file_path

        super().__init__(config, timeout_in_sec, working_dir, config_path,
                         communities_cls=list(self.communities_gen(config)))

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

    def communities_gen(self, config: TriblerConfig):
        yield CommunityFactory(create_class=TriblerDiscoveryStrategies)
        yield CommunityFactory(create_class=DHTDiscoveryStrategies)
        yield CommunityFactory(create_class=BandwidthAccountingCommunity,
                               kwargs={'database': config.state_dir / "sqlite" / "bandwidth.db"})
        yield CommunityFactory(create_class=TriblerTunnelCommunity)
        yield CommunityFactory(create_class=ObservablePopularityCommunity,
                               kwargs={'interval_in_sec': self._interval_in_sec,
                                       'output_file_path': self._output_file_path})
        yield CommunityFactory(create_class=GigaChannelCommunity)


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
    working_dir = Path('/tmp/tribler/experiment/popularity_community/initial_filling/.Tribler')

    service = Service(arguments.interval,
                      arguments.file,
                      arguments.timeout,
                      working_dir=working_dir,
                      config_path=Path('./tribler.conf'))

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
