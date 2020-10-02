import asyncio
import csv
import getopt
import logging
import os
import sys
import time

from pony.orm import db_session, count

from ipv8.peer import Peer
from ipv8.peerdiscovery.discovery import RandomWalk
from popularity_community.tool.tiny_tribler_service import TinyTriblerService
from tribler_core.modules.popularity.popularity_community import PopularityCommunity

_logger = logging.getLogger(__name__)


# defaults
class ExperimentConfiguration:
    check_interval_in_sec = 10
    timeout_in_sec = 10 * 60
    output_file_name = 'result.csv'
    target_peers_count = 20

    def __str__(self):
        return f"Check interval: {self.check_interval_in_sec}s, " \
               f"timeout: {self.timeout_in_sec}s, " \
               f"target peers: {self.target_peers_count}, " \
               f"output file: {self.output_file_name}"


class ObservablePopularityCommunity(PopularityCommunity):

    def __init__(self, *args, **kwargs):
        self._experiment_configuration = kwargs.pop('experiment_configuration')
        super(ObservablePopularityCommunity, self).__init__(*args, **kwargs)
        self._logger = logging.getLogger(self.__class__.__name__)

        self._start_time = time.time()
        self._csv_file, self._csv_writer = self.init_csv_writer()

        self.register_task("check", self.check, interval=self._experiment_configuration.check_interval_in_sec)

    def __del__(self):
        if self._csv_file:
            self._csv_file.close()

    def init_csv_writer(self):
        csv_file = open(self._experiment_configuration.output_file_name, 'w')
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

        self._logger.info(f"Time: {time_since_start:.0f}s, total: {torrents_total}, live: {torrents_with_seeders}")

        self._csv_writer.writerow([f"{time_since_start:.0f}", torrents_total, torrents_with_seeders])
        self._csv_file.flush()


class Service(TinyTriblerService):
    def __init__(self, experiment_configuration, timeout_in_sec, working_dir, config_path):
        super(Service, self).__init__(Service.create_config(working_dir, config_path),
                                      timeout_in_sec,
                                      working_dir,
                                      config_path)

        self.experiment_configuration = experiment_configuration

    @staticmethod
    def create_config(working_dir, config_path):
        config = TinyTriblerService.create_default_config(working_dir, config_path)

        config.set_libtorrent_enabled(True)
        config.set_ipv8_enabled(True)
        config.set_chant_enabled(True)

        return config

    async def on_tribler_started(self):
        await super(Service, self).on_tribler_started()

        session = self.session
        peer = Peer(session.trustchain_keypair)

        session.popularity_community = ObservablePopularityCommunity(peer, session.ipv8.endpoint,
                                                                     session.ipv8.network,
                                                                     metadata_store=session.mds,
                                                                     torrent_checker=session.torrent_checker,
                                                                     experiment_configuration=self.experiment_configuration)

        session.ipv8.overlays.append(session.popularity_community)
        session.ipv8.strategies.append((RandomWalk(session.popularity_community),
                                        self.experiment_configuration.target_peers_count))


def _exception_handler(loop, context):
    loop.default_exception_handler(context)
    _logger.error(context)
    loop.stop()


def _parse_argv(argv):
    experiment_configuration = ExperimentConfiguration()
    try:
        opts, _ = getopt.getopt(argv, "i:t:f:")
    except getopt.GetoptError:
        print('get_all_nodes.py -i <check_interval_in_sec> -t <timeout_in_sec> -f <output_file.csv>')
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-i':
            experiment_configuration.check_interval_in_sec = int(arg)
        elif opt == "-t":
            experiment_configuration.timeout_in_sec = int(arg)
        elif opt == "-f":
            experiment_configuration.output_file_name = arg

    _logger.info(experiment_configuration)
    return experiment_configuration


def main(argv):
    logging.basicConfig(level=logging.INFO)
    experiment_configuration = _parse_argv(argv)

    service = Service(experiment_configuration,
                      experiment_configuration.timeout_in_sec,
                      working_dir=os.path.join(
                          '/tmp/tribler/experiment/popularity_community/initial_filling',
                          '.Tribler'),
                      config_path='./tribler.conf')

    loop = asyncio.get_event_loop()

    loop.set_exception_handler(_exception_handler)
    loop.create_task(service.start_tribler())

    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    main(sys.argv[1:])
