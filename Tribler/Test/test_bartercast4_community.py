# Written by Cor-Paul Bezemer
# see LICENSE.txt for license information

from time import sleep

from nose.twistedtools import deferred, reactor

from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall, deferLater

from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.bartercast4.community import BarterCommunity, BarterCommunityCrawler
from Tribler.community.bartercast4.statistics import BartercastStatisticTypes, _barter_statistics
from Tribler.community.tunnel.tunnel_community import TunnelSettings
from Tribler.dispersy.util import blocking_call_on_reactor_thread


DEBUG = True
PEER_STATEDIR = "data"


class TestBarterCommunity(TestAsServer):

    """Start a tribler session and wait for the statistics to be increased."""

    def __init__(self, *argv, **kwargs):
        super(TestBarterCommunity, self).__init__(*argv, **kwargs)
        self._test_condition_lc = None

    @deferred(timeout=10)
    @inlineCallbacks
    def test_local_stats(self):
        def do_stats_test():
            tries_left = 300
            while True:
                for val in _barter_statistics.bartercast[BartercastStatisticTypes.TORRENTS_RECEIVED].itervalues():
                    if val > 0:
                        assert True, "Some torrent statistic was received"
                        return
                # wait for a bit
                yield deferLater(reactor, 1, lambda: None)
                tries_left = tries_left - 1
                if tries_left <= 0:
                    assert False, "No torrent statistics received"
                    return

        yield self.startTest(do_stats_test)

    @deferred(timeout=300)
    @inlineCallbacks
    def test_stats_messages(self):

        def do_stats_messages():
            # check if the crawler receives messages
            if len(_barter_statistics.get_interactions(self.dispersy)):
                # Some bartercast statistic was crawled.
                self._test_condition_lc.stop()
                self.quit()

        def has_finished():
            def check_running():
                return not self._test_condition_lc.running
            return check_running

        def noop():
            pass

        # Make it blocking so CallConditional can't do a check before the LoopingCall exists.
        @blocking_call_on_reactor_thread
        def start():
            self._test_condition_lc = LoopingCall(do_stats_messages)
            self._test_condition_lc.start(5, now=True)

        @blocking_call_on_reactor_thread
        def cleanup_and_fail(succeeded, err_msg):
            self._test_condition_lc.stop()
            self._test_condition_lc = None
            self.assert_(succeeded, err_msg)

        yield self.startTest(start)
        self.CallConditional(300.0, has_finished, noop, u"Failed to crawl", assert_callback=cleanup_and_fail)

    # for future stuff; you can use this if you need another peer for some reason
    @inlineCallbacks
    def setupPeer(self):
        from Tribler.Core.Session import Session

        self.setUpPreSession()

        self.config2 = self.config.copy()
        self.config2.set_state_dir(PEER_STATEDIR)

        self.session2 = Session(self.config2, ignore_singleton=True)

        upgrader = self.session2.prestart()
        while not upgrader.is_done:
            sleep(0.1)
        assert not upgrader.failed, upgrader.current_status
        yield self.session2.start()
        self.dispersy2 = self.session2.get_dispersy_instance()
        yield self.load_communities(self.session2, self.session2.get_dispersy_instance())

    def setUpPreSession(self):
        super(TestBarterCommunity, self).setUpPreSession()
        self.config.set_dispersy(True)
        self.config.set_megacache(True)
        self.config.set_enable_channel_search(True)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def load_communities(self, session, dispersy, crawler=False):
        keypair = dispersy.crypto.generate_key(u"curve25519")
        dispersy_member = yield dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))
        settings = TunnelSettings(tribler_session=session)
        settings.become_exitnode = True
        if crawler:
            yield dispersy.define_auto_load(BarterCommunityCrawler, dispersy_member, (session, settings), load=True)
        else:
            yield dispersy.define_auto_load(BarterCommunity, dispersy_member, (session, settings), load=True)

    @inlineCallbacks
    def setUp(self):
        super(TestBarterCommunity, self).setUp()
        self.dispersy = self.session.get_dispersy_instance()
        yield self.load_communities(self.session, self.dispersy, True)
        yield self.setupPeer()

    @inlineCallbacks
    def tearDown(self):
        if self.session2:
            yield self._shutdown_session(self.session2)

        super(TestBarterCommunity, self).tearDown()
