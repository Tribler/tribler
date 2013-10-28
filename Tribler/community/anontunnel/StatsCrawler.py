import os
import logging.config
logging.config.fileConfig(os.path.dirname(os.path.realpath(__file__)) + "/logger.conf")
logger = logging.getLogger(__name__)

import json
import sys
from threading import Thread, Event
from time import sleep
from datetime import datetime
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.community.anontunnel.ProxyCommunity import ProxyCommunity
from Tribler.dispersy.callback import Callback
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import RawserverEndpoint


class StatsCrawler(Thread):
    def __init__(self):
        Thread.__init__(self)

        self.stored_candidates = {}
        self.community = None

        self.server_done_flag = Event()
        self.raw_server = RawServer(self.server_done_flag,
                                    10.0 / 5.0,
                                    10.0,
                                    ipv6_enable=False)

        self.callback = Callback()

        self.endpoint = RawserverEndpoint(self.raw_server, port=10000)
        self.dispersy = Dispersy(self.callback, self.endpoint, u".", u":memory:")

        self.first = True
        self.community = None

        self.filename = datetime.now().strftime("%Y%m%d-%H%M%S.json")
        self.fout = open(self.filename, 'w')
        self.fout.write("[")

    def run(self):
        def join_overlay(dispersy):
            dispersy.define_auto_load(ProxyCommunity,
                                      (self.dispersy.get_new_member(), None, False),
                                      load=True)

        self.dispersy.start()
        self.dispersy.callback.call(join_overlay, (self.dispersy,))

        while True:
            communities = self.dispersy.get_communities()
            proxy_communities = filter(lambda c: isinstance(c, ProxyCommunity), communities)

            if proxy_communities:
                logger.error("Community loaded")
                self.community = proxy_communities[0]
                self.community.subscribe("on_stats", self.on_stats)
                break

            sleep(1)

        self.raw_server.listen_forever(None)

    @staticmethod
    def stats_to_txt(stats):
        return json.dumps(stats)

    def on_stats(self, e):

        # Do not store if we have received a STATS message from the same client before
        if e.message.candidate in self.stored_candidates:
            return

        if not self.first:
            self.fout.write(",")
        else:
            self.first = False

        self.fout.write(self.stats_to_txt(e.message.payload.stats))
        self.stored_candidates[e.message.candidate] = True

    def finalize_file(self):
        self.fout.write("]")
        self.fout.close()

    def __del__(self):
        self.finalize_file()

    def stop(self):
        self.dispersy.stop()
        self.finalize_file()
        self.server_done_flag.set()
        self.raw_server.shutdown()


def main():
    stats_crawler = StatsCrawler()
    stats_crawler.start()

    while 1:
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            stats_crawler.stop()
            break

        if not line:
            break

        if line == 'q\n':
            stats_crawler.stop()
            break

if __name__ == "__main__":
    main()
