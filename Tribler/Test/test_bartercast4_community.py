# Written by Cor-Paul Bezemer
# see LICENSE.txt for license information

from Tribler.Test.test_as_server import TestAsServer

from Tribler.community.bartercast4.community import BarterCommunity, BarterCommunityCrawler
from Tribler.community.tunnel.tunnel_community import TunnelSettings
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.community.bartercast4.statistics import BartercastStatisticTypes, _barter_statistics


from time import sleep

DEBUG = True
CRAWLER_STATEDIR = "data"


class TestBarterCommunity(TestAsServer):
    """Start a tribler session and wait for the statistics to be increased."""

    def test_local_stats(self):
        def do_stats_test():
            tries_left = 300
            while True:
                for val in _barter_statistics.bartercast[BartercastStatisticTypes.TORRENTS_RECEIVED].itervalues():
                    if val > 0:
                        assert True, "Some torrent statistic was received"
                        return
                # wait for a bit
                sleep(1.0)
                tries_left = tries_left - 1
                if tries_left <= 0:
                    assert False, "No torrent statistics received"
                    return

        # self.startTest(do_stats_test)
        pass

    def test_stats_messages(self):
        self.setupCrawler()

        def do_stats_messages():
            # check that the crawler receives messages here
            pass

        self.startTest(do_stats_messages)

    def setupCrawler(self):
        from Tribler.Core.Session import Session

        self.setUpPreSession()

        self.config2 = self.config.copy()
        self.config2.set_state_dir(CRAWLER_STATEDIR)

        self.session2 = Session(self.config2, ignore_singleton=True)

        upgrader = self.session2.prestart()
        while not upgrader.is_done:
            sleep(0.1)
        assert not upgrader.failed, upgrader.current_status
        self.session2.start()
        self.load_communities(self.session2, self.session2.get_dispersy_instance(), True)

    def setUpPreSession(self):
        super(TestBarterCommunity, self).setUpPreSession()
        self.config.set_dispersy(True)
        self.config.set_megacache(True)
        self.config.set_enable_channel_search(True)

    @blocking_call_on_reactor_thread
    def load_communities(self, session, dispersy, crawler=False):
        keypair = dispersy.crypto.generate_key(u"curve25519")
        dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))
        settings = TunnelSettings(tribler_session=session)
        settings.do_test = False
        settings.become_exitnode = True
        if crawler:
            dispersy.define_auto_load(BarterCommunityCrawler, dispersy_member, (session, settings), load=True)
        else:
            dispersy.define_auto_load(BarterCommunity, dispersy_member, (session, settings), load=True)

    def setUp(self):
        super(TestBarterCommunity, self).setUp()
        dispersy = self.session.get_dispersy_instance()
        self.load_communities(self.session, dispersy)
        self.session2 = None

    def tearDown(self):
        if self.session2:
            self._shutdown_session(self.session2)
            sleep(10)

        super(TestBarterCommunity, self).tearDown()
