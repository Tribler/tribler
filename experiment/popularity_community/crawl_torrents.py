"""This script crawl first 100 torrens from random nodes in the network.

```
export PYTHONPATH=${PYTHONPATH}:`echo ../.. ../../src/{pyipv8,tribler-common,tribler-core} | tr " " :`

python3 crawl_torrents.py [-t <timeout_in_sec>] [-f <db_file.sqlite>] [-v]
                          [--peers_count_csv=<csv_file_with_peers_count>]
```

Where:
* `timeout_in_sec` means the time that the experiment will last
* `db_file.sqlite` means the path to `sqlite` db file.
    If file doesn't exists, then new file will be created.
    If file exists, then crawler will append it.
* `csv_file_with_peers_count` means the path to `csv` file that contains
    `(time, active_peers, crawled_peers)` tuples.

### Example

```
python3 crawl_torrents.py -t 600
python3 crawl_torrents.py -t 600 -f torrents.sqlite
python3 crawl_torrents.py -t 600 -f torrents.sqlite --peers_count_csv="peers.csv"
python3 crawl_torrents.py -t 600 -f torrents.sqlite --peers_count_csv="peers.csv" -v
```

"""
import argparse
import asyncio
import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import lz4
import sentry_sdk
from pony.orm import Database, Required, db_session

from ipv8.lazy_community import lazy_wrapper
from ipv8.peer import Peer
from ipv8.peerdiscovery.discovery import RandomWalk
from tribler_core.components.metadata_store.db.serialization import REGULAR_TORRENT
from tribler_core.components.metadata_store.remote_query_community.remote_query_community import RemoteQueryCommunity, \
    RemoteSelectPayload, \
    SelectRequest, \
    SelectResponsePayload
from tribler_core.components.metadata_store.remote_query_community.settings import RemoteQueryCommunitySettings
from tribler_core.utilities.tiny_tribler_service import TinyTriblerService
from tribler_core.utilities.unicode import hexlify

# flake8: noqa

UNLIMITED = -1  # const. Don't change.

IPV8_WALK_INTERVAL = 0.05

RANDOM_WALK_TIMEOUT_IN_SEC = 5
RANDOM_WALK_WINDOW_SIZE = 0
RANDOM_WALK_RESET_CHANCE = 30

CRAWLER_SELECT_REQUEST_INTERVAL_IN_SEC = 20
CRAWLER_SELECT_COUNT_LIMIT_PER_ONE_REQUEST = 20

CRAWLER_REQUEST_TIMEOUT_IN_SEC = 60

db = Database()

sentry_sdk.init(
    os.environ.get('SENTRY_URL'),
    traces_sample_rate=1.0
)


class RawData(db.Entity):
    peer_hash = Required(str)
    torrent_hash = Required(str)
    torrent_title = Required(str)
    torrent_votes = Required(int)
    torrent_position = Required(int)
    date_add = Required(datetime)


class CrawlerSelectRequest(SelectRequest):
    """Custom class for RemoteQueryCommunity select request

    It has been added only for having an ability to increase `timeout_delay`
    """

    @property
    def timeout_delay(self):
        return CRAWLER_REQUEST_TIMEOUT_IN_SEC


