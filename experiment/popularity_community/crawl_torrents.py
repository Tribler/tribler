"""This script crawl first 100 torrens from random nodes in the network.

### Usage

```
export PYTHONPATH=${PYTHONPATH}:`echo ../../../src/{pyipv8,tribler-common,tribler-core} | tr " " :`

python3 crawl_torrents.py [-t <timeout_in_sec>] [-f <db_file.sqlite>]
```

Where:
* `timeout_in_sec` means the time that the experiment will last
* `db_file.sqlite` means the path to `sqlite` db file.
    If file doesn't exists, then new file will be created.
    If file exists, then crawler will append it.

### Example

```
python3 crawl_torrents.py -t 600
python3 crawl_torrents.py -t 600 -f torrents.sqlite
```

"""
import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

import lz4
from pony.orm import Database, Required, db_session

from ipv8.lazy_community import lazy_wrapper
from ipv8.peer import Peer
from ipv8.peerdiscovery.discovery import RandomWalk
from tribler_core.modules.metadata_store.community.remote_query_community import RemoteQueryCommunity, \
    SelectResponsePayload, SelectRequest, RemoteSelectPayload
from tribler_core.modules.metadata_store.serialization import REGULAR_TORRENT
from tribler_core.utilities.unicode import hexlify
from experiment.tool.tiny_tribler_service import TinyTriblerService

UNLIMITED = -1  # const. Don't change.

IPV8_WALK_INTERVAL = 0.05

RANDOM_WALK_TIMEOUT_IN_SEC = 5
RANDOM_WALK_WINDOW_SIZE = 0
RANDOM_WALK_RESET_CHANCE = 30

CRAWLER_REQUEST_TIMEOUT_IN_SEC = 60

db = Database()


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

    def __init__(self, my_peer, endpoint, network, metadata_store, db_file_path):
        super().__init__(my_peer, endpoint, network, metadata_store)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.max_peers = UNLIMITED

        self.db = TorrentCrawler.create_db(db_file_path)

        self.register_task("request_torrents", self.request_torrents_from_new_peers, interval=10)

    def request_torrents_from_new_peers(self):
        """Send a request for gathering torrent information

        Behaviour:

        For all new peers the crawler request 100 most popular torrents.

        Note:   it is possible to request more, but it requires a significant
                increase of code complexity.
        Ref: see RemoteQueryCommunity.sanitize_query(query_dict, cap=100)
        """
        peers_ready_to_request = self.get_peers()
        self._logger.info(f"Request torrents from {len(peers_ready_to_request)} peers")

        for peer in peers_ready_to_request:
            self._logger.debug(f"Requesting torrents from {peer}.")
            self.send_select(peer, metadata_type=[REGULAR_TORRENT], sort_by="HEALTH", first=0, last=100)
            self._logger.debug(f"Marked as polled: {peer}")
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
        for index, (metadata, _) in enumerate(unpacked_data):
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

    # this method has been overloaded only for changing timeout
    def send_select(self, peer, **kwargs):
        request = CrawlerSelectRequest(self.request_cache, hexlify(peer.mid), kwargs)
        self.request_cache.add(request)
        self.ez_send(peer, RemoteSelectPayload(request.number, json.dumps(kwargs).encode('utf8')))

    def introduction_response_callback(self, peer, dist, payload):
        """ This method adds logging behaviour to the base implementation
        """
        self._logger.debug(f"Peer {peer} wants to introduce {payload.wan_introduction_address}")


class Service(TinyTriblerService):
    def __init__(self, output_file_path, timeout_in_sec, working_dir, config_path):
        super().__init__(Service.create_config(working_dir, config_path),
                         timeout_in_sec, working_dir, config_path)
        self._output_file_path = output_file_path

    @staticmethod
    def create_config(working_dir, config_path):
        config = TinyTriblerService.create_default_config(working_dir, config_path)

        config.set_ipv8_enabled(True)
        config.set_ipv8_walk_interval = IPV8_WALK_INTERVAL

        config.set_chant_enabled(True)
        return config

    async def on_tribler_started(self):
        await super().on_tribler_started()
        session = self.session
        peer = Peer(session.trustchain_keypair)

        session.remote_query_community = TorrentCrawler(peer, session.ipv8.endpoint,
                                                        session.ipv8.network,
                                                        session.mds, self._output_file_path)

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

    return parser.parse_args()


def _run_tribler(arguments):
    working_dir = Path('/tmp/tribler/experiment/popularity_community/crawl_torrents/.Tribler')
    service = Service(arguments.file, arguments.timeout,
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

    logging_level = logging.DEBUG if _arguments.verbosity else logging.INFO
    logging.basicConfig(level=logging_level)

    _run_tribler(_arguments)
