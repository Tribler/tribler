"""This script crawl first 100 torrens from random nodes in the network.

### Usage

```
export PYTHONPATH=${PYTHONPATH}:`echo ../../../src/{pyipv8,tribler-common,tribler-core} | tr " " :`

python3 crawl_torrents.py [-t <timeout_in_sec>] [-f <output_file.json>]
```

Where:
* `timeout_in_sec` means a time that the experiment will last
* `output_file.json` means a path and a result file name

### Example

```
python3 crawl_torrents.py -t 600
python3 crawl_torrents.py -t 600 -f result.json
```

"""
import argparse
import asyncio
import json
import logging
import os
from collections import defaultdict

import lz4

from ipv8.lazy_community import lazy_wrapper
from ipv8.peer import Peer
from ipv8.peerdiscovery.discovery import RandomWalk
from tool.tiny_tribler_service import TinyTriblerService
from tribler_core.modules.metadata_store.community.remote_query_community import RemoteQueryCommunity, \
    SelectResponsePayload, SelectRequest, RemoteSelectPayload
from tribler_core.modules.metadata_store.serialization import REGULAR_TORRENT
from tribler_core.utilities.unicode import hexlify

UNLIMITED = -1  # this magic number is use inside many Tribler modules

IPV8_WALK_INTERVAL = 0.05

RANDOM_WALK_TIMEOUT_IN_SEC = 5
RANDOM_WALK_WINDOW_SIZE = 0
RANDOM_WALK_RESET_CHANCE = 30

CRAWLER_REQUEST_TIMEOUT_IN_SEC = 60
CRAWLER_SAVE_INTERVAL_IN_SEC = 60


class CrawlerSelectRequest(SelectRequest):
    """Custom class for RemoteQueryCommunity select request

    It has been added only for having an ability to increase `timeout_delay`
    """

    @property
    def timeout_delay(self):
        return CRAWLER_REQUEST_TIMEOUT_IN_SEC


class Crawler(RemoteQueryCommunity):
    """ Crawler based on RemoteQueryCommunity

    The approach based on two ideas:
        * use "aggressive" values for network walking (see ExperimentConfiguration.RANDOM_WALK_*)
        * use RemoteQueryCommunity's ability to select MetadataInfo from remote db
    """

    def __init__(self, my_peer, endpoint, network, metadata_store, out_file_path):
        super().__init__(my_peer, endpoint, network, metadata_store)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._output_file_path = out_file_path
        self.max_peers = UNLIMITED
        self.queried_peers_limit = UNLIMITED

        self.torrent_list = defaultdict(list)
        self.polled_peers = set()

        self.register_task("request_torrents", self.request_torrents_from_new_peers, interval=10)
        self.register_task("save_torrents", self.save, interval=CRAWLER_SAVE_INTERVAL_IN_SEC)

    def request_torrents_from_new_peers(self):
        """Send a request for gathering torrent information

        Behaviour:

        For all new pears: ```self.get_peers() - self.polled_peers```
        the crawler request 100 most popular torrents.

        Note:   it is possible to request more, but it requires a significant
                increase of code complexity.
        Ref: https://github.com/Tribler/tribler/blob/devel/src/tribler-core/tribler_core/modules/metadata_store/community/remote_query_community.py#L19
        """
        peers_ready_to_request = self.get_peers() - self.polled_peers
        self._logger.info(f"Request torrents from {peers_ready_to_request}")

        for peer in peers_ready_to_request:
            self._logger.debug(f"Requesting torrents from peer: {peer}")
            self.send_select(peer, metadata_type=[REGULAR_TORRENT], first=0, last=100)
            self._logger.debug(f"Marked as polled: {peer}")
            self.polled_peers.add(peer)

    @lazy_wrapper(SelectResponsePayload)
    async def on_remote_select_response(self, peer, response):
        self._logger.debug(f"Received select response from {peer}")

        decompressed_data = lz4.frame.decompress(response.raw_blob)
        unpacked_data = self.mds.process_squashed_mdblob(decompressed_data)

        for metadata, _ in unpacked_data:
            if not metadata:
                continue

            self.add_torrent_to_the_list(peer, metadata)

    def add_torrent_to_the_list(self, peer, metadata):
        key = hexlify(peer.mid)

        votes = int(getattr(metadata, 'votes', 0))
        infohash = hexlify(getattr(metadata, 'infohash', ''))
        title = getattr(metadata, 'title', '')

        self._logger.info(f"Collect torrent item for {key}: {title}")
        self.torrent_list[key].append((votes, infohash, title))

    # this method has been overloaded only for changing timeout
    def send_select(self, peer, **kwargs):
        request = CrawlerSelectRequest(self.request_cache, hexlify(peer.mid), kwargs)
        self.request_cache.add(request)
        self.ez_send(peer, RemoteSelectPayload(request.number, json.dumps(kwargs).encode('utf8')))

    def save(self):
        self._logger.info(f"Save results to : {self._output_file_path}")

        with open(self._output_file_path, 'w') as json_file:
            json.dump(self.torrent_list, json_file)

    def introduction_response_callback(self, peer, dist, payload):
        """ This method adds logging behaviour to the base implementation
        """
        super().introduction_response_callback(peer, dist, payload)
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

        session.remote_query_community_community = Crawler(peer, session.ipv8.endpoint,
                                                           session.ipv8.network,
                                                           session.mds, self._output_file_path)

        session.ipv8.overlays.append(session.remote_query_community_community)
        session.ipv8.strategies.append((RandomWalk(session.remote_query_community_community,
                                                   timeout=RANDOM_WALK_TIMEOUT_IN_SEC,
                                                   window_size=RANDOM_WALK_WINDOW_SIZE,
                                                   reset_chance=RANDOM_WALK_RESET_CHANCE),
                                        UNLIMITED))


def _parse_argv():
    parser = argparse.ArgumentParser(description='Crawl first 100 torrents from random nodes in the network')
    parser.add_argument('-t', '--timeout', type=int, help='a time in sec that the experiment will last', default=0)
    parser.add_argument('-f', '--file', type=str, help='result file path (json)', default='result.json')
    parser.add_argument('-v', '--verbosity', help='increase output verbosity', action='store_true')

    return parser.parse_args()


def _run_tribler(arguments):
    service = Service(arguments.file, arguments.timeout,
                      working_dir=os.path.join(
                          '/tmp/tribler/experiment/popularity_community/crawl_torrents',
                          '.Tribler'),
                      config_path='./tribler.conf')
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

    if _arguments.verbosity:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    _run_tribler(_arguments)