class TorrentCrawler(RemoteQueryCommunity):
    """ Crawler based on RemoteQueryCommunity

    The approach based on two ideas:
        * use "aggressive" values for network walking (see ExperimentConfiguration.RANDOM_WALK_*)
        * use RemoteQueryCommunity's ability to select MetadataInfo from remote db
    """

    def __init__(self, my_peer, endpoint, network, metadata_store, crawler_settings):
        super().__init__(my_peer, endpoint, network, metadata_store, rqc_settings=RemoteQueryCommunitySettings())
        self._logger = logging.getLogger(self.__class__.__name__)
        self._db = TorrentCrawler.create_db(crawler_settings.output_file_path)
        self._peers_count_csv_file = Path(crawler_settings.peers_count_csv_file_path).open("a")
        self._limit_per_one_request = CRAWLER_SELECT_COUNT_LIMIT_PER_ONE_REQUEST
        self._crawled_peers = defaultdict(lambda: 0)  # value is a count of crawled torrents

        self.max_peers = UNLIMITED
        self.start_time = datetime.utcnow()

        self.register_task("log_peer_count", self.log_peers_count, interval=60)
        self.register_task("request_torrents", self.request_torrents_from_new_peers,
                           interval=CRAWLER_SELECT_REQUEST_INTERVAL_IN_SEC)

    def log_peers_count(self):
        time = self.seconds_since_start()
        peers_count = len(self.get_peers())
        peers_crawled = len(self._crawled_peers)
        print(f"\nTime: {time}, peers: {peers_count}, crawled: {peers_crawled}")
        self._peers_count_csv_file.write(f"{time},{peers_count},{peers_crawled}\n")

    def request_torrents_from_new_peers(self):
        """Send a request for gathering torrent information

        Behaviour:

        For all new peers the crawler request 100 most popular torrents.

        Note:   it is possible to request more, but it requires a significant
                increase of code complexity.
        Ref: see RemoteQueryCommunity.sanitize_query(query_dict, cap=100)
        """
        print(f'\nTime: {self.seconds_since_start()}, starting select request')
        requested_select_count = 0
        for peer in self.get_peers():
            try:
                peer_has_already_been_crawled = peer.mid in self._crawled_peers
                if peer_has_already_been_crawled:
                    print('·', end='')
                    continue

                limit_reached = requested_select_count > self._limit_per_one_request
                if limit_reached:
                    print('Select limit reached')
                    break

                print(f"Requesting torrents from {hexlify(peer.mid)}")
                self.send_select(peer, metadata_type=[REGULAR_TORRENT],
                                 sort_by="HEALTH", first=0, last=100)
                requested_select_count += 1
            finally:
                self.network.remove_peer(peer)

    @lazy_wrapper(SelectResponsePayload)
    async def on_remote_select_response(self, peer, response):
        self._logger.debug(f"Received select response from {peer}")

        decompressed_data = lz4.frame.decompress(response.raw_blob)
        unpacked_data = self.mds.process_squashed_mdblob(decompressed_data)
        self.save_to_db(peer, unpacked_data)

    @staticmethod
    def create_db(file_path, provider='sqlite'):
        db_instance = db
        db_instance.bind(provider, file_path, create_db=True)
        db_instance.generate_mapping(create_tables=True)

        return db_instance

    @db_session
    def save_to_db(self, peer, unpacked_data):
        index = self._crawled_peers[peer.mid]
        for metadata, _ in unpacked_data:
            if not metadata:
                continue

            peer_hash = hexlify(peer.mid)
            votes = int(getattr(metadata, 'votes', 0))
            infohash = hexlify(getattr(metadata, 'infohash', ''))
            title = getattr(metadata, 'title', '')
            self._logger.debug(f"Collect torrent item for {peer_hash}: {title}")
            RawData(torrent_hash=infohash, torrent_title=title, peer_hash=peer_hash,
                    torrent_votes=votes, date_add=datetime.utcnow(),
                    torrent_position=index)
            index += 1

        self._crawled_peers[peer.mid] = index

    # this method has been overloaded only for changing timeout
    def send_select(self, peer, **kwargs):
        request = CrawlerSelectRequest(self.request_cache, hexlify(peer.mid), kwargs)
        self.request_cache.add(request)
        self.ez_send(peer, RemoteSelectPayload(request.number, json.dumps(kwargs).encode('utf8')))

    def introduction_response_callback(self, peer, dist, payload):
        """ This method adds logging behaviour to the base implementation
        """
        self._logger.debug(f"Peer {peer} wants to introduce {payload.wan_introduction_address}")

    def seconds_since_start(self):
        return (datetime.utcnow() - self.start_time).seconds


class Service(TinyTriblerService):
    def __init__(self, output_file_path, peers_count_csv_file_path, timeout_in_sec,
                 working_dir, config_path):
        super().__init__(Service.create_config(working_dir, config_path),
                         timeout_in_sec, working_dir, config_path)
        self._output_file_path = output_file_path
        self._peers_count_csv_file_path = peers_count_csv_file_path

    @staticmethod
    def create_config(working_dir, config_path):
        return TinyTriblerService.create_default_config(working_dir, config_path) \
            .put('ipv8', 'enabled', True) \
            .put('ipv8', 'walk_interval', IPV8_WALK_INTERVAL) \
            .put('chant', 'enabled', True)

    async def on_tribler_started(self):
        await super().on_tribler_started()
        session = self.session
        peer = Peer(session.trustchain_keypair)

        crawler_settings = SimpleNamespace(output_file_path=self._output_file_path,
                                           peers_count_csv_file_path=self._peers_count_csv_file_path)
        session.remote_query_community = TorrentCrawler(peer, session.ipv8.endpoint,
                                                        session.ipv8.network,
                                                        session.mds, crawler_settings)

        session.ipv8.overlays.append(session.remote_query_community)
        session.ipv8.strategies.append((RandomWalk(session.remote_query_community,
                                                   timeout=RANDOM_WALK_TIMEOUT_IN_SEC,
                                                   window_size=RANDOM_WALK_WINDOW_SIZE,
                                                   reset_chance=RANDOM_WALK_RESET_CHANCE),
                                        UNLIMITED))


def _parse_argv():
    parser = argparse.ArgumentParser(description='Crawl first 100 torrents from random nodes in the network')
    parser.add_argument('-t', '--timeout', type=int, help='the time in sec that the experiment will last', default=0)
    parser.add_argument('-f', '--file', type=str, help='sqlite db file path', default='torrents.sqlite')
    parser.add_argument('-v', '--verbosity', help='increase output verbosity', action='store_true')
    parser.add_argument('--peers_count_csv', type=str, help='csv file that logs peers count in time',
                        default='peers_count.csv')

    return parser.parse_args()


def _run_tribler(arguments):
    working_dir = Path('/tmp/tribler/experiment/popularity_community/crawl_torrents/.Tribler')
    service = Service(arguments.file, arguments.peers_count_csv, arguments.timeout,
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
